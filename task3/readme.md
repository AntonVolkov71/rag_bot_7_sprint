### Выбор эмбеддинг-модель
- Модель: sentence-transformers/all-MiniLM-L6-v2
- Размер эмбеддингов(вектора): 384
- Размер чанков: 900
  - исходя из того, что файлы БЗ небольшие, и сохранить смысловые куски
  - overlap: 150
- Время генерации: меньше минуты (не учитывается первоначальное время скачивания библиотек)
- Источник: Hugging Face
- Векторная БД: 
  - CromaDB локальная
  - persist_directory: vector_store_chroma
  - collection: folklore_kb

### Запуск
- установка зависимостей 
```
pip install -r requirements.txt
```

- запуск индексации из корня проекта
```
// активировать venv
.\.venv\Scripts\Activate.ps1

python ./task3/index.py
```

- результат скрипта
  - сохранённый индекс ChromaDB
  - вывод минитеста 
    - [output_tests.txt](output_tests.txt)
- алгоритм работы скрипта
  - Сканирует файлы knowledge_base/**.md
  - Для каждого файла определяет:
    - source - путь
    - entity - имя файла без расширения
    - category -  папка
  - деление на чанки через RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
  - построение эмбеддингов и запись в Chroma
  - Проверка минитестом запросами в ChromaDb
