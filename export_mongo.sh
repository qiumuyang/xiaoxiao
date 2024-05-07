#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <remote_host>"
    exit 1
fi

# Local MongoDB information
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="27017"
LOCAL_DB_NAME="nonebot2"
BACKUP_DIR="xiao_db"

mkdir -p $BACKUP_DIR

# Remote host information
REMOTE_HOST=$1
REMOTE_USER="ubuntu"
REMOTE_PORT="22"
REMOTE_DB_NAME=$LOCAL_DB_NAME
REMOTE_DB_HOST="localhost"
REMOTE_DB_PORT="27017"

# Export local MongoDB database
mongodump --host $LOCAL_DB_HOST --port $LOCAL_DB_PORT --db $LOCAL_DB_NAME --out $BACKUP_DIR

# Transfer backup to remote host
scp -P $REMOTE_PORT -r $BACKUP_DIR $REMOTE_USER@$REMOTE_HOST:~/

# Manual Import on Remote Host:
echo "Backup transferred to remote host. Now manually import the database using the following command:"
echo "> ssh -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST"
echo "> mongorestore --host $REMOTE_DB_HOST --port $REMOTE_DB_PORT --db $REMOTE_DB_NAME --drop ~/$(basename $BACKUP_DIR)/$LOCAL_DB_NAME"
