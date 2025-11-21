# linked

```
MON_URL=example.com

curl \
    -X POST \
    -F "password=test" \
    -F "file=@monfichierbinaire.pdf" \
    #--insecure \
    "https://$MON_URL/"

curl \
    -X POST \
    -F "password=test" \
    -F "file=@test.txt" \
    #--insecure \
    "https://$MON_URL/"

curl \
    -X GET \
    #--insecure \
    -o monpdf.pdf\
    "https://$MON_URL/monfichierbinaire.pdf"

curl \
    -X GET \
    #--insecure \
    "https://$MON_URL/test.txt"
```
