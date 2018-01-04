import requests
import inspect
import redis
import threading
import simplejson as json
import pymysql.cursors
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

from lib.commonfns import log_formatter
from datetime import datetime


def _get_stop_words(config):
    try:
        data = []
        conn = pymysql.connect(host=config['db_host'],
                               user=config['db_user'],
                               password=config['db_pass'],
                               port=config['db_port'],
                               db=config['db_name'],
                               charset='utf8mb4',
                               cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        sql = 'SELECT word FROM stop_word WHERE is_active = 1'
        cursor.execute(sql)
        data = cursor.fetchall()
        conn.close()
    except Exception as err:
        print "ERROR - failed to get stop words - {}".format(err)
    return [i['word'] for i in data]


def _encode_data(data_str):
    if data_str is None:
        return data_str

    data_str = data_str.lower()
    try:
        data_str.encode('utf-8')
    except UnicodeDecodeError:
        return data_str
    else:
        return data_str.encode('utf-8')


def register_search_activity(url, data):
    """
    add an entry to solr core
    """
    try:
        print log_formatter(inspect.stack()[0][3], "in register search solr")
        #prepare url for solr
        url = "{}/{}".format(url, "search_activity/update/json/docs?commit=true&wt=json")

        print log_formatter(inspect.stack()[0][3], "solr url {} - {}".format(url, data))

        response = requests.post(url, data=json.dumps(data))
        print log_formatter(inspect.stack()[0][3], "got resp search solr - {}".format(response))

        if response.status_code != 200:
            return False
        if json.loads(response.text)["responseHeader"]["status"] != 0:
            return False
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], "failed logging search activity - {}".format(str(err)), "ERROR")
        return False
    return True


def register_request(config_dict, param_dict):
    #insert into solr - trending search
    print log_formatter(inspect.stack()[0][3], "in register_request")
    if param_dict['author_found'] > 0 or param_dict['pratilipi_found'] > 0:
        data = {"activity_date": datetime.now().strftime("%Y-%m-%d"),
                "activity_hour": datetime.now().strftime("%H"),
                "platform": param_dict['platform'],
                "language": param_dict['language'],
                "userid": param_dict['userid'],
                "keyword": param_dict['text']}
        register_search_activity(config_dict['solr_url'],data)

    print log_formatter(inspect.stack()[0][3], "done solr insert")


    try:
        #TODO why connect all time, pool can be added ?
        r = redis.StrictRedis(config_dict['redis_url'], config_dict['redis_port'], config_dict['redis_db'])
        rvalue = "{}|{}|{}|{}".format(datetime.now().strftime("%Y-%m-%d"), param_dict['platform'], param_dict['language'], param_dict['text'])
      
        cntr = 1
        if r.hexists("daily_search_activity", rvalue): 
            cntr = r.hmget("daily_search_activity", rvalue) 
            cntr = int(cntr[0]) + 1

        r.hmset("daily_search_activity", {rvalue:cntr})
        rvalue = "{}|{}|{}|{}|{}|{}|{}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                                          param_dict['platform'],
                                          param_dict['language'],
                                          param_dict['userid'],
                                          str(param_dict['author_found']),
                                          str(param_dict['pratilipi_found']),
                                          param_dict['text'])
        r.hmset("user_search_activity_detail", {rvalue:1})
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], "failed logging request in redis - {}".format(str(err)), "ERROR")
        return False
    print log_formatter(inspect.stack()[0][3], "done register_request")
    return True


def trending_search(config_dict, data):
    """
    Trending Search
    - fetch data from datastore(solr) for trending search keywords
    """
    #parse query dict
    language = data.get('language', '*')
    platform = data.get('platform', 'web')
    limit = config_dict['trending_limit']
    age = config_dict['trending_age']

    try:
        #fetch search activities
        #prepare url for solr
        param_dict = {'wt':'json',
                      'group':'true',
                      'group.field':'keyword',
                      'rows':100000,
                      'fl':'keyword',
                      'q':'language:{} AND activity_date:[NOW-1DAY TO NOW]'.format(language)}
        url = "{}/{}".format(config_dict['solr_url'], "search_activity/select")

        print log_formatter(inspect.stack()[0][3], "trending search solr url %s" % url)
        print log_formatter(inspect.stack()[0][3], "trending search solr param %s" % param_dict)

        #generate response
        trending_keywords = {}
        response = requests.get(url, params=param_dict)
        if response.status_code == 200:
            data = json.loads(response.text)
            for row in data['grouped']['keyword']['groups']:
                trending_keywords[row['groupValue']] = row['doclist']['numFound']
        else:
            print "failed for trending search - {}".format(response.text)

        stop_word = _get_stop_words(config_dict)
        print "------> stopword - {}".format(stop_word)
        for sw in stop_word:
            for ky in trending_keywords.keys():
                if ky is None:
                    continue 

                k1 = _encode_data(sw)
                k2 = _encode_data(ky)
                
                if k1 in k2:
                    del(trending_keywords[ky])

        temp = sorted(trending_keywords, key=trending_keywords.get, reverse=True)
        if len(temp) == 0:
            return [200, "Success"]

        response = {'trending_keywords': temp[:int(limit)]}

        return [200, "Success", response]
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], "failed while getting trending search - {}".format(str(err)), "ERROR")
        return [500, 'Internal Server Error']


def author_data(config_dict, pdict):
    try:
        #fetch authors
        #prepare url for solr
        language_filter = '{}'.format(pdict['language']) if pdict['language'] is not None else '*'
        param_dict = {'wt':'json',
                      'fl':'author_id',
                      'sort':'score desc',
                      'rows':pdict['author_limit'],
                      'start':pdict['author_offset'],
                      'q':'*{}* AND language:{}'.format(pdict['text'], language_filter)}
        url = "{}/{}".format(config_dict['solr_url'], "author/select")

        print log_formatter(inspect.stack()[0][3], "solr url %s" % url)
        print param_dict

        #prepare author dict
        author = []
        author_count = 0
        response = requests.get(url, params=param_dict)

        if response.status_code == 200:
            data = json.loads(response.text)
            print "===========>>>> ", data
            author_count = data['response']['numFound']
            for row in data['response']['docs']:
                author.append(row['author_id'])

        #generate author response
        response = {}
        if author_count > 0 and pdict['author_offset'] < author_count:
            response['authors_found'] = author_count
            url = "{}".format(config_dict['author_url'])
            param_dict = {'id':','.join([str(x) for x in author])}
            print log_formatter(inspect.stack()[0][3], "called author service")
            print log_formatter(inspect.stack()[0][3], param_dict)
            
            service_response = requests.get(url, params=param_dict, headers={"User-Id":str(pdict['userid'])})

            print log_formatter(inspect.stack()[0][3], "done author service")
            if service_response.status_code == 200:
                response = {'authorList': [], 'authorCursor': pdict['author_offset'] + pdict['author_limit'] + 1, 'numberFound': author_count}
                found_auth = json.loads(service_response.text)
                found_auth = [i for i in found_auth if i] #remove empty keys
                for row in found_auth:
                    temp = {}
                    temp['authorId'] = row['authorId']
                    temp['name'] = row['fullName'] if 'fullName' in row else row['fullNameEn']
                    temp['pageUrl'] = row['pageUrl'] if 'pageUrl' in row else ''
                    temp['imageUrl'] = row['coverImageUrl'] if 'coverImageUrl' in row else ''
                    temp['profileImageUrl'] = row['profileImageUrl'] if 'profileImageUrl' in row else ''
                    temp['followCount'] = row['followCount'] if 'followCount' in row else 0
                    temp['contentPublished'] = row['contentPublished'] if 'contentPublished' in row else 0
                    temp['totalReadCount'] = row['totalReadCount'] if 'totalReadCount' in row else 0
                    temp['following'] = row['following'] if 'following' in row else False
                    response['authorList'].append(temp)
            else:
                print log_formatter(inspect.stack()[0][3], "call failed to author service", "ERROR")
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], "failed while searching - {}".format(str(err)), "ERROR")
        raise Exception('failed while processing author data')
    return response, author


def pratilipi_data(config_dict, pdict, author_found_list):
    try:
        #fetch pratilipis
        #prepare url for solr
        language_filter = '{}'.format(pdict['language']) if pdict['language'] is not None else '*'
        param_dict = {'wt':'json', 
                      'fl':'pratilipi_id', 
                      'sort':'score desc', 
                      'rows':pdict['pratilipi_limit'],
                      'start':pdict['pratilipi_offset'],
                      'q':'*{}* AND language:{}'.format(pdict['text'], language_filter)}
        url = "{}/{}".format(config_dict['solr_url'], "pratilipi/select")

        print log_formatter(inspect.stack()[0][3], "solr url %s" % url)
        print param_dict

        #prepare pratilipi dict
        pratilipi = []
        pratilipi_count = 0
        response = requests.get(url, params=param_dict)
        if response.status_code == 200:
            data = json.loads(response.text)
            pratilipi_count = data['response']['numFound']
            for row in data['response']['docs']:
                pratilipi.append(row['pratilipi_id'])

        #optimise result
        if pratilipi_count == 0 and len(author_found_list) > 0:
            #get pratilipi's for found author's
            param_dict = {'wt':'json',
                          'fl':'pratilipi_id',
                          'sort':'score desc',
                          'rows':pdict['pratilipi_limit'],
                          'start':pdict['pratilipi_offset'],
                          'q':'author_id:({}) AND language:{}'.format(' '.join(str(x) for x in author_found_list), language_filter)}
            url = "{}/{}".format(config_dict['solr_url'], "pratilipi/select")
            print log_formatter(inspect.stack()[0][3], "solr url %s" % url)

            #prepare pratilipi dict
            response = requests.get(url, params=param_dict)
            if response.status_code == 200:
                data = json.loads(response.text)
                print "===========>>>> ", data
                pratilipi_count = data['response']['numFound']
                for row in data['response']['docs']:
                    pratilipi.append(row['pratilipi_id'])


        #generate pratilipi response
        response = {}
        if pratilipi_count > 0 and pdict['pratilipi_offset'] < pratilipi_count:
            response['pratilipis_found'] = pratilipi_count
            url = "{}".format(config_dict['pratilipi_url'])
            param_dict = {'id':','.join([str(x) for x in pratilipi]), 'userId':pdict['userid']}
            print log_formatter(inspect.stack()[0][3], "called pratilipi service")
            print log_formatter(inspect.stack()[0][3], param_dict)
            service_response = requests.get(url, params=param_dict)
            print log_formatter(inspect.stack()[0][3], "done pratilipi service")
            if service_response.status_code == 200:
                found_pratilipi = json.loads(service_response.text)
                found_pratilipi = [i for i in found_pratilipi if i] #remove empty keys
                response = {'pratilipiList': found_pratilipi, 'pratilipiCursor': pdict['pratilipi_offset'] + pdict['pratilipi_limit'] + 1, 'numberFound': pratilipi_count}
            else:
                print log_formatter(inspect.stack()[0][3], "call failed to pratilipi service", "ERROR")
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], "failed while searching - {}".format(str(err)), "ERROR")
        raise Exception('failed while processing pratilipi data')
    return response


def search(config_dict, data, user_id):
    """
    Search
    - fetch data from datastore(solr) for authors and pratilipis
    - register request for analysis
    """
    #parse query dict
    param_dict = {}
    param_dict['userid'] = user_id
    param_dict['text'] = data.get('text', None)
    param_dict['language'] = data.get('language', None)
    param_dict['platform'] = data.get('platform', 'web')
    param_dict['is_active'] = data.get('is_active', True)
    param_dict['author_limit'] = int(data.get('authorResultCount', 10))
    param_dict['pratilipi_limit'] = int(data.get('pratilipiResultCount', 20))
    param_dict['author_offset'] = int(data.get('authorCursor', 0))
    param_dict['pratilipi_offset'] = int(data.get('pratilipiCursor', 0))

    print log_formatter(inspect.stack()[0][3], param_dict)

    if param_dict['text'] is None:
        return [400, "Bad Request"]

    response = {}
    author_found = 0
    pratilipi_found = 0
    author_found_list = []

    try:
        if param_dict['author_limit'] > 0:
            response['author'], author_found_list = author_data(config_dict, param_dict)
            author_found = response['author']['numberFound']
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], str(err))

    try:
        if param_dict['pratilipi_limit'] > 0:
            response['pratilipi'] = pratilipi_data(config_dict, param_dict, author_found_list)
            pratilipi_found = response['pratilipi']['numberFound']
    except Exception as err:
        print log_formatter(inspect.stack()[0][3], str(err))

    #if response is empty
    if not bool(response):
        return [204, "No Content"]

    #register request for analysis
    param_dict = {"language": param_dict['language'],
                  "userid": param_dict['userid'],
                  "platform": param_dict['platform'],
                  "text": param_dict['text'],
                  "author_found": author_found,
                  "pratilipi_found": pratilipi_found}
    thr = threading.Thread(target=register_request, args=(config_dict, param_dict))
    print log_formatter(inspect.stack()[0][3], "starting thread")
    thr.start()

    #return response
    return [200, "Success", response]

