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

class MessageServiceServicer(bot_backend_pb2_grpc.MessageServiceServicer):
	def EchoMessage(self, request, context):
		logger.info(request.user_id + " said: " + request.text)
		return bot_backend_pb2.MessageResponse(text=request.text)

if __name__ == "__main__":
	load_dotenv()
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	logger = logging.getLogger()

	conn = None

	try:
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

		server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
		bot_backend_pb2_grpc.add_MessageServiceServicer_to_server(MessageServiceServicer(), server)
		server.add_insecure_port("[::]:50051")
		server.start()
		logger.info("Server started!")
		server.wait_for_termination()
	except (Exception, pg.DatabaseError) as error:
		print(error)
	finally:
		if conn is not None:
			conn.close()
			print("Closing database")
