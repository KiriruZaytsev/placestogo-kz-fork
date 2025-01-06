import torch
import chromadb
import numpy as np
import typing as tp
import pandas as pd
from sentence_transformers import SentenceTransformer

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
    

if __name__ == '__main__':
    chroma_client = chromadb.HttpClient(host='localhost',
                                        port=8000)
    collection = chroma_client.create_collection(name='placestogo1')
    emb_model = SentenceTransformer('cointegrated/rubert-tiny2')
    emb_model.to('cuda')
    df = pd.read_csv('./data/text_data.csv')
    add_items_to_collection(collection=collection,
                            data=df)