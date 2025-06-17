#!/bin/bash

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <user>@<remote_host>"
    exit 1
fi

REMOTE="$1"
REMOTE_USER=$(echo $REMOTE | cut -d'@' -f1)
REMOTE_HOST=$(echo $REMOTE | cut -d'@' -f2)
REMOTE_PORT="22"

DB_NAME="files"
DUMP_DIR="dump_${DB_NAME}_$(date +%Y%m%d_%H%M%S)"

echo "📦 Dumping MongoDB database: $DB_NAME"
mongodump --host localhost --port 27017 --db "$DB_NAME" --out "$DUMP_DIR" --gzip

echo "🚀 Transferring dump to $REMOTE..."
scp -P "$REMOTE_PORT" -r "$DUMP_DIR" "$REMOTE_USER@$REMOTE_HOST:~/"

echo "🧹 Cleaning up local dump..."
rm -rf "$DUMP_DIR"

echo ""
echo "✅ Transfer complete. To restore on remote:"
echo "> ssh -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST"
echo "> mongorestore --gzip --drop ~/$(basename $DUMP_DIR)"

