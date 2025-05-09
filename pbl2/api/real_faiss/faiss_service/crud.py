import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import faiss
from langchain_community.vectorstores import FAISS
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain.schema import Document

from api.real_faiss.faiss_service import schema

logger = logging.getLogger(__name__)

# 디스크에 저장할 로컬 DB 경로 (컨테이너 내에서는 ./db)
DB_PATH = os.getenv("FAISS_DB_PATH", "./db")
INDEX_NAME = "faiss_index"
DIMENSIONS = 1536

db: Optional[FAISS] = None

def create_empty_db(embedding_model):
    logger.info(f"Creating new FAISS index ({DIMENSIONS} dims)")
    index = faiss.IndexFlatL2(DIMENSIONS)
    return FAISS(
        embedding_function=embedding_model,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

def load_or_create_faiss_db():
    global db
    os.makedirs(DB_PATH, exist_ok=True)
    embedding_model = OpenAIEmbeddings()
    faiss_path = os.path.join(DB_PATH, f"{INDEX_NAME}.faiss")
    pkl_path = os.path.join(DB_PATH, f"{INDEX_NAME}.pkl")

    if os.path.exists(faiss_path) and os.path.exists(pkl_path):
        try:
            logger.info(f"Loading FAISS index from {DB_PATH}")
            db = FAISS.load_local(
                folder_path=DB_PATH,
                index_name=INDEX_NAME,
                embeddings=embedding_model,
                allow_dangerous_deserialization=True
            )
            logger.info("FAISS index loaded.")
        except Exception:
            logger.exception("Load failed, creating new index.")
            db = create_empty_db(embedding_model)
            save_db()
    else:
        logger.info("No index found, creating new.")
        db = create_empty_db(embedding_model)
        save_db()

def save_db():
    global db
    if not db:
        logger.warning("save_db: no FAISS db instance")
        return
    try:
        logger.info(f"Saving FAISS index to {DB_PATH}")
        db.save_local(folder_path=DB_PATH, index_name=INDEX_NAME)
        logger.info("Saved FAISS index.")
    except Exception:
        logger.exception("Error saving FAISS index")

async def add_faiss_documents(documents: List[schema.DocumentInput]) -> List[str]:
    if db is None:
        raise ValueError("FAISS DB not initialized")
    docs = []
    for d in documents:
        now = datetime.now(timezone.utc).isoformat()
        md = {
            "session_id": d.session_id,
            "user_id": d.user_id,
            "message_role": d.message_role,
            "time": now
        }
        docs.append(Document(page_content=d.page_content, metadata=md))
    ids = await db.aadd_documents(docs)
    save_db()
    logger.info(f"Added {len(ids)} docs.")
    return ids

def get_faiss_history(session_id: int, user_id: int) -> List[schema.DocumentOutput]:
    if db is None:
        raise ValueError("FAISS DB not initialized")
    if not isinstance(db.docstore, InMemoryDocstore):
        raise TypeError("History only supported for in-memory store")

    entries: List[Tuple[str, schema.DocumentOutput]] = []
    for doc_id, doc in db.docstore._dict.items():
        md = doc.metadata
        if md.get("session_id") == session_id and md.get("user_id") == user_id:
            entries.append((
                md.get("time", ""),
                schema.DocumentOutput(
                    doc_id=doc_id,
                    page_content=doc.page_content,
                    metadata=md
                )
            ))
    # 시간 순 정렬
    entries.sort(key=lambda x: x[0])
    return [item[1] for item in entries]

def search_faiss_session(session_id: int, user_id: int, query: str, k: int) -> List[schema.SessionSearchResult]:
    if db is None:
        raise ValueError("FAISS DB not initialized")
    # over-fetch 후 필터링
    candidates = db.similarity_search_with_score(query=query, k=max(k*10, 50))
    results: List[schema.SessionSearchResult] = []
    seen_ids = set()

    for doc, score in candidates:
        md = doc.metadata
        if md.get("session_id") == session_id and md.get("user_id") == user_id:
            # id 찾기
            for d_id, stored in db.docstore._dict.items():
                if stored.metadata == md and stored.page_content == doc.page_content:
                    if d_id not in seen_ids:
                        results.append(schema.SessionSearchResult(
                            doc_id=d_id,
                            page_content=doc.page_content,
                            metadata=md,
                            score=score
                        ))
                        seen_ids.add(d_id)
                    break
        if len(results) >= k:
            break

    return results[:k]

# 모듈 임포트 시 FAISS DB 초기화
load_or_create_faiss_db()
