import torch
import chromadb
import numpy as np
import typing as tp
import pandas as pd
from openai import OpenAI
from sentence_transformers import SentenceTransformer

client_llm = OpenAI(base_url='http://localhost:8000/v1',
                    api_key='token_abc123')
SYS_ANSW_PROMPT = '''Ты русскоязычный туристический гид. Тебе нужно посоветовать гостю, \\
какие места из предложенного контекста можно посетить. Нужно советовать места только из предложенного контекста и никакие больше. \\
Ответ должен полностью охватывать запрос пользователя. Контекст: 
'''

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


def get_answer_llm(query: str,
                   context: str) -> tp.Tuple[str, str]:
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

if __name__ == '__main__':
    chroma_client = chromadb.HttpClient(host='localhost',
                                        port=8000)
    collection = chroma_client.get_collection('placestogo1')
    emb_model = SentenceTransformer('cointegrated/rubert-tiny2')
    emb_model.to('cuda')
    user_query = 'Хочу сходить в театр'
    user_city = 'Москва'
    retrieved = process_user_query(collection=collection,
                                   query=user_query,
                                   top_k=5,
                                   city=user_city)
    context = retrieved['documents'][0]
    print(get_answer_llm(user_query, context[0]))