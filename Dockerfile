FROM 370531249777.dkr.ecr.ap-south-1.amazonaws.com/ubuntu-nginx:2.0.0

#set timezone
RUN rm /etc/localtime
RUN ln -s /usr/share/zoneinfo/Asia/Kolkata /etc/localtime
RUN export TZ=Asia/Kolkata

#search codebase
RUN mkdir -p /search/src
RUN mkdir -p /search/lib
RUN mkdir -p /search/config

#setup search env
COPY requirements.txt /search/
COPY main.py /search/
COPY wsgi.py /search/
COPY src/* /search/src/
COPY lib/* /search/lib/
COPY config/* /search/config/
COPY worker.py /search/
COPY pratilipi.py /search/
COPY re_indexer.py /search/

#setup nginx for search
RUN rm /etc/nginx/sites-available/default
COPY container_conf/search.nginx /etc/nginx/sites-available/search
RUN ln -s /etc/nginx/sites-available/search /etc/nginx/sites-enabled/

#setup search init script
COPY container_conf/search_init.sh /search/

#set work dir
WORKDIR /search

#install dependencies for search
RUN pip install -q -r requirements.txt

#container port expose
EXPOSE 80
