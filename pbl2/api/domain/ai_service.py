import os, httpx
from api.core.security import create_access_token

AI_SERVER_URL = os.getenv("AI_SERVER_URL")

async def call_ai(endpoint: str, payload: dict) -> dict:
    token = create_access_token({"sub": "backend_service"})
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=AI_SERVER_URL, timeout=30) as client:
        resp = await client.post(f"{endpoint}", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
