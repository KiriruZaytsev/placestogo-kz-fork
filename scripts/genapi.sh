#!/bin/sh
readonly inputdir="./api"
readonly outputdir="./api/generated"
readonly protofiles='bot_backend.proto bot_vectordb.proto vectordb_llm.proto'

if [ ! -d './api' ]; then
	echo "You should execute this script from the root of repository"
	exit 1
fi

if [ ! -d ${outputdir} ]; then
	mkdir ${outputdir}
fi

for f in ${protofiles}; do
	python -m grpc_tools.protoc \
		-I${inputdir} \
		--python_out=${outputdir} \
		--pyi_out=${outputdir} \
		--grpc_python_out=${outputdir} \
		${inputdir}/${f}
done
