#!/bin/sh

TO_RENEW=`sudo certbot certificates | grep EXPIRED | wc -l`

echo "Number of expired certificates : $TO_RENEW"

if [ $TO_RENEW -gt 0 ]; then
  certbot renew
fi
