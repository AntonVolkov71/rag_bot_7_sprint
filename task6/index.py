import hashlib
import json
import logging
import os
import shutil
import time
import urllib.request

from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Dict, Tuple, Optional

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

BASE_DIR = Path(__file__).resolve().parent.parent
BUILDS_ROOT = BASE_DIR / "vector_store_chroma_builds"

KB_DIR = BASE_DIR / "knowledge_base"
COLLECTION_NAME = "folklore_kb"

ACTIVE_POINTER = BASE_DIR / "vector_store_chroma_active.txt"

MANIFEST_NAME = "manifest.json"
ENTITIES_NAME = "entities.json"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MIN_CHARS = 50

LOG_PATH = Path(__file__).resolve().parent / "index_update.log"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("kb_index_update")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


logger = setup_logger()

def choose_build_dir_unique() -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (BUILDS_ROOT / f"build-{ts}").resolve()


def switch_active_dir(new_active: Path) -> None:
    tmp = ACTIVE_POINTER.with_suffix(".tmp")
    tmp.write_text(str(new_active.resolve()), encoding="utf-8")
    tmp.replace(ACTIVE_POINTER)
    logger.info("[active] -> %s", new_active)


def _post(url_env: str, label: str, timeout: int = 5) -> None:
    url = os.getenv(url_env)
    if not url:
        logger.info("[notify] %s not set -> skip", url_env)
        return

    if "://" not in url:
        url = "http://" + url

    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            logger.info("[notify] %s ok | status=%s | body=%s", label, resp.status, body[:300])
    except Exception as e:
        logger.warning("[notify] %s failed (ignored): %s", label, e)


def maintenance_on() -> None:
    _post("RAG_MAINTENANCE_ON_URL", "maintenance_on", timeout=3)


def maintenance_off() -> None:
    _post("RAG_MAINTENANCE_OFF_URL", "maintenance_off", timeout=3)


def reload_db() -> None:
    _post("RAG_RELOAD_URL", "reload_db", timeout=20)


def iter_md_files(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.md")


def rel_source(file_path: Path) -> str:
    return str(file_path.relative_to(BASE_DIR)).replace("\\", "/")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_documents_for_files(file_paths: List[Path]) -> List:
    docs = []
    for file_path in file_paths:
        entity = file_path.stem
        try:
            category = file_path.relative_to(KB_DIR).parts[0]
        except Exception:
            category = "unknown"

        loader = TextLoader(str(file_path), encoding="utf-8")
        file_docs = loader.load()

        for d in file_docs:
            d.metadata.update(
                {
                    "source": rel_source(file_path),
                    "entity": entity,
                    "category": category,
                }
            )
        docs.extend(file_docs)
    return docs


def clean_chunks(chunks, min_chars: int = 80):
    out = []
    for c in chunks:
        text = (c.page_content or "").strip()
        if len(text) < min_chars:
            continue
        if text.startswith("#") and text.count("\n") == 0:
            continue
        out.append(c)
    return out


def build_entity_index(docs) -> List[str]:
    entities = sorted({d.metadata.get("entity", "") for d in docs if d.metadata.get("entity")})
    entities.sort(key=len, reverse=True)
    return entities


def read_manifest(persist_dir: Path) -> Dict[str, Dict]:
    mp = persist_dir / MANIFEST_NAME
    if not mp.exists():
        return {}
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_manifest(persist_dir: Path, manifest: Dict[str, Dict]) -> None:
    persist_dir.mkdir(parents=True, exist_ok=True)
    (persist_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_entities(persist_dir: Path, entities: List[str]) -> None:
    persist_dir.mkdir(parents=True, exist_ok=True)
    (persist_dir / ENTITIES_NAME).write_text(
        json.dumps(entities, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def diff_kb_vs_manifest(
    kb_files: List[Path], manifest: Dict[str, Dict]
) -> Tuple[List[Path], List[Path], List[str], Dict[str, Dict]]:
    new_manifest: Dict[str, Dict] = {}
    kb_by_source: Dict[str, Path] = {}

    for p in kb_files:
        src = rel_source(p)
        kb_by_source[src] = p
        new_manifest[src] = {
            "sha256": sha256_file(p),
            "mtime": p.stat().st_mtime,
            "size": p.stat().st_size,
        }

    old_sources = set(manifest.keys())
    new_sources = set(new_manifest.keys())

    deleted_sources = sorted(list(old_sources - new_sources))
    added_sources = sorted(list(new_sources - old_sources))
    common_sources = sorted(list(old_sources & new_sources))

    added_files = [kb_by_source[s] for s in added_sources]
    changed_files = []
    for s in common_sources:
        old_hash = (manifest.get(s) or {}).get("sha256")
        new_hash = (new_manifest.get(s) or {}).get("sha256")
        if old_hash != new_hash:
            changed_files.append(kb_by_source[s])

    return added_files, changed_files, deleted_sources, new_manifest


def get_vectordb(embeddings: HuggingFaceEmbeddings, persist_dir: Path) -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
    )


def safe_delete_by_source(vectordb: Chroma, source_value: str) -> None:
    if hasattr(vectordb, "delete"):
        try:
            vectordb.delete(where={"source": source_value})
            return
        except Exception:
            pass

    try:
        col = getattr(vectordb, "_collection", None)
        if col is not None and hasattr(col, "delete"):
            col.delete(where={"source": source_value})
            return
    except Exception:
        pass

    raise RuntimeError("Не удалось удалить документы из Chroma по where={'source': ...}")


def chunk_docs(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    chunks = clean_chunks(chunks, min_chars=MIN_CHARS)
    return chunks


def bootstrap_index(embeddings: HuggingFaceEmbeddings, persist_dir: Path) -> None:
    logger.info("BOOTSTRAP: building index from scratch")

    kb_files = list(iter_md_files(KB_DIR))
    docs = load_documents_for_files(kb_files)
    logger.info("[load] documents: %s", len(docs))

    chunks = chunk_docs(docs)
    logger.info("[split] chunks (clean): %s", len(chunks))

    entities = build_entity_index(docs)
    logger.info("[meta] entities: %s", len(entities))

    persist_dir.mkdir(parents=True, exist_ok=True)
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
    )
    vectordb.persist()
    logger.info("[save] chroma persisted -> %s", persist_dir)

    new_manifest: Dict[str, Dict] = {}
    for p in kb_files:
        src = rel_source(p)
        new_manifest[src] = {
            "sha256": sha256_file(p),
            "mtime": p.stat().st_mtime,
            "size": p.stat().st_size,
        }

    write_manifest(persist_dir, new_manifest)
    logger.info("[save] %s -> %s", MANIFEST_NAME, persist_dir / MANIFEST_NAME)

    write_entities(persist_dir, entities)
    logger.info("[save] %s -> %s", ENTITIES_NAME, persist_dir / ENTITIES_NAME)


def update_index(embeddings: HuggingFaceEmbeddings, persist_dir: Path) -> None:
    manifest = read_manifest(persist_dir)
    if not manifest:
        bootstrap_index(embeddings, persist_dir)
        return

    kb_files = list(iter_md_files(KB_DIR))
    added_files, changed_files, deleted_sources, new_manifest = diff_kb_vs_manifest(kb_files, manifest)

    logger.info("UPDATE: added=%s changed=%s deleted=%s", len(added_files), len(changed_files), len(deleted_sources))

    vectordb = get_vectordb(embeddings, persist_dir)

    to_delete_sources = deleted_sources + [rel_source(p) for p in changed_files]
    for src in to_delete_sources:
        try:
            safe_delete_by_source(vectordb, src)
            logger.info("[delete] source=%s", src)
        except Exception as e:
            logger.error("[delete][ERR] source=%s -> %s", src, e)

    to_add_files = added_files + changed_files
    if to_add_files:
        docs = load_documents_for_files(to_add_files)
        chunks = chunk_docs(docs)
        logger.info("[add] docs=%s chunks=%s", len(docs), len(chunks))
        if chunks:
            vectordb.add_documents(chunks)

    vectordb.persist()
    logger.info("[save] chroma persisted -> %s", persist_dir)

    all_docs = load_documents_for_files(kb_files)
    entities = build_entity_index(all_docs)
    write_entities(persist_dir, entities)
    logger.info("[save] %s -> %s", ENTITIES_NAME, persist_dir / ENTITIES_NAME)

    write_manifest(persist_dir, new_manifest)
    logger.info("[save] %s -> %s", MANIFEST_NAME, persist_dir / MANIFEST_NAME)

def prepare_build_dir_unique(build_dir: Path, active_dir: Path) -> None:
    build_dir.parent.mkdir(parents=True, exist_ok=True)
    if active_dir.exists() and any(active_dir.iterdir()):
        shutil.copytree(active_dir, build_dir)
    else:
        build_dir.mkdir(parents=True, exist_ok=True)

def read_active_dir() -> Optional[Path]:
    if not ACTIVE_POINTER.exists():
        return None

    raw = ACTIVE_POINTER.read_text(encoding="utf-8").strip()
    if not raw:
        return None

    p = Path(raw)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p.resolve()


def main():
    started = datetime.now()
    logger.info("=" * 80)
    logger.info("Index update started | KB_DIR=%s", KB_DIR)

    if not KB_DIR.exists():
        raise FileNotFoundError(f"knowledge_base not found: {KB_DIR}")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    active_dir = read_active_dir()
    build_dir = choose_build_dir_unique()
    logger.info("[bluegreen] active=%s build=%s", active_dir, build_dir)

    maintenance_on()
    time.sleep(2)

    try:
        prepare_build_dir_unique(build_dir, active_dir)

        manifest_path = build_dir / MANIFEST_NAME
        if not manifest_path.exists():
            bootstrap_index(embeddings, build_dir)
        else:
            update_index(embeddings, build_dir)

        time.sleep(1)

        switch_active_dir(build_dir)
        reload_db()

    finally:
        maintenance_off()

    finished = datetime.now()
    logger.info("Index update finished | elapsed=%.2fs", (finished - started).total_seconds())


if __name__ == "__main__":
    main()
