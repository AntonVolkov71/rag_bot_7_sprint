from __future__ import annotations

import logging
import os
from pathlib import Path
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

def get_active_persist_dir() -> Path:
    base_dir = Path(__file__).resolve().parents[2]  # ...\7\
    pointer = base_dir / "vector_store_chroma_active.txt"

    default_dir = base_dir / "vector_store_chroma_blue"

    if not pointer.exists():
        return default_dir.resolve()

    name = pointer.read_text(encoding="utf-8").strip()
    if not name:
        return default_dir.resolve()

    p = Path(name)
    if not p.is_absolute():
        p = base_dir / p

    return p.resolve()


def make_engine() -> RagEngine:
    persist_dir = get_active_persist_dir()
    return RagEngine(
        persist_dir=str(persist_dir),
        collection_name="folklore_kb",
    )

# инициализация эмбендинга
engine = make_engine()

def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")

LLM_ENABLED = env_bool("LLM_ENABLED", True)
PREPROMPTED = env_bool("PREPROMPTED", True)
POSTFILTERED = env_bool("POSTFILTERED", True)
SANITIZED = env_bool("SANITIZED", True)


log.info("LLM_ENABLED=%s", LLM_ENABLED)
log.info("PREPROMPTED=%s", PREPROMPTED)
log.info("POSTFILTERED=%s", POSTFILTERED)

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


class AskResponse(BaseModel):
    found: bool
    answer: str
    sources: list[SourceItem]

MAINTENANCE = False

@app.post("/maintenance_on")
def maintenance_on():
    global MAINTENANCE
    MAINTENANCE = True
    return {"status": "maintenance_on"}

@app.post("/maintenance_off")
def maintenance_off():
    global MAINTENANCE
    MAINTENANCE = False
    return {"status": "maintenance_off"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reload_db")
def reload_engine():
    global engine

    engine = make_engine()
    log.info("RAG engine reloaded | entities_loaded=%s | persist_dir=%s",
             len(engine.entities), str(engine.persist_dir))

    return {
        "status": "reloaded",
        "entities_loaded": len(engine.entities),
        "persist_dir": str(engine.persist_dir),
    }

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    log.info("ASK question=%r k=%s", req.question, req.k)
    if MAINTENANCE:
        raise HTTPException(status_code=503, detail="Index is updating, try later")

    chunks, matched  = engine.retrieve(req.question, k=req.k)

    if SANITIZED:
        changes = engine.sanitize_chunks(chunks)
        log.info("SANITIZED: applied to %s chunks | changes=%s | question=%r", len(chunks), changes, req.question)

        if changes > 0:
            log.warning(
                "SECURITY EVENT | sanitize triggered | changes=%s | question=%r",
                changes,
                req.question,
            )

    blocked_count = 0

    if POSTFILTERED:
        before = len(chunks)
        chunks = engine.post_filter_chunks(chunks)
        blocked_count = before - len(chunks)

        log.info("POSTFILTERED: %s -> %s", before, len(chunks))

        if blocked_count > 0:
            log.warning(
                "SECURITY EVENT | post-filter triggered | blocked=%s | question=%r",
                blocked_count,
                req.question,
            )

    log.info("Matched entity: %r (entities_loaded=%s)", matched, len(engine.entities))

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
    prompt = engine.build_prompt(req.question, chunks, use_system=PREPROMPTED)

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
