from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import Optional

from api.models.ORM import User
from api.core import security
from api.schemas.user_schema import UserCreate, UserOAuthCreate

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalars().first()

async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 등록된 이메일입니다.")

    if hasattr(user_data, 'password') and hasattr(user_data, 'confirm_pwd'):
        if user_data.password != user_data.confirm_pwd:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비밀번호 확인이 일치하지 않습니다.")
        hashed_pw = security.hash_password(user_data.password)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비밀번호 정보가 필요합니다.")


    nickname = user_data.nickname if user_data.nickname else user_data.email.split('@')[0]

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

async def create_oauth_user(
    db: AsyncSession,
    user_data: UserOAuthCreate,
    oauth_provider: str,
    oauth_id: str,
    refresh_token_val: Optional[str] = None
) -> User:
    nickname = user_data.nickname if user_data.nickname else user_data.email.split('@')[0]

    new_user = User(
        email=user_data.email,
        nickname=nickname,
        login_info=oauth_provider,
        Oauth=oauth_provider,
        Oauth_id=oauth_id,
        refresh_token=refresh_token_val,
        password=None 
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def update_user_oauth_details(
    db: AsyncSession,
    user: User,
    nickname: str,
    oauth_provider: str,
    oauth_id: str,
    new_refresh_token: Optional[str] = None
) -> User:
    if user.nickname != nickname:
        user.nickname = nickname
    user.Oauth = oauth_provider
    user.Oauth_id = oauth_id
    if new_refresh_token:
        user.refresh_token = new_refresh_token
    await db.commit()
    await db.refresh(user)
    return user

async def update_user_refresh_token(db: AsyncSession, user_id: int, refresh_token: str | None) -> Optional[User]:
    user = await get_user_by_id(db, user_id)
    if user:
        user.refresh_token = refresh_token
        await db.commit()
        await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user or not user.password: 
        return None
    if not security.verify_password(password, user.password):
        return None
    return user
