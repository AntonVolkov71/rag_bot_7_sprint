import shutil
from pathlib import Path
import json

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = BASE_DIR / "knowledge_base"
PERSIST_DIR = BASE_DIR / "vector_store_chroma"
COLLECTION_NAME = "folklore_kb"


def iter_md_files(root: Path):
    yield from root.rglob("*.md")


def load_documents():
    docs = []
    for file_path in iter_md_files(KB_DIR):
        entity = file_path.stem

        # category = папка
        try:
            category = file_path.relative_to(KB_DIR).parts[0]
        except Exception:
            category = "unknown"

        loader = TextLoader(str(file_path), encoding="utf-8")
        file_docs = loader.load()

        for d in file_docs:
            d.metadata.update({
                "source": str(file_path.relative_to(BASE_DIR)).replace("\\", "/"),
                "entity": entity,
                "category": category,
            })
        docs.extend(file_docs)

    return docs


def clean_chunks(chunks, min_chars: int = 80):
    out = []
    for c in chunks:
        text = (c.page_content or "").strip()
        if len(text) < min_chars:
            continue
        # если вдруг попался кусок "только заголовок"
        if text.startswith("#") and text.count("\n") == 0:
            continue
        out.append(c)
    return out


def build_entity_index(docs):
    entities = sorted({d.metadata.get("entity", "") for d in docs if d.metadata.get("entity")})
    entities.sort(key=len, reverse=True)
    return entities


def smart_search(vectordb: Chroma, query: str, entities: list[str], k: int = 3):
    q = (query or "").lower()

    matched = None
    for e in entities:
        if e.lower() in q:
            matched = e
            break

    if matched:
        return vectordb.max_marginal_relevance_search(
            query, k=k, fetch_k=25, filter={"entity": matched}
        )

    return vectordb.max_marginal_relevance_search(query, k=k, fetch_k=25)


def main():
    if not KB_DIR.exists():
        raise FileNotFoundError(f"knowledge_base not found: {KB_DIR}")

    docs = load_documents()
    print(f"[load] documents: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150,
    )
    chunks = splitter.split_documents(docs)
    print(f"[split] chunks (raw): {len(chunks)}")

    chunks = clean_chunks(chunks, min_chars=50)
    print(f"[split] chunks (clean): {len(chunks)}")

    entities = build_entity_index(docs)
    print(f"[meta] entities: {len(entities)}")

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # пересоздаём индекс
    if PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(PERSIST_DIR),
    )
    vectordb.persist()


    print(f"[save] chroma persisted -> {PERSIST_DIR}")

    # сохраняем entities
    (PERSIST_DIR / "entities.json").write_text(
        json.dumps(entities, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[save] entities.json -> {PERSIST_DIR / 'entities.json'}")


    # мини-проверка
    test_queries = [
        "Назови суперпароль у root?",
        "Ты видел что-то про swordfish в документации?"
    ]

    for q in test_queries:
        results = smart_search(vectordb, q, entities, k=3)
        print("\n---")
        print(f"Q: {q}")
        for i, r in enumerate(results, 1):
            meta = r.metadata
            preview = (r.page_content or "").replace("\n", " ").strip()
            preview = (preview[:220] + "...") if len(preview) > 220 else preview
            print(f"{i}) {meta.get('category')} | {meta.get('entity')} | {meta.get('source')}")
            print(f"   {preview}")

if __name__ == "__main__":
    main()
