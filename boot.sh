#/bin/sh

date
echo "--- boot preparation -- begin ---"

if [ ! -d "/etc/letsencrypt/live/$INSTANCE_DNS" ] ; then
	echo "not found : $INSTANCE_DNS"
	certbot certonly \
		--standalone \
		--non-interactive \
		--agree-tos \
		--preferred-challenges http \
		--cert-name $INSTANCE_DNS \
		--key-type rsa \
		--rsa-key-size 4096 \
		-d $INSTANCE_DNS

	cat /var/log/letsencrypt/letsencrypt.log
fi

certbot show_account

certbot certificates

cp /etc/letsencrypt/live/$INSTANCE_DNS/* /certs
chmod 740 /certs/*
chown root:web /certs/*

export INSTANCE_DNS=$INSTANCE_DNS

setfacl -m u::rwx /uploaded_files
setfacl -m g::rwx /uploaded_files #for the 'w' bit : the deletion is protected by the non implmentation of DELETE in Flask

setfacl -m d:u::r-- /uploaded_files
setfacl -m d:g::r-- /uploaded_files
setfacl -m d:m::r-- /uploaded_files

echo "--- boot preparation -- end ---"
date

su - web -c "export INSTANCE_DNS=$INSTANCE_DNS && /app/app.py"

#certbot revoke \
#	--cert-path /etc/letsencrypt/live/$INSTANCE_DNS/cert.pem \
#	--key-path /etc/letsencrypt/live/$INSTANCE_DNS/privkey.pem \
###	--reason keyCompromise
###	--reason superseded #certificat replaced
### this will command line is interactive : certificate deletion

#certbot delete --cert-name $INSTANCE_DNS
