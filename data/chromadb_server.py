import os
import sys
import logging

import torch
import chromadb
from chromadb.config import Settings
import numpy as np
import typing as tp
import pandas as pd
from sentence_transformers import SentenceTransformer

import grpc
from concurrent.futures import ThreadPoolExecutor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_vectordb_pb2, bot_vectordb_pb2_grpc
import vectordb_llm_pb2, vectordb_llm_pb2_grpc

logger = None

collection = None

def create_embeddings(texts: tp.List[str]) -> np.ndarray:
    '''
    Создание эмбеддингов для описаний
    Parameters:
        texts: Список с текстами
    Return:
        np.ndarray с эмбеддингами текстов
    '''
    embeddings = []
    for txt in texts:
        embed = emb_model.encode(txt)
        embeddings.append(embed)
    return np.array(embeddings)


def add_items_to_collection(collection: chromadb.api.models.Collection.Collection,
                            data: pd.DataFrame) -> None:
    '''
    Добавление новых объектов в векторную базу данных
    Parameters:
        data: DataFrame, у которого должны быть 3 поля: 'description' с текстовым описанием мероприятия,
            'city' с названием города, 'img_path' - путь до изображения
    '''
    names = data['name'].to_list()
    documents = data['description'].to_list()
    documents = [names[i] + ' ' + documents[i] for i in range(len(documents))]
    cities = data['town'].to_list()
    img_paths = data['path'].to_list()
    embeddings = create_embeddings(documents)
    ids = [f'doc_{i}' for i in range(len(documents))]
    metadatas = [{'city': cities[i], 'img_path': img_paths[i]} for i in range(len(cities))]
    collection.add(documents=documents,
                   embeddings=embeddings,
                   metadatas=metadatas,
                   ids=ids)

def process_user_query(collection: chromadb.api.models.Collection.Collection,
                       query: str,
                       top_k: int=5,
                       city: str='Москва') -> tp.Dict[str, tp.Any]:
    '''
    Функция для обработки сообщения пользователя
    Parameters:
        query: Текст с запросом пользователя
        top_k: Количество релевантных текстов, которые будут использоваться
        city: Город пользователя
    Return:
        Словарь с городом проведения мероприятия, его описанием и путём до изображений, связанных
            с мероприятиями
    '''
    filter = {'city': city}
    query_embeddings = create_embeddings([query])
    result = collection.query(query_embeddings=query_embeddings,
                              n_results=top_k,
                              where=filter,
                              include=['documents', 'metadatas'])
    preprocessed_res = {}
    preprocessed_res['city'] = [result['metadatas'][0][i]['city'] for i in range(top_k)]
    preprocessed_res['documents'] = result['documents']
    preprocessed_res['img'] = [result['metadatas'][0][i]['img_path'] for i in range(top_k)]
    return preprocessed_res

#    user_query = 'Хочу сходить в театр'
#    user_city = 'Москва'
#    retrieved = process_user_query(collection=collection,
#                                   query=user_query,
#                                   top_k=5,
#                                   city=user_city)
#    context = retrieved['documents'][0]
#    print(get_answer_llm(user_query, context[0]))

vectordb_llm_channel = grpc.insecure_channel("localhost:50053")
vectordb_llm_stub = vectordb_llm_pb2_grpc.VectorDBLLMStub(vectordb_llm_channel)

class BotVectorDBService(bot_vectordb_pb2_grpc.BotVectorDBServicer):
	def Query(self, request, context):
		vecdb_llm_request = vectordb_llm_pb2.QueryRequest(query=request.text, context="")
		vecdb_llm_response = vectordb_llm_stub.Query(vecdb_llm_request)
		return bot_vectordb_pb2.ChatResponse(text=vecdb_llm_response.text)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()
    logger.info("Starting ChromaDB client...")
    chroma_client = chromadb.HttpClient(host='localhost',
                                        port=8000,
                                        settings=Settings(allow_reset=True, anonymized_telemetry=False))
    logger.info("ChromaDB client started!")

    logger.info("Initalizing ChromaDB collection...")
    #collection = chroma_client.create_collection(name='placestogo1')
    #emb_model = SentenceTransformer('cointegrated/rubert-tiny2')
    #emb_model.to('cuda')

    #df = pd.read_csv('./data/text_data.csv')
    #add_items_to_collection(collection=collection,
    #                        data=df)

    logger.info("Starting gRPC server...")
    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    bot_vectordb_pb2_grpc.add_BotVectorDBServicer_to_server(BotVectorDBService(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    logger.info("gRPC server started!")
    server.wait_for_termination()
