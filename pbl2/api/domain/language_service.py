from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx 
from typing import List, Dict, Tuple

from api.models.ORM import Language 

AUTO_SELECT_LANGUAGE_ID = 1
DEFAULT_APP_LANGUAGE_ID = 2 
DEFAULT_APP_LANGUAGE_CODE = "ko" 

COUNTRY_TO_LANG_CODE_MAP: Dict[str, str] = {
    "KR": "ko",  
    "US": "en",  
    "GB": "en",  
    "JP": "ja",  
}

async def get_all_languages(db: AsyncSession) -> List[Language]:
    stmt = select(Language).order_by(Language.lang_id)
    result = await db.execute(stmt)
    languages = result.scalars().all()
    return languages

def _parse_accept_language_header(header_value: str) -> List[Tuple[str, float]]:
    if not header_value:
        return []
    
    languages = []
    for lang_part in header_value.split(','):
        parts = lang_part.strip().split(';')
        lang_tag = parts[0].strip().lower()
        q_value = 1.0
        for part in parts[1:]:
            if part.strip().startswith('q='):
                try:
                    q_value = float(part.strip()[2:])
                    break
                except ValueError:
                    pass
        languages.append((lang_tag, q_value))
    
    languages.sort(key=lambda x: x[1], reverse=True)
    return languages

async def _get_lang_code_from_ip(request: Request, db: AsyncSession) -> str | None:
    client_ip = request.client.host
    if not client_ip or client_ip == "127.0.0.1" or client_ip == "localhost": 
        return None

    try:
        async with httpx.AsyncClient(timeout=2.0) as client: 
            response = await client.get(f"https://get.geojs.io/v1/ip/country/{client_ip}.json")
            response.raise_for_status() 
            data = response.json()
            country_code = data.get("country")
            
            if country_code:
                lang_code_from_map = COUNTRY_TO_LANG_CODE_MAP.get(country_code.upper())
                if lang_code_from_map:
                    lang_exists_result = await db.execute(
                        select(Language.lang_code).where(Language.lang_code == lang_code_from_map)
                    )
                    if lang_exists_result.scalars().first():
                        return lang_code_from_map
    except httpx.RequestError: 
        pass 
    except Exception: 
        pass
    return None

async def get_effective_lang_code(
    request: Request,
    user_language_preference_id: int,
    db: AsyncSession
) -> str:
    if user_language_preference_id != AUTO_SELECT_LANGUAGE_ID:
        lang_result = await db.execute(
            select(Language.lang_code).where(Language.lang_id == user_language_preference_id)
        )
        specific_lang_code = lang_result.scalars().first()
        if specific_lang_code:
            return specific_lang_code
        default_lang_from_id_result = await db.execute(
            select(Language.lang_code).where(Language.lang_id == DEFAULT_APP_LANGUAGE_ID)
        )
        fallback_code = default_lang_from_id_result.scalars().first()
        return fallback_code if fallback_code else DEFAULT_APP_LANGUAGE_CODE

    accept_language_header = request.headers.get("accept-language")
    if accept_language_header:
        parsed_langs = _parse_accept_language_header(accept_language_header)
        for lang_tag, _ in parsed_langs:
            full_match_result = await db.execute(
                select(Language.lang_code).where(Language.lang_code == lang_tag)
            )
            if full_match_result.scalars().first():
                return lang_tag
            
            base_lang_code = lang_tag.split('-')[0]
            base_match_result = await db.execute(
                select(Language.lang_code).where(Language.lang_code == base_lang_code)
            )
            if base_match_result.scalars().first():
                return base_lang_code
    
    lang_code_from_ip = await _get_lang_code_from_ip(request, db)
    if lang_code_from_ip:
        return lang_code_from_ip

    default_lang_from_id_result = await db.execute(
        select(Language.lang_code).where(Language.lang_id == DEFAULT_APP_LANGUAGE_ID)
    )
    final_fallback_code = default_lang_from_id_result.scalars().first()
    return final_fallback_code if final_fallback_code else DEFAULT_APP_LANGUAGE_CODE