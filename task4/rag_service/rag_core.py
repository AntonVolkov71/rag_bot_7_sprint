from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from .prompt_templates import compose_prompt


@dataclass
class RetrievedChunk:
    idx: int
    text: str
    source: str
    category: str
    entity: str


class RagEngine:
    def __init__(
        self,
        persist_dir: str = "vector_store_chroma",
        collection_name: str = "folklore_kb",
        entities_file: str = "entities.json",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.entities_path = self.persist_dir / entities_file

        self.embeddings = HuggingFaceEmbeddings(model_name=model_name)

        # Важно: НЕ пересоздаём индекс, а открываем persist_directory
        self.vectordb = Chroma(
            collection_name=self.collection_name,
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
        )

        self.entities = self._load_entities()

    def _load_entities(self) -> list[str]:
        if self.entities_path.exists():
            try:
                data = json.loads(self.entities_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return sorted([str(x) for x in data], key=len, reverse=True)
            except Exception:
                pass
        return []

    def _smart_search(self, query: str, k: int = 3):
        q = (query or "").lower()
        matched = None
        for e in self.entities:
            if e.lower() in q:
                matched = e
                break

        if matched:
            docs = self.vectordb.max_marginal_relevance_search(
                query, k=k, fetch_k=25, filter={"entity": matched}
            )
            return docs, matched

        docs = self.vectordb.max_marginal_relevance_search(query, k=k, fetch_k=25)
        return docs, None

    def retrieve(self, question: str, k: int = 3):
        docs, matched = self._smart_search(question, k=k)
        out: list[RetrievedChunk] = []
        for i, d in enumerate(docs, 1):
            meta: dict[str, Any] = d.metadata or {}
            text = (d.page_content or "").strip()


            out.append(
                RetrievedChunk(
                    idx=i,
                    text=text,
                    source=str(meta.get("source", "")),
                    category=str(meta.get("category", "")),
                    entity=str(meta.get("entity", "")),
                )
            )
        return out, matched

    def build_context_block(self, chunks: list[RetrievedChunk], max_chars: int = 4500) -> str:
        parts: list[str] = []
        total = 0
        for c in chunks:
            header = f"[{c.idx}] source={c.source} category={c.category} entity={c.entity}\n"
            body = c.text.strip()
            block = header + body + "\n\n"
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        return "".join(parts).strip()

    def should_answer_idk(self, chunks, matched_entity) -> bool:
        # если не нашли точную сущность — считаем, что ответа в базе нет
        if matched_entity is None:
            return True
        return len(chunks) == 0

    def build_prompt(self, question: str, chunks: list[RetrievedChunk]) -> str:
        context_block = self.build_context_block(chunks)
        return compose_prompt(question=question, context_block=context_block)

    def answer(self, prompt, sources):
        pass
