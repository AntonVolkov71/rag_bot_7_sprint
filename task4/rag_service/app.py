from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from .rag_core import RagEngine
from .llm_yandex import YandexGptClient



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("rag")

app = FastAPI(title="RAG Service", version="0.1")

# инициализация эмбендинга
engine = RagEngine(
    persist_dir="vector_store_chroma",
    collection_name="folklore_kb",
)

LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() in ("1", "true", "yes", "on")

log.info("LLM_ENABLED=%s", LLM_ENABLED)
log.info("ENV folder_id=%r token_present=%s",
         os.getenv("YANDEX_FOLDER_ID"),
         bool(os.getenv("YANDEX_IAM_TOKEN")))

llm = None
if LLM_ENABLED:
    llm = YandexGptClient()
else:
    log.warning("LLM is disabled (LLM_ENABLED=false). Returning prompt-based stub answers.")

# валидация запроса
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(default=3, ge=1, le=10)


class SourceItem(BaseModel):
    idx: int
    source: str
    category: str
    entity: str

# тип ответа
class AskResponse(BaseModel):
    found: bool
    answer: str
    sources: list[SourceItem]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    log.info("ASK question=%r k=%s", req.question, req.k)
    chunks, matched  = engine.retrieve(req.question, k=req.k)

    log.info("Matched entity: %r (entities_loaded=%s)", matched, len(engine.entities))

    # если чанки пустые отдаем “не знаю” на основе ответа из векторной БД
    if engine.should_answer_idk(chunks, matched):
        return AskResponse(
            found=False,
            answer=(
                "Я не знаю: в базе нет подтверждений по этому вопросу.\n"
                f"Вопрос пользователя: «{req.question}»\n"
                "Ответ сформирован без использования LLM."
            ),
            sources=[],
        )

    # генерим промпт
    prompt = engine.build_prompt(req.question, chunks)

    # логируем источники
    for c in chunks:
        log.info("Chunk[%s] entity=%r source=%r", c.idx, c.entity, c.source)

    log.info("Prompt length=%s chars", len(prompt))
    log.info("Prompt preview:\n%s", prompt[:800]) # для лога сократим ответ

    sources = [
        SourceItem(idx=c.idx, source=c.source, category=c.category, entity=c.entity)
        for c in chunks
    ]

    if not LLM_ENABLED:
        # если LLM выключен
        return AskResponse(
            found=True,
            answer="LLM отключён (LLM_ENABLED=false). Retrieval работает, промпт сформирован.",
            sources=sources,
        )

    # проводим ответ через LLM
    try:
        answer = llm.generate(prompt)
    except Exception as e:
        log.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=str(e))

    return AskResponse(found=True, answer=answer, sources=sources)
