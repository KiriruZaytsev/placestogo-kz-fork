# Places To Go

## Запуск сервера ChromaDB
Для запуска сервера ChromaDB необходимо выполнить следующую команду:
```
docker run -d --rm --name chromadb -p 8000:8000 \
        -v ./data/vectordb \
        -e IS_PERSISTENT=TRUE chromadb/chroma:0.5.13
```

## Запуск сервера с LLM
Для запуска сервера vllm необходимо в консоли Cloud.ru выполнить следующую команду:
```
vllm serve RefalMachine/ruadapt_qwen2.5_3B_ext_u48_instruct_v4
```