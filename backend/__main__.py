import os
import sys
import logging
from concurrent import futures

import psycopg2 as pg
import grpc
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_backend_pb2, bot_backend_pb2_grpc

logger = None

conn = None

class BotBackendService(bot_backend_pb2_grpc.BotBackendServicer):
	def Start(self, request, context):
		logger.info(f"{request.user_id} attempts to register with {request.city} city")

		success = False

		try:
			cur = conn.cursor()
			cur.execute("""
				select exists (
					select 1 from (select distinct town from events) as vals
					where town = %s
				);
			""", (request.city,))
			success = cur.fetchone()[0]
		except Exception as e:
			logger.info(f"Failed to execute existence query for user {request.user_id} with {request.city} city: " + str(e))

		if success:
			try:
				cur.execute(f"""
					insert into users (id, city)
					values (%s, %s)
					on conflict (id) do update
					set city = %s;
				""", (request.user_id, request.city, request.city))
				conn.commit()
				logger.info(f"{request.user_id} registered with {request.city} city")
			except Exception as e:
				logger.info(f"Failed to register user {request.user_id} with {request.city} city: " + str(e))
				success = False
		else:
			logger.info(f"{request.user_id} was unable to register with {request.city} city")

		return bot_backend_pb2.StartResponse(success=success)


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	logger = logging.getLogger()

	load_dotenv()

	try:
		logger.info("Establishing PostgreSQL connection...")
		conn = pg.connect(
			dbname=os.getenv("POSTGRES_DB"),
			user=os.getenv("POSTGRES_USER"),
			password=os.getenv("POSTGRES_PASSWORD"),
			host="localhost",
		)
		cur = conn.cursor()
		cur.execute('select version()')
		ver = cur.fetchone()
		logger.info(ver)
		logger.info("PostgreSQL connection established!")

		try:
			logger.info("Creating user table...")
			cur.execute("""
				create table if not exists users (
					id bigint primary key,
					city varchar(100) not null
				);
			""")
			conn.commit()
			logger.info("User table created!")
		except Exception as e:
			logger.info("Failed to create users table: " + str(e))

		logger.info("Starting gRPC server...")
		server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
		bot_backend_pb2_grpc.add_BotBackendServicer_to_server(BotBackendService(), server)
		server.add_insecure_port("[::]:50051")
		server.start()
		logger.info("gRPC server started!")
		server.wait_for_termination()
		logger.info("Stopping server...")
		server.stop()
		logger.info("Server stopped!")
	except (Exception, pg.DatabaseError) as error:
		print(error)
	finally:
		if conn is not None:
			logger.info("Closing database...")
			conn.close()
			logger.info("Database closed!")
