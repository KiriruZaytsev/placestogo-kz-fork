import grpc

import bot_backend_pb2, bot_backend_pb2_grpc
import backend_vecdb_pb2, backend_vecdb_pb2_grpc

from . import core

backend_vecdb_channel = grpc.insecure_channel("localhost:50052")
backend_vecdb_stub = backend_vecdb_pb2_grpc.BackendVectorDBStub(backend_vecdb_channel)

class BotBackend(bot_backend_pb2_grpc.BotBackendServicer):
	def Start(self, request, context):
		core.logger.info(f"{request.user_id} attempts to register with {request.city} city")

		success = False

		try:
			cur = core.conn.cursor()
			cur.execute("""
				select exists (
					select 1 from (select distinct town from events) as vals
					where town = %s
				);
			""", (request.city,))
			success = cur.fetchone()[0]
		except Exception as e:
			core.logger.info(f"Failed to execute existence query for user {request.user_id} with {request.city} city: " + str(e))

		if success:
			try:
				cur.execute(f"""
					insert into users (id, city)
					values (%s, %s)
					on conflict (id) do update
					set city = %s;
				""", (request.user_id, request.city, request.city))
				core.conn.commit()
				core.logger.info(f"{request.user_id} registered with {request.city} city")
			except Exception as e:
				core.logger.info(f"Failed to register user {request.user_id} with {request.city} city: " + str(e))
				success = False
		else:
			core.logger.info(f"{request.user_id} was unable to register with {request.city} city")

		return bot_backend_pb2.StartResponse(success=success)

	def Chat(self, request, context):
		core.logger.info(f"{request.user_id} sent: {request.text}")

		cur = core.conn.cursor()
		cur.execute('select city from users where id = %s;', (request.user_id,))
		city = cur.fetchone()[0]

		backend_vecdb_request = backend_vecdb_pb2.EmbedRequest(user_id=request.user_id,
		                                                       query=request.text,
		                                                       city=city)
		backend_vecdb_response = backend_vecdb_stub.Embed(backend_vecdb_request)

		text = backend_vecdb_response.text
		image_path = backend_vecdb_response.image_path

		return bot_backend_pb2.ChatResponse(text=text, image_path=image_path)

	def Dislike(self, request, context):
		core.logger.info(f"{request.user_id} disliked the response")

		backend_vecdb_request = backend_vecdb_pb2.GetNextRequest(user_id=request.user_id)
		backend_vecdb_response = backend_vecdb_stub.GetNext(backend_vecdb_request)

		text = backend_vecdb_response.text
		image_path = backend_vecdb_response.image_path

		return bot_backend_pb2.ChatResponse(text=text, image_path=image_path)


