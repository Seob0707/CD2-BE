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

DB_PATH = os.getenv("FAISS_DB_PATH", "./db")
INDEX_NAME = "faiss_index"
DIMENSIONS = 1536 

db: Optional[FAISS] = None

def create_empty_db(embedding_model: OpenAIEmbeddings) -> FAISS:
    logger.info(f"Creating new FAISS index with {DIMENSIONS} dimensions.")
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
        logger.error(f"Failed to initialize OpenAIEmbeddings. Ensure OPENAI_API_KEY is set. Error: {e}")
        raise ValueError(f"OpenAIEmbeddings initialization failed: {e}")

    faiss_path = os.path.join(DB_PATH, f"{INDEX_NAME}.faiss")
    pkl_path = os.path.join(DB_PATH, f"{INDEX_NAME}.pkl")

    if os.path.exists(faiss_path) and os.path.exists(pkl_path):
        try:
            logger.info(f"Loading FAISS index from local path: {DB_PATH}")
            db = FAISS.load_local(
                folder_path=DB_PATH,
                index_name=INDEX_NAME,
                embeddings=embedding_model,
                allow_dangerous_deserialization=True 
            )
            logger.info("FAISS index loaded successfully from local path.")
        except Exception as e:
            logger.exception(f"Failed to load FAISS index from {DB_PATH}. Creating a new one. Error: {e}")
            db = create_empty_db(embedding_model)
            save_db()
    else:
        logger.info(f"No FAISS index found at {DB_PATH}. Creating a new one.")
        db = create_empty_db(embedding_model)
        save_db()

def save_db():
    global db
    if not db:
        logger.warning("Attempted to save FAISS DB, but no instance exists.")
        return
    try:
        logger.info(f"Saving FAISS index to local path: {DB_PATH}")
        db.save_local(folder_path=DB_PATH, index_name=INDEX_NAME)
        logger.info("FAISS index saved successfully to local path.")
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
            # 피드백 관련 필드는 DocumentInput 스키마에 따라 자동으로 처리됨
            # "target_message_id": doc_input.target_message_id,
            # "feedback_rating": doc_input.feedback_rating,
        }
        if hasattr(doc_input, 'target_message_id') and doc_input.target_message_id is not None:
             metadata["target_message_id"] = doc_input.target_message_id
        if hasattr(doc_input, 'feedback_rating') and doc_input.feedback_rating is not None:
             metadata["feedback_rating"] = doc_input.feedback_rating

        docs_to_add.append(Document(page_content=doc_input.page_content, metadata=metadata))

    if not docs_to_add:
        return []

    added_ids = await db.aadd_documents(docs_to_add)
    save_db() 
    logger.info(f"Successfully added {len(added_ids)} documents to FAISS.")
    return added_ids


def get_conversation_history_by_session(session_id: int, user_id: int) -> schema.ConversationHistoryResponse:
    if db is None:
        raise ValueError("FAISS DB not initialized. Cannot retrieve history.")
    if not isinstance(db.docstore, InMemoryDocstore):
        raise TypeError("History retrieval is currently only supported for InMemoryDocstore.")

        messages_with_details: List[Tuple[str, str, Document]] = [] 

    for doc_id_key, doc_obj in db.docstore._dict.items():
        md = doc_obj.metadata
        if md.get("session_id") == session_id and md.get("user_id") == user_id:
            messages_with_details.append((
                md.get("time", "1970-01-01T00:00:00Z"), 
                doc_id_key,
                doc_obj
            ))

    messages_with_details.sort(key=lambda x: x[0])

    chat_messages: List[schema.ChatMessageOutput] = []
    for msg_time, msg_id, doc_obj in messages_with_details:
        md = doc_obj.metadata
        chat_messages.append(schema.ChatMessageOutput(
            doc_id=msg_id, 
            page_content=doc_obj.page_content,
            message_role=md.get("message_role"), 
            timestamp=md.get("time"),
            user_id=md.get("user_id"),
            # target_message_id=md.get("target_message_id"), # 피드백 제외 시 주석 처리
            # feedback_rating=md.get("feedback_rating")    # 피드백 제외 시 주석 처리
        ))

    return schema.ConversationHistoryResponse(
        session_id=session_id,
        user_id=user_id,
        messages=chat_messages,
        total_messages=len(chat_messages)
    )

def search_faiss_session(session_id: int, user_id: int, query: str, k: int) -> List[schema.SessionSearchResult]:
    if db is None:
        raise ValueError("FAISS DB not initialized")

    k_fetch = max(k * 5, 20)
    candidates = db.similarity_search_with_score(query=query, k=k_fetch)
    
    results: List[schema.SessionSearchResult] = []
    seen_doc_content_metadata_tuples = set()

    for doc_obj_from_search, score in candidates:
        md = doc_obj_from_search.metadata
        if md.get("session_id") == session_id and md.get("user_id") == user_id:
            current_doc_tuple = (doc_obj_from_search.page_content, tuple(sorted(md.items())))

            if current_doc_tuple not in seen_doc_content_metadata_tuples:
                found_doc_id = None
                for id_key, stored_doc_obj in db.docstore._dict.items():
                    if stored_doc_obj.page_content == doc_obj_from_search.page_content and \
                       stored_doc_obj.metadata == md:
                        found_doc_id = id_key
                        break
                
                if found_doc_id:
                    results.append(schema.SessionSearchResult(
                        doc_id=found_doc_id,
                        page_content=doc_obj_from_search.page_content,
                        metadata=md,
                        score=score
                    ))
                    seen_doc_content_metadata_tuples.add(current_doc_tuple)
            
        if len(results) >= k:
            break
    return results[:k]

if db is None:
    load_or_create_faiss_db()