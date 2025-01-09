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

class MessageServiceServicer(bot_backend_pb2_grpc.MessageServiceServicer):
	def EchoMessage(self, request, context):
		logger.info(request.user_id + " said: " + request.text)
		return bot_backend_pb2.MessageResponse(text=request.text)

	def Subscribe(self, request, context):
		text: str | None = None
		if request.city:
			cur = conn.cursor()
			cur.execute('')
			logger.info(request.user_id + " subbed to " + request.city)
			text = "Теперь вы будете получать ежедневную рассылку об интересностях в городе " + request.city
		else:
			logger.info(request.user_id + " attempted to sub with no city name")
			text = "Введите имя города после команды /subscribe"
		return bot_backend_pb2.SubscribeResponse(text=text)

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	logger = logging.getLogger()

	load_dotenv()

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
	except KeyboardInterrupt:
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
