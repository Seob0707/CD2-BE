import httpx
from api.core.security import create_access_token
from api.config import settings
import logging

logger = logging.getLogger(__name__)

async def call_ai(endpoint: str, payload: dict) -> dict:
    token = create_access_token({"sub": "backend_service_proxy"})
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=settings.AI_SERVER_URL, timeout=settings.AI_SERVER_TIMEOUT) as client:
        try:
            resp = await client.post(f"{endpoint}", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"AI server (proxy call) returned an error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI server proxy call: {e}")
            raise

async def _request_ai_server_management_api(
    method: str,
    ai_server_endpoint: str,
    query_params: dict | None = None,
    json_payload: dict | None = None
):
    if not settings.AI_SERVER_SHARED_SECRET:
        logger.error("AI_SERVER_SHARED_SECRET is not configured. Cannot make management API call to AI server.")
        raise ValueError("AI_SERVER_SHARED_SECRET is not configured for AI server communication.")

    headers = {
        "X-Internal-Auth-Token": settings.AI_SERVER_SHARED_SECRET,
        "Content-Type": "application/json"
    }
    full_url = f"{settings.AI_SERVER_URL}{ai_server_endpoint}"
    logger.info(f"Requesting AI server management API: {method.upper()} {full_url}")
    async with httpx.AsyncClient(timeout=settings.AI_SERVER_TIMEOUT) as client:
        try:
            if method.upper() == "DELETE":
                resp = await client.delete(full_url, headers=headers, params=query_params)
            elif method.upper() == "POST":
                resp = await client.post(full_url, headers=headers, json=json_payload, params=query_params)
            else:
                logger.error(f"Unsupported HTTP method for AI management API: {method}")
                raise ValueError(f"Unsupported HTTP method: {method}")
            resp.raise_for_status()
            if resp.status_code == 204:
                logger.info(f"AI server management API call successful (204 No Content): {method.upper()} {full_url}")
                return None
            response_data = resp.json()
            logger.info(f"AI server management API response: {response_data}")
            return response_data
        except httpx.HTTPStatusError as e:
            logger.error(f"AI server management API returned an error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI server management API call: {e}")
            raise

async def delete_specific_file_from_ai_server_internal(session_id: int, filename: str) -> dict | None:
    ai_server_delete_endpoint = f"/admin/files/specific/{session_id}/{filename}" 
    logger.info(f"Internal request to delete specific file from AI server: session_id={session_id}, filename={filename}")
    return await _request_ai_server_management_api(method="DELETE", ai_server_endpoint=ai_server_delete_endpoint)

async def delete_all_files_for_session_from_ai_server_internal(session_id: int) -> dict | None:
    ai_server_session_files_delete_endpoint = f"/admin/files/session/{session_id}/all" 
    logger.info(f"Internal request to delete ALL files for session {session_id} from AI server via endpoint: {ai_server_session_files_delete_endpoint}")
    return await _request_ai_server_management_api(method="DELETE", ai_server_endpoint=ai_server_session_files_delete_endpoint)

async def delete_all_backend_sent_files_from_ai_server_internal() -> dict | None:
    ai_server_bulk_delete_endpoint = "/admin/files/all_temporary" 
    logger.info(f"Internal request to delete ALL backend-sent temporary files from AI server via endpoint: {ai_server_bulk_delete_endpoint}")
    return await _request_ai_server_management_api(method="DELETE", ai_server_endpoint=ai_server_bulk_delete_endpoint)