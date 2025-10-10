FROM python:3.12-rc-bullseye

RUN mkdir /config
COPY requirements.txt /config

RUN apt-get update
#RUN apt-get install -y libxml2-dev libxslt-dev
#graphviz
RUN pip install -r /config/requirements.txt

RUN mkdir /certs
COPY config /certs

RUN mkdir /app
COPY app /app
WORKDIR /app
#WORKDIR /

RUN mkdir /uploaded_files
VOLUME /uploaded_files

#ENTRYPOINT ["gunicorn"]
#ENTRYPOINT ["python3"]
#CMD ["app.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout","60", "--certfile", "/certs/server_cert.pem", "--keyfile", "/certs/server_key.pem", "app:app"]
#CMD ["gunicorn", "--bind", "0.0.0.0:5000","app:app"]
