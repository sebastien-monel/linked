#/bin/sh
cp /etc/letsencrypt/live/$INSTANCE_DNS/* /certs
chmod 740 /certs/*
chown root:web /certs/*

su - web -c "/app/app.py"
