FROM python:3.12-rc-bullseye

#Create directories
RUN mkdir /config
RUN mkdir /certs
RUN mkdir /app
RUN mkdir /uploaded_files

RUN useradd -ms /bin/bash web

#Install requirements
COPY requirements.txt /config
RUN apt-get update
RUN pip install -r /config/requirements.txt

#Install certs
COPY config /certs
COPY app /app

#Configure access write
RUN chmod 660 /certs/*
RUN chown root:web /certs/*

RUN chmod 770 /uploaded_files
RUN chown root:web /uploaded_files

#Change current user
USER web

#Docker config
WORKDIR /app
VOLUME /uploaded_files

#Docker container start
##ENTRYPOINT ["gunicorn"]
##ENTRYPOINT ["python3"]
#CMD ["app.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:443", "--workers", "1", "--timeout","60", "--certfile", "/certs/fullchain.pem", "--keyfile", "/certs/privkey.pem", "app:app"]
