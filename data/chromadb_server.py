import os
import sys
import logging

from dotenv import load_dotenv

import torch
import chromadb
import numpy as np
import typing as tp
import pandas as pd
from rank_bm25 import BM25Okapi
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

import psycopg2 as pg

import grpc
from concurrent.futures import ThreadPoolExecutor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import backend_vecdb_pb2, backend_vecdb_pb2_grpc
import vectordb_llm_pb2, vectordb_llm_pb2_grpc

logger = None

collection = None
emb_model = None

vectordb_llm_channel = grpc.insecure_channel("localhost:50053")
vectordb_llm_stub = vectordb_llm_pb2_grpc.VectorDBLLMStub(vectordb_llm_channel)

max_suggestions = 5
storage = dict()

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


# NOTE(vladeemerr): data is expected to contain `name`, `description`, `town` and `path`
def add_items_to_collection(collection: chromadb.api.models.Collection.Collection,
                            data: pd.DataFrame) -> None:
    '''
    Добавление новых объектов в векторную базу данных
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


def rerank_items(documents: tp.List[str]) -> tp.List[int]:
    '''
    Делает реранкинг найденных с помощью ALS эмбеддингов
    Parameters:
        documents: Список с документами
    Return:
        Список индексов переранжированных документов
    '''
    splitted_docs = [txt.split() for txt in documents]
    bm25 = BM25Okapi(splitted_docs)
    bm25_scores = bm25.get_scores(splitted_docs)
    indicies = np.argsort(bm25_scores)[::-1]
    return indicies


def process_user_query(collection: chromadb.api.models.Collection.Collection,
                       query: str,
                       start_k_docs: int=100,
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
                              n_results=start_k_docs,
                              where=filter,
                              include=['documents', 'metadatas'])
    top_k_indicies = rerank_items(result['documents'][0])[:top_k]
    preprocessed_res = {}
    preprocessed_res['city'] = [result['metadatas'][0][idx]['city'] for idx in top_k_indicies]
    preprocessed_res['documents'] = [result['documents'][idx] for idx in top_k_indicies]
    preprocessed_res['img'] = [result['metadatas'][0][idx]['img_path'] for idx in top_k_indicies]
    return preprocessed_res


class BackendVectorDBService(backend_vecdb_pb2_grpc.BackendVectorDBServicer):
	def Embed(self, request, context):
		suggestions = process_user_query(collection, request.query, max_suggestions, request.city)
		storage[request.user_id] = {
			'counter': 1,
			'query': request.query,
			'documents': suggestions['documents'][0],
			'images': suggestions['img']
		}
		info = suggestions['documents'][0][0]
		image_path = suggestions['img'][0]
		vecdb_llm_request = vectordb_llm_pb2.QueryRequest(query=request.query, context=info)
		vecdb_llm_response = vectordb_llm_stub.Query(vecdb_llm_request)
		return backend_vecdb_pb2.EmbedResponse(text=vecdb_llm_response.response, image_path=image_path)

	def GetNext(self, request, context):
		if request.user_id in storage.keys():
			index = storage[request.user_id]['counter']
			if index < max_suggestions:
				query = storage[request.user_id]['query']
				info = storage[request.user_id]['documents'][index]
				image_path = storage[request.user_id]['images'][index]
				vecdb_llm_request = vectordb_llm_pb2.QueryRequest(query=query, context=info)
				vecdb_llm_response = vectordb_llm_stub.Query(vecdb_llm_request)
				storage[request.user_id]['counter'] += 1
				return backend_vecdb_pb2.EmbedResponse(text=vecdb_llm_response.response, image_path=image_path)
		return backend_vecdb_pb2.EmbedResponse(text="", image_path="")


###

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()

    load_dotenv()

    conn = pg.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="localhost",
    )

    logger.info("Starting ChromaDB client...")
    chroma_client = chromadb.HttpClient(host='localhost',
                                        port=8000,
                                        settings=Settings(allow_reset=True, anonymized_telemetry=False))
    logger.info("ChromaDB client started!")

    emb_model = SentenceTransformer('cointegrated/rubert-tiny2')

    logger.info("Initalizing ChromaDB collection...")
    chroma_client.delete_collection('placestogo-vecdb')
    collection = chroma_client.get_or_create_collection('placestogo-vecdb')

    cur = conn.cursor()
    cur.execute('select name, description, town, path from events')
    df = pd.DataFrame(cur.fetchall(), columns=['name', 'description', 'town', 'path'])

    add_items_to_collection(collection=collection, data=df)
    logger.info("ChromaDB collection initialized!")

    logger.info("Starting gRPC server...")
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    backend_vecdb_pb2_grpc.add_BackendVectorDBServicer_to_server(BackendVectorDBService(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    logger.info("gRPC server started!")
    server.wait_for_termination()
