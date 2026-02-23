FROM python:3.13-trixie

#Create directories
RUN mkdir /config
RUN mkdir /certs
RUN mkdir /app
RUN mkdir /npm
RUN mkdir /uploaded_files

RUN useradd -ms /bin/bash web

#Install requirements
COPY requirements.txt /
RUN apt-get update
#RUN apt-get install -y acl
RUN apt-get install -y sudo net-tools #iptables 
RUN pip install -r /requirements.txt
RUN rm /requirements.txt

#!!!!!
#RUN echo "Plugin sudoers_policy sudoers.so" >> /etc/sudo.conf
#RUN echo "Plugin sudoers_io sudoers.so" >> /etc/sudo.conf
#RUN echo "Debug sudo /var/log/sudo_debug all@debug" >> /etc/sudo.conf
#RUN echo "Debug sudoers.so /var/log/sudoers_debug all@debug" >> /etc/sudo.conf

#RUN chmod 744 /etc/sudoers
RUN echo "web ALL=(ALL) NOPASSWD:/scripts/gen_certs.sh" >> /etc/sudoers.d/gen_certs
RUN echo "web ALL=(ALL) NOPASSWD:/scripts/revoke_certs.sh" >> /etc/sudoers.d/revoke_certs
RUN echo "web ALL=(ALL) NOPASSWD:/scripts/chown_archive.sh" >> /etc/sudoers.d/chown_archive
RUN echo "web ALL=(ALL) NOPASSWD:/usr/bin/netstat" >> /etc/sudoers.d/netstat
#RUN echo "web ALL=(ALL) NOPASSWD:/usr/bin/su" >> /etc/sudoers.d/su
#RUN echo "web ALL=(ALL) NOPASSWD:/usr/bin/cat" >> /etc/sudoers.d/cat
#!!!!

#Install certs
COPY npm /npm
COPY app /app
COPY scripts /scripts

#Configure access write
RUN chmod -R 750 /certs
RUN chown -R root:web /certs

RUN chmod -R 770 /uploaded_files
RUN chown -R root:web /uploaded_files

RUN chmod -R 770 /config
RUN chown -R root:web /config

RUN chmod -R 750 /npm
RUN chown -R root:web /npm

RUN chmod -R 750 /app
RUN chown -R root:web /app

RUN chmod -R 750 /scripts
RUN chown -R root:web /scripts
#RUN chmod -R 4750 /scripts/*

#COPY boot.sh /
#RUN chmod -R 755 /boot.sh
#RUN chown -R root:web /boot.sh

#Change current user
USER web

#Docker config
WORKDIR /app
VOLUME /uploaded_files

#Docker container start
ENTRYPOINT ["/app/app.py"]

#PREVIOUS config with gunicorn :
#CMD ["gunicorn", "--bind", "0.0.0.0:443", "--workers", "1", "--timeout","60", "--certfile", "/certs/fullchain.pem", "--keyfile", "/certs/privkey.pem", "app:app"]
