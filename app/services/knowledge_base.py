# -*- coding: utf-8 -*-
"""
Knowledge Base Service - ChromaDB vector store with OpenAI embeddings.
Provides document storage, embedding generation, and semantic search.
"""
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import chromadb

from app.config import get_settings
from app.services.chunker import chunk_text, count_tokens, extract_pages_from_chunk
from app.services.document_processor import extract_text, clean_text

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """Manages document ingestion, embedding, and semantic search via ChromaDB."""

    def __init__(self):
        self.settings = get_settings()

        # ChromaDB persistent storage next to the app
        persist_dir = str(self.settings.DATA_DIR / "chromadb")
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=persist_dir,
        )
        self._collection = self._client.get_or_create_collection(
            name=self.settings.RAG_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # OpenAI embedding endpoint (direct, proxy doesn't support /v1/embeddings)
        self._embed_url = "https://api.openai.com/v1/embeddings"
        self._api_key = self.settings.OPENAI_API_KEY

        logger.info(
            f"KnowledgeBase initialized: collection='{self.settings.RAG_COLLECTION_NAME}', "
            f"chunks={self._collection.count()}"
        )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API for a list of texts."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.EMBEDDING_MODEL,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._embed_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Sort by index to guarantee order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    # ------------------------------------------------------------------
    # Document ingestion
    # ------------------------------------------------------------------

    async def add_document(
        self,
        file_path: str,
        filename: str,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a file: extract text, chunk, embed, store in ChromaDB.

        Returns dict with document_id, chunk_count, token_count.
        """
        # Extract and clean text
        raw_text = extract_text(file_path, content_type)
        text = clean_text(raw_text)

        if not text:
            raise ValueError("No text could be extracted from the file")

        total_tokens = count_tokens(text)

        # Generate a stable document id from content hash
        doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Chunk
        chunks = chunk_text(
            text,
            chunk_size=self.settings.RAG_CHUNK_SIZE,
            chunk_overlap=self.settings.RAG_CHUNK_OVERLAP,
        )

        if not chunks:
            raise ValueError("Text produced zero chunks")

        # Embed in batches of 50
        all_embeddings: List[List[float]] = []
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = await self._get_embeddings(batch)
            all_embeddings.extend(embeddings)

        # Prepare ids and metadata (extract page numbers from [PAGE:N] markers)
        # Propagate page numbers: if a chunk has no [PAGE:N] marker,
        # inherit the last known page from the previous chunk
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        last_known_page = ""
        metadatas = []
        for i, chunk in enumerate(chunks):
            pages = extract_pages_from_chunk(chunk)
            if pages:
                last_known_page = pages.split("-")[-1]  # take last page number
            elif last_known_page:
                pages = last_known_page  # inherit from previous chunk
            metadatas.append({
                "document_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "added_at": int(time.time()),
                "pages": pages,
            })

        # Upsert into ChromaDB
        self._collection.upsert(
            ids=ids,
            embeddings=all_embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info(
            f"Added document '{filename}': id={doc_id}, "
            f"chunks={len(chunks)}, tokens={total_tokens}"
        )

        return {
            "document_id": doc_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "token_count": total_tokens,
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_relevance: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over the knowledge base.

        Uses multi-query strategy: searches with both the original query
        and a keyword-enriched version, then merges and deduplicates results.
        Filters out low-quality chunks (TOC pages, very short text).

        Returns list of dicts with keys: text, score, filename, chunk_index.
        """
        if self._collection.count() == 0:
            return []

        top_k = top_k or self.settings.RAG_TOP_K
        min_relevance = min_relevance or self.settings.RAG_MIN_RELEVANCE
        fetch_k = min(top_k * 20, self._collection.count())

        # Build query variants: original + keyword-enriched
        queries = [query]
        expanded = self._expand_query(query)
        if expanded != query:
            queries.append(expanded)

        # Get embeddings for all queries at once
        query_embeddings = await self._get_embeddings(queries)

        # Collect candidates from all queries, keep best score per chunk
        candidates: Dict[str, Dict[str, Any]] = {}  # keyed by chunk id

        for q_emb in query_embeddings:
            results = self._collection.query(
                query_embeddings=[q_emb],
                n_results=fetch_k,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results["documents"]:
                continue

            for doc, meta, dist, chunk_id in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
                results["ids"][0],
            ):
                score = 1.0 - (dist / 2.0)
                if score < min_relevance:
                    continue
                if self._is_low_quality_chunk(doc):
                    continue

                # Keep best score if chunk appears in multiple queries
                if chunk_id not in candidates or score > candidates[chunk_id]["score"]:
                    candidates[chunk_id] = {
                        "text": doc,
                        "score": round(score, 4),
                        "filename": meta.get("filename", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "document_id": meta.get("document_id", ""),
                        "pages": meta.get("pages", ""),
                    }

        # Filter by document matching car brand/model in query
        query_lower = query.lower()
        car_keywords = self._extract_car_keywords(query_lower)
        if car_keywords:
            # Check if any candidates match the car keywords
            matched = {k: v for k, v in candidates.items()
                       if any(kw in v["filename"].lower() for kw in car_keywords)}
            if matched:
                # Use only matching documents
                candidates = matched
                logger.info(f"RAG filtered to {len(candidates)} chunks from matching documents")

        # Sort by score descending, return top_k
        hits = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)
        return hits[:top_k]

    @staticmethod
    def _expand_query(query: str) -> str:
        """Enrich query with synonyms/related terms for better retrieval."""
        expansions = {
            "буксир": "буксировка буксировочная проушина транспортировка эвакуатор",
            "масло": "моторное масло замена масла спецификация вязкость уровень",
            "фильтр": "фильтр замена фильтра воздушный масляный салонный топливный",
            "тормоз": "тормозная система колодки тормозная жидкость диски суппорт",
            "аккумулятор": "аккумуляторная батарея зарядка запуск клемма",
            "предохранител": "предохранитель блок предохранителей замена реле",
            "шин": "шины давление в шинах колесные диски замена колесо",
            "свет": "фары освещение лампы замена ламп ближний дальний",
            "двигател": "двигатель мотор ДВС запуск цилиндр блок",
            "кондиционер": "кондиционер климат-контроль хладагент фильтр салон",
            "оборот": "обороты холостой ход дроссель заслонка ресивер подсос воздух впуск регулятор",
            "холост": "холостой ход обороты дроссель регулятор ресивер подсос воздуха",
            "дроссел": "дроссельная заслонка дроссельный узел регулятор холостого хода ресивер",
            "троит": "троит цилиндр зажигание свеча катушка компрессия",
            "заглох": "глохнет заглох остановка двигатель холостой ход топливо",
            "стук": "стук шум двигатель подшипник клапан поршень",
            "перегрев": "перегрев температура охлаждение радиатор термостат помпа антифриз",
            "подвеск": "подвеска амортизатор стойка рычаг шаровая сайлентблок стабилизатор",
            "сцеплен": "сцепление диск корзина выжимной педаль привод",
            "коробк": "коробка передач КПП МКПП АКПП переключение масло",
            "руле": "рулевое управление руль рейка наконечник тяга насос ГУР",
            "генератор": "генератор зарядка ремень напряжение аккумулятор",
            "стартер": "стартер запуск втягивающее реле бендикс",
            "датчик": "датчик сенсор проверка замена электрика",
        }
        query_lower = query.lower()
        extra_terms = []
        for keyword, synonyms in expansions.items():
            if keyword in query_lower:
                extra_terms.append(synonyms)
        if extra_terms:
            return query + " " + " ".join(extra_terms)
        return query

    @staticmethod
    def _extract_car_keywords(query: str) -> List[str]:
        """Extract car brand/model keywords from query for document matching."""
        brands = {
            "voyah": ["voyah"], "воях": ["voyah"],
            "hyundai": ["hyundai", "getz", "solaris", "tucson", "creta", "santa"],
            "хендай": ["hyundai"], "хёндай": ["hyundai"], "хундай": ["hyundai"],
            "гетц": ["getz"], "солярис": ["solaris"], "туксон": ["tucson"],
            "крета": ["creta"], "санта": ["santa"],
            "kia": ["kia"], "киа": ["kia"],
            "рио": ["rio"], "сид": ["ceed"], "спортейдж": ["sportage"],
            "toyota": ["toyota"], "тойота": ["toyota"],
            "камри": ["camry"], "королла": ["corolla"], "рав4": ["rav4"],
            "bmw": ["bmw"], "бмв": ["bmw"],
            "mercedes": ["mercedes"], "мерседес": ["mercedes"],
            "audi": ["audi"], "ауди": ["audi"],
            "volkswagen": ["volkswagen", "vw"], "фольксваген": ["volkswagen", "vw"],
            "nissan": ["nissan"], "ниссан": ["nissan"],
            "honda": ["honda"], "хонда": ["honda"],
            "ford": ["ford"], "форд": ["ford"],
            "chevrolet": ["chevrolet"], "шевроле": ["chevrolet"],
            "geely": ["geely"], "джили": ["geely"],
            "changan": ["changan"], "чанган": ["changan"],
            "haval": ["haval"], "хавал": ["haval"],
            "zeekr": ["zeekr"], "зикр": ["zeekr"],
            "lada": ["lada", "vaz"], "лада": ["lada", "vaz"], "ваз": ["vaz", "lada"],
        }
        found = []
        for keyword, file_terms in brands.items():
            if keyword in query:
                found.extend(file_terms)
        return list(set(found))

    @staticmethod
    def _is_low_quality_chunk(text: str) -> bool:
        """Filter out table-of-contents pages, headers, and very short chunks."""
        # Too short to be useful
        if len(text.strip()) < 100:
            return True
        # Table of contents: lines with dots as separators (". . ." or "....")
        dot_lines = sum(1 for line in text.split("\n")
                        if ". . ." in line or "...." in line or "…" in line)
        total_lines = max(len(text.split("\n")), 1)
        if dot_lines > 3 and dot_lines / total_lines > 0.2:
            return True
        return False

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def get_documents(self) -> List[Dict[str, Any]]:
        """List all unique documents in the collection."""
        if self._collection.count() == 0:
            return []

        all_meta = self._collection.get(include=["metadatas"])
        docs: Dict[str, Dict[str, Any]] = {}
        for meta in all_meta["metadatas"]:
            doc_id = meta.get("document_id", "")
            if doc_id not in docs:
                docs[doc_id] = {
                    "document_id": doc_id,
                    "filename": meta.get("filename", ""),
                    "total_chunks": meta.get("total_chunks", 0),
                    "added_at": meta.get("added_at", 0),
                }
        return list(docs.values())

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific document."""
        results = self._collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"],
        )
        if not results or not results["ids"]:
            return None

        meta = results["metadatas"][0]
        return {
            "document_id": document_id,
            "filename": meta.get("filename", ""),
            "total_chunks": meta.get("total_chunks", 0),
            "added_at": meta.get("added_at", 0),
            "chunk_count": len(results["ids"]),
            "chunks": [
                {"index": m.get("chunk_index", 0), "text": d}
                for m, d in zip(results["metadatas"], results["documents"])
            ],
        }

    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks belonging to a document."""
        results = self._collection.get(
            where={"document_id": document_id},
        )
        if not results or not results["ids"]:
            return False

        self._collection.delete(ids=results["ids"])
        logger.info(f"Deleted document {document_id}: {len(results['ids'])} chunks removed")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        total_chunks = self._collection.count()
        documents = self.get_documents()
        return {
            "total_chunks": total_chunks,
            "total_documents": len(documents),
            "collection_name": self.settings.RAG_COLLECTION_NAME,
            "documents": documents,
        }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_kb_service: Optional[KnowledgeBaseService] = None


def get_kb_service() -> KnowledgeBaseService:
    """Get knowledge base service singleton."""
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service
