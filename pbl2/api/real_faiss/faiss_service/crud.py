import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Set

import faiss
from langchain_community.vectorstores import FAISS
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain.schema import Document

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from . import schema
from api.models.ORM import Session as OrmSession, Topic as OrmTopic

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("FAISS_DB_PATH", "./db")
INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "faiss_index")
DIMENSIONS = 1536
db: Optional[FAISS] = None

def create_empty_db(embedding_model: OpenAIEmbeddings) -> FAISS:
    index = faiss.IndexFlatL2(DIMENSIONS)
    return FAISS(
        embedding_function=embedding_model,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

def load_or_create_faiss_db():
    global db
    if db is not None:
        return
    os.makedirs(DB_PATH, exist_ok=True)
    try:
        embedding_model = OpenAIEmbeddings()
    except Exception as e:
        raise ValueError(f"OpenAIEmbeddings initialization failed: {e}")

    faiss_path = os.path.join(DB_PATH, f"{INDEX_NAME}.faiss")
    pkl_path = os.path.join(DB_PATH, f"{INDEX_NAME}.pkl")

    if os.path.exists(faiss_path) and os.path.exists(pkl_path):
        try:
            db = FAISS.load_local(
                folder_path=DB_PATH,
                index_name=INDEX_NAME,
                embeddings=embedding_model,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            db = create_empty_db(embedding_model)
            save_db()
    else:
        db = create_empty_db(embedding_model)
        save_db()

def save_db():
    global db
    if not db:
        return
    try:
        db.save_local(folder_path=DB_PATH, index_name=INDEX_NAME)
    except Exception as e:
        logger.exception(f"Error saving FAISS index to {DB_PATH}. Error: {e}")

async def add_faiss_documents(documents: List[schema.DocumentInput]) -> List[str]:
    if db is None:
        raise ValueError("FAISS DB not initialized. Cannot add documents.")

    docs_to_add: List[Document] = []
    for doc_input in documents:
        now_utc_iso = datetime.now(timezone.utc).isoformat()
        metadata = {
            "session_id": doc_input.session_id,
            "user_id": doc_input.user_id,
            "message_role": doc_input.message_role,
            "time": now_utc_iso,
        }
        if hasattr(doc_input, 'target_message_id') and doc_input.target_message_id is not None:
             metadata["target_message_id"] = doc_input.target_message_id
        if hasattr(doc_input, 'feedback_rating') and doc_input.feedback_rating is not None:
             metadata["feedback_rating"] = doc_input.feedback_rating
        docs_to_add.append(Document(page_content=doc_input.page_content, metadata=metadata))

    if not docs_to_add:
        return []
    added_ids = await db.aadd_documents(docs_to_add, ids=None)
    save_db()
    return added_ids

async def get_conversation_history_by_session(
    session_id: int,
    user_id: int,
    db_sql: AsyncSession
) -> schema.ConversationHistoryResponse:
    if db is None:
        raise ValueError("FAISS DB not initialized. Cannot retrieve history.")
    if not isinstance(db.docstore, InMemoryDocstore):
        raise TypeError("History retrieval is currently only supported for InMemoryDocstore.")

    session_orm_result = await db_sql.execute(
        select(OrmSession)
        .options(selectinload(OrmSession.topics))
        .where(OrmSession.session_id == session_id, OrmSession.user_id == user_id)
    )
    session_orm: Optional[OrmSession] = session_orm_result.scalars().first()

    session_title: Optional[str] = None
    session_topics: Optional[List[str]] = None

    if session_orm:
        session_title = session_orm.title
        if session_orm.topics:
            session_topics = [topic.topic_name for topic in session_orm.topics if topic.topic_name]
    else:
        logger.warning(f"Session with ID {session_id} and user_id {user_id} not found in SQL DB.")

    messages_with_details: List[Tuple[str, str, Document]] = []
    if not hasattr(db.docstore, '_dict'):
        logger.error("InMemoryDocstore does not have a _dict attribute. Cannot retrieve history.")
    else:
        for doc_id_key, doc_obj in db.docstore._dict.items():
            if not isinstance(doc_obj, Document) or not hasattr(doc_obj, 'metadata'):
                continue
            md = doc_obj.metadata
            if not isinstance(md, dict):
                continue
            if md.get("session_id") == session_id and md.get("user_id") == user_id:
                timestamp = md.get("time", datetime.min.replace(tzinfo=timezone.utc).isoformat())
                messages_with_details.append((timestamp, doc_id_key, doc_obj))

    messages_with_details.sort(key=lambda x: x[0])

    chat_messages: List[schema.ChatMessageOutput] = []
    for msg_time, msg_id, doc_obj in messages_with_details:
        md = doc_obj.metadata
        role_value = md.get("message_role")
        if role_value not in schema.ChatMessageOutput.model_fields["role"].annotation.__args__:
            role_value = "user"

        chat_messages.append(schema.ChatMessageOutput(
            doc_id=msg_id,
            page_content=doc_obj.page_content,
            role=role_value,
            timestamp=msg_time,
            user_id=md.get("user_id")
        ))

    return schema.ConversationHistoryResponse(
        session_id=session_id,
        user_id=user_id,
        title=session_title,
        topics=session_topics,
        messages=chat_messages,
        total_messages=len(chat_messages)
    )

def search_faiss_session(session_id: int, user_id: int, query: str, k: int) -> List[schema.SessionSearchResult]:
    if db is None:
        raise ValueError("FAISS DB not initialized. Cannot perform session search.")
    k_fetch = max(k * 5, 20)
    candidates = db.similarity_search_with_score(query=query, k=k_fetch)
    results: List[schema.SessionSearchResult] = []
    seen_doc_ids = set()
    for doc_obj_from_search, score in candidates:
        if not isinstance(doc_obj_from_search, Document) or not hasattr(doc_obj_from_search, 'metadata'):
            continue
        md = doc_obj_from_search.metadata
        if not isinstance(md, dict):
            continue
        if md.get("session_id") == session_id and md.get("user_id") == user_id:
            found_doc_id = None
            if hasattr(db.docstore, '_dict'):
                for id_key, stored_doc_obj in db.docstore._dict.items():
                    if stored_doc_obj.page_content == doc_obj_from_search.page_content and \
                       stored_doc_obj.metadata == md:
                        if id_key not in seen_doc_ids:
                           found_doc_id = id_key
                           break
            if found_doc_id:
                results.append(schema.SessionSearchResult(
                    doc_id=found_doc_id,
                    page_content=doc_obj_from_search.page_content,
                    metadata=md,
                    score=score
                ))
                seen_doc_ids.add(found_doc_id)
        if len(results) >= k:
            break
    return results[:k]


async def get_sessions_by_keyword(
    user_id: int,
    keyword: str,
    db_sql: AsyncSession
) -> List[schema.ConversationHistoryResponse]:
    if db is None:
        raise ValueError("FAISS DB not initialized. Cannot search by keyword.")
    if not isinstance(db.docstore, InMemoryDocstore):
        raise TypeError("Keyword search is currently only supported for InMemoryDocstore.")

    matching_session_ids: Set[int] = set()

    if not hasattr(db.docstore, '_dict') or not isinstance(db.docstore._dict, dict):
        return []

    for doc_id_key, doc_obj in db.docstore._dict.items():
        if not isinstance(doc_obj, Document) or \
           not hasattr(doc_obj, 'metadata') or \
           not hasattr(doc_obj, 'page_content'):
            continue
        metadata = doc_obj.metadata
        page_content = doc_obj.page_content
        if not isinstance(metadata, dict) or not isinstance(page_content, str):
            continue
        if metadata.get("user_id") == user_id and keyword.lower() in page_content.lower():
            session_id = metadata.get("session_id")
            if session_id is not None and isinstance(session_id, int):
                matching_session_ids.add(session_id)

    sessions_history: List[schema.ConversationHistoryResponse] = []
    for session_id_val in sorted(list(matching_session_ids)):
        try:
            history = await get_conversation_history_by_session(
                session_id=session_id_val,
                user_id=user_id,
                db_sql=db_sql
            )
            if history.messages:
                sessions_history.append(history)
        except Exception as e:
            logger.error(f"Error fetching history for session_id {session_id_val} (user_id: {user_id}) during keyword search: {e}", exc_info=True)
    return sessions_history
