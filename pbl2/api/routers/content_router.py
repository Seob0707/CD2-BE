from fastapi import APIRouter, Depends
from api.dependencies import get_resolved_lang_code

router = APIRouter(
    prefix="/content",
    tags=["content"]
)

@router.get("/greeting")
async def get_greeting_message(
    lang_code: str = Depends(get_resolved_lang_code)
):
    if lang_code == "ko":
        return {"message": "안녕하세요!"}
    elif lang_code == "en":
        return {"message": "Hello!"}
    elif lang_code == "ja":
        return {"message": "こんにちは！"}
    else:
        return {"message": f"Greetings! (Language: {lang_code}, Enhanced logic)"}