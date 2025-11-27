FROM python:3.13-trixie

#Create directories
RUN mkdir /config
RUN mkdir /certs
RUN mkdir /app
RUN mkdir /uploaded_files

RUN useradd -ms /bin/bash web

#Install requirements
COPY requirements.txt /
RUN apt-get update
RUN apt-get install acl
RUN pip install -r /requirements.txt
RUN rm /requirements.txt

#Install certs
COPY app /app

#Configure access write
RUN chmod -R 750 /certs
RUN chown -R root:web /certs

RUN chmod -R 770 /uploaded_files
RUN chown -R root:web /uploaded_files

RUN chmod -R 770 /config
RUN chown -R root:web /config

RUN chmod -R 750 /app
RUN chown -R root:web /app

COPY boot.sh /
RUN chmod -R 755 /boot.sh
RUN chown -R root:web /boot.sh

#Change current user
#USER web

#Docker config
WORKDIR /app
VOLUME /uploaded_files

#Docker container start
ENTRYPOINT ["/bin/bash"]
CMD ["/boot.sh"]

#PREVIOUS config with gunicorn :
#CMD ["gunicorn", "--bind", "0.0.0.0:443", "--workers", "1", "--timeout","60", "--certfile", "/certs/fullchain.pem", "--keyfile", "/certs/privkey.pem", "app:app"]
