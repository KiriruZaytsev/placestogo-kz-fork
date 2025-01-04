#!/bin/sh
readonly name="${1:-placestogo-db}"

if running="$(docker container inspect ${name} -f '{{.State.Running}}' 2>/dev/null)"; then
	if [ "${running}" = 'false' ]; then
		echo "Starting database"
		exec docker start ${name}
	else
		echo "Stopping database"
		exec docker stop ${name}
	fi
else
	if [ ! -f './backend/.env' ]; then
		echo "You should execute this script from the root of the repository!"
		exit 1
	fi

	echo "Creating database"
	exec docker run --name ${name} -p 5432:5432 --env-file ./backend/.env -d postgres:17.1
fi
