from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from api.models.ORM import User
from api.core import security

async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, user_data):
    if await get_user_by_email(db, user_data.email):
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    
    if user_data.password != user_data.confirm_pwd:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비밀번호 확인이 일치하지 않습니다.")
    
    hashed_pw = security.hash_password(user_data.password)
    
    nickname = user_data.nickname if user_data.nickname else user_data.email

    new_user = User(
        email=user_data.email,
        password=hashed_pw,
        nickname=nickname,
        login_info="email"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def create_oauth_user(db: AsyncSession, user_data):
    if await get_user_by_email(db, user_data.email):
        return await get_user_by_email(db, user_data.email)
    
    dummy_password = "GooglePass1"
    hashed_pw = security.hash_password(dummy_password)
    nickname = user_data.nickname if user_data.nickname else user_data.email

    new_user = User(
        email=user_data.email,
        password=hashed_pw,
        nickname=nickname,
        login_info="google"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user_by_email(db, email)
    if not user or not security.verify_password(password, user.password):
        return None
    return user

