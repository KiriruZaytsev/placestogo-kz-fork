import os
import sys
import logging
from concurrent import futures

import psycopg2 as pg
import grpc
from dotenv import load_dotenv

from . import core, service

import bot_backend_pb2_grpc

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	core.logger = logging.getLogger()

	load_dotenv()

	try:
		core.logger.info("Establishing PostgreSQL connection...")
		core.conn = pg.connect(
			dbname=os.getenv("POSTGRES_DB"),
			user=os.getenv("POSTGRES_USER"),
			password=os.getenv("POSTGRES_PASSWORD"),
			host="localhost",
		)
		cur = core.conn.cursor()
		cur.execute('select version()')
		ver = cur.fetchone()
		core.logger.info(ver)
		core.logger.info("PostgreSQL connection established!")

		try:
			core.logger.info("Creating user table...")
			cur.execute("""
				create table if not exists users (
					id bigint primary key,
					city varchar(100) not null
				);
			""")
			core.conn.commit()
			core.logger.info("User table created!")
		except Exception as e:
			core.logger.info("Failed to create users table: " + str(e))

		core.logger.info("Starting gRPC server...")
		server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
		bot_backend_pb2_grpc.add_BotBackendServicer_to_server(service.BotBackend(), server)
		server.add_insecure_port("[::]:50051")
		server.start()
		core.logger.info("gRPC server started!")
		server.wait_for_termination()
		core.logger.info("Stopping server...")
		server.stop()
		core.logger.info("Server stopped!")
	except (Exception, pg.DatabaseError) as error:
		print(error)
	finally:
		if core.conn is not None:
			core.logger.info("Closing database...")
			core.conn.close()
			core.logger.info("Database closed!")
