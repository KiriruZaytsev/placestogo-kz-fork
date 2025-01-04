import torch
import chromadb
import numpy as np
import typing as tp
import pandas as pd
from openai import OpenAI
from sentence_transformers import SentenceTransformer

emb_model = SentenceTransformer('cointegrated/rubert-tiny2')
emb_model.to('cuda')

client = chromadb.Client()
collection = client.create_collection(name='placestogo')

llm_client = OpenAI(base_url='http://localhost:8000/v1',
                api_key='token_abc123')
SYS_ANSW_PROMPT = '''Ты русскоязычный туристический гид. Тебе нужно посоветовать гостю, \\
какие места из предложенного контекста можно посетить. Нужно советовать места только из предложенного контекста. \\
Ответ должен быть кратким, но полностью охватывать запрос пользователя. Контекст: 
'''

def create_embeddings(texts: tp.List[str]) -> np.ndarray:
    '''
    Создание эмбеддингов для описаний
    Parameters:
        texts: Список с текстами
    Return:
        np.ndarray с эмбеддингами текстов
    '''
    embeddings = emb_model.encode(texts)
    return embeddings


def add_items_to_collection(data: pd.DataFrame) -> None:
    '''
    Добавление новых объектов в векторную базу данных
    Parameters:
        data: DataFrame, у которого должны быть 3 поля: 'description' с текстовым описанием мероприятия,
            'city' с названием города, 'img_path' - путь до изображения
    '''
    documents = data['description'].to_list()
    cities = data['city'].to_list()
    img_paths = data['img_path'].to_list()
    embeddings = create_embeddings(documents)
    ids = [f'doc_{i}' for i in range(len(documents))]
    metadatas = [{'city': cities[i], 'img_path': img_paths[i]} for i in range(len(cities))]
    collection.add(documents=documents,
                   embeddings=embeddings,
                   metadatas=metadatas,
                   ids=ids)
    

def process_user_query(query: str,
                       top_k: int=1) -> tp.Dict[str, tp.Any]:
    '''
    Функция для обработки сообщения пользователя
    Parameters: 
        query: Текст с запросом пользователя
    Return:
        Словарь с городом проведения мероприятия, его описанием и путём до изображений, связанных
            с мероприятиями
    '''
    query_embeddings = create_embeddings([query])
    result = collection.query(query_embeddings=query_embeddings,
                              n_results=top_k,
                              include=['documents', 'metadatas'])
    preprocessed_res = {}
    preprocessed_res['city'] = [result['metadatas'][0][i]['city'] for i in range(top_k)]
    preprocessed_res['documents'] = result['documents']
    preprocessed_res['img'] = [result['metadatas'][0][i]['img_path'] for i in range(top_k)]
    return preprocessed_res

def get_answer_llm(query: str) -> tp.Tuple[str, str]:
    '''
    Функция, формирующая рекомендацию-ответ на запрос пользователя
    Parameters:
        query: Запрос пользователя
    Return:
        Предложенный ответ и изображение, связанное с предложенным местом
    '''
    retrieved_result = process_user_query(query=query)
    context = '; '.join(retrieved_result['documents'][0])
    completion = llm_client.chat.completions.create(model='RefalMachine/ruadapt_qwen2.5_3B_ext_u48_instruct_v4',
                                                    messages=[{'role': 'system', 'content': SYS_ANSW_PROMPT + context},
                                                              {'role': 'user', 'content': query}])
    return completion.choices[0].message.content

df = pd.read_csv('../data/text_data.csv')
add_items_to_collection(df)

query = 'Хочу сходить в парк'
print(get_answer_llm(query))
