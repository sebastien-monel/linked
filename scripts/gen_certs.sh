#/bin/sh

INSTANCE_DNS=`echo "$1" | grep -E "^[a-zA-Z0-9._-]*$"`
if [ -z "$INSTANCE_DNS" ]; then
    echo "Usage : $0 [DNS NAME]"
    exit 1
fi

date

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

	#cat /var/log/letsencrypt/letsencrypt.log
fi

certbot show_account

certbot certificates

cp /etc/letsencrypt/live/$INSTANCE_DNS/* /certs
chmod 740 /certs/*
chown root:web /certs/*

date
