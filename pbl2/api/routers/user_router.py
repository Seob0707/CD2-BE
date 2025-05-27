from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from api.schemas import user_schema
from api.database import get_db
from api.domain import user_service
from api.core import security
from api.core.auth import get_current_user
from api.models.ORM import User
from datetime import timedelta

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

    access_token_expires = timedelta(minutes=security.settings.access_token_expire_minutes)
    access_token = security.create_access_token(
        data={"sub": str(db_user.user_id), "role": db_user.role},
        expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(days=security.settings.refresh_token_expire_days)
    refresh_token = security.create_refresh_token(
        data={"sub": str(db_user.user_id)},
        expires_delta=refresh_token_expires
    )

    await user_service.update_user_refresh_token(db, db_user.user_id, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.user_id,
        "refresh_token": refresh_token 
    }

@router.get("/me")
async def read_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "created_at": current_user.created_at
    }

oauth2_scheme_refresh = OAuth2PasswordBearer(tokenUrl="/api/v1/user/refresh-token")

@router.post("/refresh-token", response_model=user_schema.Token, summary="리프레시 토큰으로 액세스 토큰 갱신")
async def refresh_access_token(
    refresh_token: str = Depends(oauth2_scheme_refresh),
    db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="리프레시 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 리프레시 토큰 디코딩
    token_data = security.decode_token(refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise credentials_exception

    user_id_str: str = token_data.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await user_service.get_user_by_id(db, user_id)
    if not user or user.refresh_token != refresh_token:
        if user and user.refresh_token:
            await user_service.update_user_refresh_token(db, user.user_id, None)
        raise credentials_exception

    access_token_expires = timedelta(minutes=security.settings.access_token_expire_minutes)
    new_access_token = security.create_access_token(
        data={"sub": str(user.user_id), "role": user.role},
        expires_delta=access_token_expires
    )

    new_refresh_token_expires = timedelta(days=security.settings.refresh_token_expire_days)
    new_refresh_token = security.create_refresh_token(
        data={"sub": str(user.user_id)},
        expires_delta=new_refresh_token_expires
    )
    
    await user_service.update_user_refresh_token(db, user.user_id, new_refresh_token)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "refresh_token": new_refresh_token
    }

@router.post("/logout", summary="사용자 로그아웃 (리프레시 토큰 무효화 포함)")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await user_service.update_user_refresh_token(db, current_user.user_id, None)
    return {"message": "로그아웃 성공. 리프레시 토큰이 무효화되었습니다."}