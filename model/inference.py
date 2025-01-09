import os
import sys
import logging
import typing as tp

from openai import OpenAI

import grpc
from concurrent.futures import ThreadPoolExecutor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import vectordb_llm_pb2, vectordb_llm_pb2_grpc

logger = None

client_llm = OpenAI(base_url='http://localhost:8000/v1',
                    api_key='token_abc123')
SYS_ANSW_PROMPT = '''Ты русскоязычный туристический гид. Тебе нужно посоветовать гостю, \\
какие места из предложенного контекста можно посетить. Нужно советовать места только из предложенного контекста и никакие больше. \\
Ответ должен полностью охватывать запрос пользователя. Контекст:
'''

def get_answer_llm(query: str, context: str) -> tp.Tuple[str, str]:
	'''
	Функция, формирующая рекомендацию-ответ на запрос пользователя
	Parameters:
		query: Запрос пользователя
		context: Контекст, полученный из векторной бд
	Return:
		Предложенный ответ и изображение, связанное с предложенным местом
	'''
	completion = client_llm.chat.completions.create(model='RefalMachine/ruadapt_qwen2.5_3B_ext_u48_instruct_v4',
                                                  messages=[{'role': 'system', 'content': SYS_ANSW_PROMPT + context},
                                                            {'role': 'user', 'content': query}])
	return completion.choices[0].message.content

class VectorDBLLMService(vectordb_llm_pb2_grpc.VectorDBLLMServicer):
	def Query(self, request, context):
		text = get_answer_llm(request.query, request.context)
		return vectordb_llm_pb2.QueryResponse(text=text, image_path="")

if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	logger = logging.getLogger()

	try:
		logger.info("Starting gRPC server...")
		server = grpc.server(ThreadPoolExecutor(max_workers=1))
		vectordb_llm_pb2_grpc.add_VectorDBLLMServicer_to_server(VectorDBLLMService(), server)
		server.add_insecure_port("[::]:50053")
		server.start()
		logger.info("gRPC server started!")
		server.wait_for_termination()
	except Exception as error:
		print(error)
	finally:
		logger.info("gRPC server stopped!")
