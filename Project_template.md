### Задание 1
- теория, выбор моделей, эмбендингов
  - [readme.md](task1/readme.md)

### Задание 2
- создание своей Базы Знаний (далее БЗ)
  - результат ./knowledge_base
  - описание [readme.md](task2/readme.md)


### Задание 3 
- разбивка на чанки, создание векторов из БЗ
  - [readme.md](task3/readme.md)
- скрипт индексации: 
  - [index.py](task3/index.py)

- результат индексации
  - Chroma
    - [vector_store_chroma](vector_store_chroma)
  - тестовые запросы 
    - [output_tests.txt](task3/output_tests.txt)
  - время генерации: 
    - меньше минуты (не учитывается первоначальное время скачивания библиотек)

### Задание 4
- создано два сервиса rag через REST API и бот телеграмм
  - описание работы и запуск сервисов [readme.md](task4/readme.md)

- выявлено, что RAG-сервис на запросе из CromaDB сначала выдавал некорректные ответы
  - добавлено в скрипт индексации базы знаний - генерация файла entities.json
  - перезапускаем индексацию как в Задании 3 файл скрипт [index.py](task4/index.py)
  
- основное отсекание нерелеватного ответа через retrieval без участия LLM
  - если и нашлось (нерелевантное), то LLM так же отсечет
  
- проверка через REST API
  - пример успешных диалогов
    - [rest-api.success.txt](task4/rest-api.success.txt)
  - пример, когда бот не знает, без LLM
    - [rest-api.not_known.txt](task4/rest-api.not_known.txt)

- проверка через телеграм бот
  - ![img.png](task4/answer_from_tg/img.png)
  - ![img_1.png](task4/answer_from_tg/img_1.png)
  - ![img_2.png](task4/answer_from_tg/img_2.png)
  - 