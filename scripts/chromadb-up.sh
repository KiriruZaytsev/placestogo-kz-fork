#!/bin/sh
if [ ! -d ./data ]; then
	echo "You must run this script from the root of repository!"
	exit 1
fi
[ ! -d ./data/chroma ] && mkdir ./data/chroma
exec docker run -d --rm --name chromadb -p 8000:8000 -v ./data/chroma:/chroma/chroma -e IS_PERSISTENT=TRUE chromadb/chroma:0.5.13
