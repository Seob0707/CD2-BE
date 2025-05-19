from fastapi import APIRouter, Depends, HTTPException 
from fastapi.security import OAuth2PasswordRequestForm 
from sqlalchemy.ext.asyncio import AsyncSession
from api.schemas import user_schema
from api.database import get_db
from api.domain import user_service
from api.core import security
from api.core.auth import get_current_user 
from api.models.ORM import User 

router = APIRouter()

@router.post("/signup")
async def signup(user: user_schema.UserCreate, db: AsyncSession = Depends(get_db)):
    new_user = await user_service.create_user(db, user)
    return {"message": "회원가입 성공", "user_id": new_user.user_id}

@router.post("/login", response_model=user_schema.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    email = form_data.username
    password = form_data.password

    db_user = await user_service.authenticate_user(db, email, password)
    if not db_user:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 틀렸습니다.")

    access_token = security.create_access_token(data={"sub": str(db_user.user_id), "role": db_user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.user_id
    }

@router.get("/me")
async def read_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "created_at": current_user.created_at
    }