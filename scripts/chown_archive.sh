#/bin/sh

FILE_NAME=`echo "$1" | grep -E "^[0-9a-f-]{36}$"`
if [ -z "$FILE_NAME" ]; then
    echo "Usage : $0 [FILE_NAME]"
    exit 1
fi

chown root:root /uploaded_files/$FILE_NAME
chmod 440 /uploaded_files/$FILE_NAME
