#/bin/sh

INSTANCE_DNS=$1
REASON=$2

INSTANCE_DNS=`echo "$1" | grep -E "^[a-zA-Z0-9._-]*$"`
if [ -z "$INSTANCE_DNS" ]; then
    echo "Usage : $0 [DNS NAME] [Revoke Reason]"
    echo " Revoke Reason : keyCompromise, superseded (certificat replaced)"
    exit 1
fi

if [ -z "$REASON" ]; then
    echo "Usage : $0 [DNS NAME] [Revoke Reason]"
    echo " Revoke Reason : keyCompromise, superseded (certificat replaced)"
    exit 1
fi

certbot revoke \
	--cert-path /etc/letsencrypt/live/$INSTANCE_DNS/cert.pem \
	--key-path /etc/letsencrypt/live/$INSTANCE_DNS/privkey.pem \
	--reason $REASON

#certbot delete --cert-name $INSTANCE_DNS
