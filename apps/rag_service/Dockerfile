FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    python -m pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    python -m pip install -r requirements.txt

# Кладём код как пакет: /app/rag_service/...
COPY . /app/rag_service

EXPOSE 8000
CMD ["uvicorn", "rag_service.app:app", "--host", "0.0.0.0", "--port", "8000"]