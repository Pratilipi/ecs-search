import os
import boto3

# env
STAGE = "local" if "STAGE" not in os.environ else os.environ["STAGE"]
API_END_POINT = 'http://localhost' if 'API_END_POINT' not in os.environ else os.environ['API_END_POINT']

# 3rd party services details
AUTH_SERVICE_URL = API_END_POINT
FOLLOW_SERVICE_URL = API_END_POINT

# data source
SOLR_URL = "http://localhost:8983/solr" if 'SEARCH_SOLR_DB_ENDPOINT' not in os.environ else os.environ['SEARCH_SOLR_DB_ENDPOINT']
SQS_QUEUE_REGION = os.environ['SQS_QUEUE_REGION']

# worker config
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
POLL_SLEEP_TIME = 1

# 3rd party services
PRATILIPI_SERVICE_URL = "{}/{}".format(os.environ['API_END_POINT'], "pratilipis")
PRATILIPI_PUBLISHED_QUERYING_URL = "{}/{}".format(os.environ['API_END_POINT'], "pratilipi/v2.0/pratilipis")
AUTHOR_SERVICE_URL = "{}/{}".format(os.environ['API_END_POINT'], "authors")

# store analysis
REDIS_DB = 6

# search app config
TOP_SEARCH_LIMIT = 10
TOP_SEARCH_AGE_IN_MIN = 3600

# db access details from parameter store
USER_NAME = 'root' if 'MASTER_MYSQL_DB_USERNAME' not in os.environ else os.environ['MASTER_MYSQL_DB_USERNAME']
PASSWORD = 'root' if 'MASTER_MYSQL_DB_PASSWORD' not in os.environ else os.environ['MASTER_MYSQL_DB_PASSWORD']

DB = {'name': 'search', 'host': '', 'port': 3306, 'user': USER_NAME, 'pass': PASSWORD}
DB['host'] = 'localhost' if 'MASTER_DB_ENDPOINT_RW' not in os.environ else os.environ['MASTER_DB_ENDPOINT_RW']


#if in devo , port = 6379, and endpoint will come from env var in 
if STAGE in ("devo", "gamma", "prod"):
    REDIS_URL = "prod-ecs-001.cpzshl.0001.apse1.cache.amazonaws.com" if 'MASTER_REDIS_ENDPOINT' not in os.environ else os.environ['MASTER_REDIS_ENDPOINT']
    REDIS_PORT = 8080 if 'MASTER_REDIS_PORT' not in os.environ else os.environ['MASTER_REDIS_PORT'] 
elif STAGE == "local":
    REDIS_URL = "localhost"
    REDIS_PORT = 6379

if STAGE in ("gamma", "prod"):
    ALGOLIA_PRATILIPI_INDEX_TEMPLATE = "prod_{}_pratilipi"
    ALGOLIA_AUTHOR_INDEX_TEMPLATE = "prod_{}_author"
else:
    ALGOLIA_PRATILIPI_INDEX_TEMPLATE = "devo_{}_pratilipi"
    ALGOLIA_AUTHOR_INDEX_TEMPLATE = "devo_{}_author"

# algolia config
ALGOLIA_APP_ID = os.environ['ALGOLIA_APP_ID']
ALGOLIA_API_KEY = os.environ['ALGOLIA_API_KEY']
