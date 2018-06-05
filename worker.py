import os
import ujson
import time
import boto3
import solr
from config import config
from algoliasearch import algoliasearch
from lib import serviceapis

# setting encoding for app
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# config
SOLR_URL = config.SOLR_URL
SQS_QUEUE_URL = config.SQS_QUEUE_URL
POLL_SLEEP_TIME = config.POLL_SLEEP_TIME
SQS_QUEUE_REGION = config.SQS_QUEUE_REGION
ALGOLIA_APP_ID = config.ALGOLIA_APP_ID
ALGOLIA_API_KEY = config.ALGOLIA_API_KEY 

algolia_client = algoliasearch.Client(ALGOLIA_APP_ID, ALGOLIA_API_KEY)

class Event:
    def __init__(self):
        """init sqs"""
        setattr(self, 'type', None)
        setattr(self, 'version', None)
        setattr(self, 'resource', None)
        setattr(self, 'resource', None)

class Author:
    def __init__(self, kwargs):
        """init"""
        """solr connection setup"""
	self._conn = solr.SolrConnection('{}/author'.format(SOLR_URL))

 	"""algolia connection setup"""
	algolia_client = algoliasearch.Client(ALGOLIA_APP_ID, ALGOLIA_API_KEY)
	algolia_client.search_timeout = (1, 5)
	algolia_client.timeout = (1,30)
	self._algolia = algolia_client

        for name in kwargs:
            attribute = self.transformer(name)
            if attribute is None: continue
            value = kwargs[name]
            setattr(self, attribute, value)

    def __del__(self):
        self._conn.close()

    def transformer(self, key):
        key = key.lower().strip()
        attribute = {}
        attribute['authorid'] = 'author_id'
        attribute['language'] = 'language'
        attribute['firstname'] = 'first_name'
        attribute['lastname'] = 'last_name'
        attribute['firstnameen'] = 'first_name_en'
        attribute['lastnameen'] = 'last_name_en'
        attribute['penname'] = 'pen_name'
        attribute['pennameen'] = 'pen_name_en'
        attribute['summary'] = 'summary'
        return attribute[key] if key in attribute else None
        
    def add(self):
        """add doc"""
	doc = self.__dict__

        if self.get() is not None: return
        self._conn.add(author_id=doc['author_id'], language=doc.get('language'), first_name=doc.get('first_name',None),
                       last_name=doc.get('last_name', None), pen_name=doc.get('pen_name', None),
                       first_name_en=doc.get('first_name_en', None), last_name_en=doc.get('last_name_en'),
                       pen_name_en=doc.get('pen_name_en', None), summary=doc.get('summary', None))
        self._conn.commit()
        print "------author added - ", doc['author_id']

    def delete(self):
        """delete doc"""
        if self.get() is None: return

        self._conn.delete_query("author_id:{}".format(self.author_id))
        self._conn.commit()

	"""delete from algolia"""
	print "Author to delete",self.author_id
	pdict = {}
        pdict['author_id'] = self.author_id
        pdict['deleted'] = True
	pdict['user_id'] = 0
	authors = serviceapis.get_authors(pdict) 
	if len(authors) > 0:
		temp = authors[0]
		language = temp['language'].lower()
		algolia_index = self._algolia.init_index("prod_{}_author".format(language))
		#print "deleted author"
		algolia_index.delete_object(self.author_id)

		"""delete author related pratilipis"""
		self.algolia_pratilipi_index = self._algolia.init_index("prod_{}_pratilipi".format(language))
		old_ptlps = self.getAlgoliaPratilipisByAuthorId()
		if len(old_ptlps) > 0:
			for hit in old_ptlps['hits']:
				if int(hit['authorId']) == self.author_id:
					print "pratilipi to delete as author deleted ",self.author_id, hit['objectID']
					self.algolia_pratilipi_index.delete_object(hit['objectID'])
	
        print "------author deleted - ", self.author_id

    def get(self):
        """get doc"""
        dataset = self._conn.query("author_id:{}".format(self.author_id))
        data = None
        for row in dataset:
            data = row
        return data
	
    def update(self):
        """update doc"""

	new_doc = self.__dict__
	old_doc = self.get()
        if old_doc is None:
            print "------ERROR - can't update author not found - {}".format(self.author_id)
            return

        for key in new_doc: old_doc[key] = new_doc[key]
        for key in old_doc: setattr(self, key, old_doc[key])
        self.delete()
        self.add()


	"""update algolia object"""
	print "updating the algolia object"
	if new_doc.get('language') is not None:
                self._algolia_index = self._algolia.init_index("prod_{}_author".format(new_doc.get('language').lower()))
		self.algolia_pratilipi_index = self._algolia.init_index("prod_{}_pratilipi".format(new_doc.get('language').lower()))
                print "prod_{}_author".format(new_doc.get('language').lower())
	
	pdict = {}
	pdict['author_id'] = self.author_id
	pdict['user_id'] = 0
	authors = serviceapis.get_authors(pdict)
	#print ("Got some authors")
	if len(authors) > 0:
		#print "The other from service ",authors[0]
		#old_doc = self.getAlgoliaObject()
        	#if old_doc is None:
		temp = authors[0]
		if int(temp['contentPublished']) > 0:
			print "create author", temp['authorId']
			author = {}
        		author["objectID"]=self.author_id,
                	author["name"]=temp.get('name',""),
                        author["nameEn"]=temp.get('nameEn',""),
	                author["penName"]=temp.get('penName',""),
	        	author["penNameEn"]=temp.get('penNameEn',"")
        	        author["firstName"]=temp.get('firstName',"")
                	author["lastName"]=temp.get("lastName","")
	                author["firstNameEn"]=temp.get("firstNameEn","")
        	        author["lastNameEn"]=temp.get("lastNameEn","")
	                author["summary"]=temp.get("summary","")
        	        author["contentPublished"]=temp.get("contentPublished","")
	        	author["totalReadCount"]=temp.get("totalReadCount","")
			print "The author to update ", author
			self._algolia_index.partial_update_object(author,True)

			"""Update pratilipis with author info"""
			old_ptlps = self.getAlgoliaPratilipisByAuthorId()
			ptlps = []
			for hit in old_ptlps['hits']:	
				if int(hit['authorId']) == self.author_id:
					ptlp = {}
					ptlp['objectID'] = hit['objectID']
					ptlp['authorName']=author["name"]
					ptlp['authorNameEn']=author["nameEn"]
					ptlp['authorPenName']=author["penName"]
					ptlp['authorPenNameEn']=author["penNameEn"]
					#ptlp_json =  ujson.dumps(ptlp)
					#print ptlp_json
					print "pratilipi updated with other info",self.author_id, hit['objectID']
					self.algolia_pratilipi_index.partial_update_object(ptlp)
    
    def getAlgoliaObject(self):
	"""get from algolia"""
	try:
		record = self._algolia_index.get_object(self.author_id)
		return ujson.loads(ujson.dumps(record))
	except Exception as err:
		return None
	
    def getAlgoliaPratilipisByAuthorId(self):
	"get pratilipis from algolia by author_id"
	try:
		records = self.algolia_pratilipi_index.search(self.author_id,{"attributesToRetrieve":"objectID,authorId"})
		return ujson.loads(ujson.dumps(records))
	except Exception as err:
		print err
		return None

class Pratilipi:
    def __init__(self, kwargs):
        """init"""
        	
	"""solr connection setup"""
	self._conn = solr.SolrConnection('{}/pratilipi'.format(SOLR_URL))
	
	"""algolia connection setup"""
	algolia_client = algoliasearch.Client(ALGOLIA_APP_ID, ALGOLIA_API_KEY)
	algolia_client.search_timeout = (1, 5)
	algolia_client.timeout = (1,30)
	self._algolia = algolia_client

        for name in kwargs:
            attribute = self.transformer(name)
            if attribute is None: continue
            value = kwargs[name]
            setattr(self, attribute, value)
	
    def __del__(self):
        self._conn.close()

    def transformer(self, key):
        key = key.lower().strip()
        attribute = {}
        attribute['pratilipiid'] = 'pratilipi_id'
        attribute['language'] = 'language'
        attribute['authorid'] = 'author_id'
        attribute['title'] = 'title'
        attribute['titleen'] = 'title_en'
        attribute['summary'] = 'summary'
        attribute['cotenttype'] = 'content_type'
        attribute['category'] = 'category'
        attribute['categoryen'] = 'category_en'
        return attribute[key] if key in attribute else None

    def add(self):
	doc = self.__dict__
        """add doc"""
	if self.get() is not None: return

        self._conn.add(pratilipi_id=doc['pratilipi_id'], language=doc.get('language', None), author_id=doc.get('author_id',None),
                       title=doc.get('title', None), title_en=doc.get('title_en', None),
                       summary=doc.get('summary', None), content_type=doc.get('content_type'),
                       category=doc.get('category', None), category_en=doc.get('category_en', None))
        self._conn.commit()
	print "Pratilipi added to solr"
	
	
	"""add pratilipi to algolia"""
	
	temp_pratilipis = get_pratilipis(config,doc) 

	if doc.get('language') is not None:
                self._algolia_index = self._algolia.init_index("prod_{}_pratilipi".format(doc.get('language').lower()))
		print "prod_{}_pratilipi".format(doc.get('language').lower())

	if self.getAlgoliaObject() is not None: return

	pratilipi = {
		
	}
	
	pratilipi_json = ujson.loads(ujson.dumps(pratilipi))
	#self._algolia_index.add_object(pratilipi_json)
	print "Pratilipi added to algolia"

        print "------pratilipi added - {}".format(doc['pratilipi_id'])

    def delete(self):
        """delete doc"""
        if self.get() is None: return
        self._conn.delete_query("pratilipi_id:{}".format(self.pratilipi_id))
        self._conn.commit()

	"""delete from algolia"""
	#doc = self.__dict__
	#if doc.get('langauge') is not None:
        #       algolia_index = self._algolia("prod_{}_pratilipi".format(doc.get('language')))
	#	algolia_index.delete_object(self.pratilipi_id)

        print "------pratilipi deleted - ", self.pratilipi_id

    def get(self):
        """get doc"""
	
        dataset = self._conn.query("pratilipi_id:{}".format(self.pratilipi_id))
        data = None
        for row in dataset:
            data = row
        return data
	
    def update(self):
        """update doc"""
	new_doc = self.__dict__
        old_doc = self.get()
        if old_doc is None:
            print "------ERROR - can't update pratilipi not found - {}".format(self.pratilipi_id)
            return
	
	for key in new_doc: old_doc[key] = new_doc[key]
        for key in old_doc: setattr(self, key, old_doc[key])
        self.delete()
        self.add()

	"""update algolia object"""
	if new_doc.get('language') is not None:
                self._algolia_index = self._algolia.init_index("prod_{}_pratilipi".format(new_doc.get('language').lower()))
                print "prod_{}_pratilipi".format(new_doc.get('language').lower())
	
	old_doc = self.getAlgoliaObject()

	if old_doc is None:
	    print "------ERROR - can't update pratilipi not found - {}".format(self.pratilipi_id)
	    return

	if old_doc['title'] != new_doc['title'] or old_doc['titleEn'] != new_doc['title_en']:
		new_object = {
			"objectID":new_doc['pratilipi_id'],
			"title":new_doc.get('title', ""),
			"titleEn":new_doc.get('title_en',""),
			"authorID":new_doc.get('author_id',"")						
		}
		pratilipi_json = ujson.loads(ujson.dumps(new_object))
		#self._algolia_index.partial_update_object(pratilipi_json)	
		
        print "------pratilipi updated - ", self.pratilipi_id

    def getAlgoliaObject(self):
	"""get from algolia"""
	try:
		record = self._algolia_index.get_object(self.pratilipi_id)
		return ujson.loads(ujson.dumps(record))
	except Exception as err:
		return None


class SearchQueue:
    def __init__(self):
        """init sqs"""
        setattr(self, 'client', boto3.client('sqs', region_name=SQS_QUEUE_REGION))
        setattr(self, 'url', SQS_QUEUE_URL)

    def poll(self):
        """poll queue"""
        setattr(self, 'events', [])
      	 
	response = self.client.receive_message(QueueUrl=self.url, MaxNumberOfMessages=1,  AttributeNames=[ 'SentTimestamp' ])
        if 'Messages' not in response: return
        for msg in response['Messages']:
            # TODO validate request as per schema
            body = ujson.loads(msg['Body'])
            data = body['Message']
            temp = ujson.loads(data)
            temp = ujson.loads(temp) if not isinstance(temp, dict) else temp

            event = Event
            event.type = temp['event']
            event.version = temp['version']
            event.resource_id = temp['meta']['resourceId']
            event.message = {} if 'message' not in temp else temp['message']
            event.rcpthandle = msg['ReceiptHandle']
            self.events.append(event)
	
	"""
	event = Event
	event.type = "PRATILIPI.ADD"
	event.version = "v2.0"
	event.resource_id = 63239529976300602
	event.message = {
		"title":"Title",
		"titleEn":"Title english ADD 2",
		"language":"HINDI",
		"pratilipiId":"63239529976300601",
		"authorId":"6800000000409487",
		"contentType":"HINDI"
	}
	event.rcpthandle = "abcdefghijklmnop..."
	self.events.append(event)
		
	event = Event
	event.type = "AUTHOR.DELETE"
	event.version = "v2.0"
	event.resource_id = 6800000000391729
	event.message = {
                "firstName":"firstname updated",
		"lastName":"lastName",
		"firstNameEn":"firstname en",
		"lastNameEn":"lastname en",
		"penName":"pen name",
		"penNameEn":"pen name en",
                "authorId":"6800000000391729",
		"language":"HINDI"
        }
        event.rcpthandle = "abcdefghijklmnop..."
        self.events.append(event)
	"""
    def process_author(self, action, author_id, kwargs):
        kwargs['authorId'] = author_id
        author = Author(kwargs)
        print "----encountered author - ", action, kwargs
        eval("{}.{}()".format("author", action.lower()))

    def process_pratilipi(self, action, pratilipi_id, kwargs):
        kwargs['pratilipiId'] = pratilipi_id
        pratilipi = Pratilipi(kwargs)
        print "----encountered pratilipi - ", action, kwargs
        eval("{}.{}()".format("pratilipi", action.lower()))

    def process(self):
        """process queue"""
        print "--processing event"
        events = self.events
        for event in events:
            resource, action = event.type.upper().split('.')

            if resource not in ("AUTHOR", "PRATILIPI"):
                self.client.delete_message( QueueUrl=self.url, ReceiptHandle=event.rcpthandle )
                continue

            if action not in ("ADD", "DELETE", "UPDATE"):
                self.client.delete_message( QueueUrl=self.url, ReceiptHandle=event.rcpthandle )
                continue

            if resource == "AUTHOR":
                self.process_author(action, event.resource_id, event.message)
            elif resource == "PRATILIPI":
                self.process_pratilipi(action, event.resource_id, event.message)
            self.client.delete_message( QueueUrl=self.url, ReceiptHandle=event.rcpthandle )

print "worker started listening for events...."
while True:
    try:
        print "poll queue...."
        event_q = SearchQueue()
        event_q.poll()
    except Exception as err:
        print "ERROR - sqs polling failed, {}".format(err)

    try:
        if len(event_q.events) > 0:
            event_q.process()
        print "sleeping now...."
        time.sleep(POLL_SLEEP_TIME)
    except Exception as err:
        print "ERROR - event processing failed, {}".format(err)


