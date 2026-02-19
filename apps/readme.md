### Запуск 
- установить зависимости
```
# версия пытона 3.10 x64
python -m venv .venv 
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\rag_service\requirements.txt
```
- в текущей версии сначала индексируем базу знаний локально
  - python index.py

- запуск докера
  - добавить значения в .env по примеру из .env_example
  - в консоли добавить токен-переменную для тг_бота
    - $env:TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
  - запуск контейнеров
    - docker compose up --build -d

- проверка 
  - http://localhost:8000/health
  - через телеграм бота
