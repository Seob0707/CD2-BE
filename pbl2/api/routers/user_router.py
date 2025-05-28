from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from api.schemas import user_schema
from api.database import get_db
from api.domain import user_service
from api.core import security
from api.core.auth import get_current_user
from api.models.ORM import User
from datetime import timedelta, datetime
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/signup")
async def signup(user: user_schema.UserCreate, db: AsyncSession = Depends(get_db)):
    new_user = await user_service.create_user(db, user)
    return {"message": "회원가입 성공", "user_id": new_user.user_id}

@router.post("/login", response_model=user_schema.Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    email = form_data.username
    password = form_data.password

    logger.info(f"로그인 시도: {email}")

    db_user = await user_service.authenticate_user(db, email, password)
    if not db_user:
        logger.warning(f"로그인 실패: {email}")
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 틀렸습니다.")

    # 토큰 만료 시간 설정 확인
    access_token_expires = timedelta(minutes=security.settings.access_token_expire_minutes)
    refresh_token_expires = timedelta(days=security.settings.refresh_token_expire_days)
    
    logger.info(f"토큰 만료 시간 설정 - Access: {security.settings.access_token_expire_minutes}분, Refresh: {security.settings.refresh_token_expire_days}일")

    # 토큰 생성
    access_token = security.create_access_token(
        data={"sub": str(db_user.user_id), "role": db_user.role},
        expires_delta=access_token_expires
    )

    refresh_token = security.create_refresh_token(
        data={"sub": str(db_user.user_id)},  # type은 security.py에서 자동 추가
        expires_delta=refresh_token_expires
    )

    logger.info(f"토큰 생성 완료 - User ID: {db_user.user_id}")
    logger.debug(f"생성된 리프레시 토큰: {refresh_token[:50]}...")

    # DB에 리프레시 토큰 저장
    await user_service.update_user_refresh_token(db, db_user.user_id, refresh_token)
    logger.info(f"DB에 리프레시 토큰 저장 완료 - User ID: {db_user.user_id}")

    # 쿠키 설정
    cookie_max_age = int(refresh_token_expires.total_seconds())
    logger.info(f"쿠키 설정 - max_age: {cookie_max_age}초 ({refresh_token_expires.days}일)")
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=security.settings.environment == "production",
        samesite="lax",
        max_age=cookie_max_age,
        path="/"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.user_id,
    }

@router.get("/me")
async def read_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "created_at": current_user.created_at
    }

async def get_refresh_token_from_cookie(request: Request) -> str:
    refresh_token = request.cookies.get("refresh_token")
    logger.info(f"쿠키에서 리프레시 토큰 조회: {'있음' if refresh_token else '없음'}")
    
    if not refresh_token:
        logger.warning("리프레시 토큰 쿠키가 없음")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰 쿠키가 없습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"받은 리프레시 토큰: {refresh_token[:50]}...")
    return refresh_token

@router.post("/refresh-token", response_model=user_schema.Token, summary="리프레시 토큰으로 액세스 토큰 갱신")
async def refresh_access_token(
    response: Response,
    refresh_token: str = Depends(get_refresh_token_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    logger.info("리프레시 토큰으로 액세스 토큰 갱신 시도")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="리프레시 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 토큰 디코딩
    try:
        token_data = security.decode_token(refresh_token)
        logger.info(f"토큰 디코딩 성공: {bool(token_data)}")
        
        if not token_data:
            logger.warning("토큰 데이터가 None")
            raise credentials_exception
            
        if token_data.get("type") != "refresh":
            logger.warning(f"토큰 타입이 올바르지 않음: {token_data.get('type')}")
            raise credentials_exception
            
        logger.info("리프레시 토큰 타입 검증 통과")
        
    except Exception as e:
        logger.error(f"토큰 디코딩 실패: {str(e)}")
        raise credentials_exception

    # 사용자 ID 추출
    user_id_str: str = token_data.get("sub")
    if user_id_str is None:
        logger.warning("토큰에 사용자 ID(sub)가 없음")
        raise credentials_exception

    try:
        user_id = int(user_id_str)
        logger.info(f"사용자 ID 추출 성공: {user_id}")
    except ValueError:
        logger.error(f"사용자 ID 형식 오류: {user_id_str}")
        raise credentials_exception

    # 사용자 조회
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        logger.error(f"사용자를 찾을 수 없음: {user_id}")
        raise credentials_exception
    
    logger.info(f"사용자 조회 성공: {user.email}")

    # 리프레시 토큰 일치 확인
    if not user.refresh_token:
        logger.warning(f"DB에 저장된 리프레시 토큰이 없음 - User ID: {user_id}")
        raise credentials_exception
        
    if user.refresh_token != refresh_token:
        logger.warning(f"리프레시 토큰 불일치 - User ID: {user_id}")
        logger.debug(f"DB 토큰: {user.refresh_token[:50]}...")
        logger.debug(f"요청 토큰: {refresh_token[:50]}...")
        
        # 토큰 불일치 시 DB의 토큰 무효화
        await user_service.update_user_refresh_token(db, user.user_id, None)
        response.delete_cookie("refresh_token", path="/")
        raise credentials_exception

    logger.info("리프레시 토큰 일치 확인 완료")

    # 새로운 토큰들 생성
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
    
    logger.info("새로운 토큰 생성 완료")
    logger.debug(f"새 리프레시 토큰: {new_refresh_token[:50]}...")

    # DB에 새 리프레시 토큰 저장
    await user_service.update_user_refresh_token(db, user.user_id, new_refresh_token)
    logger.info("DB에 새 리프레시 토큰 저장 완료")

    # 새 리프레시 토큰을 쿠키에 설정
    cookie_max_age = int(new_refresh_token_expires.total_seconds())
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=security.settings.environment == "production",
        samesite="lax",
        max_age=cookie_max_age,
        path="/"
    )
    
    logger.info("새 리프레시 토큰 쿠키 설정 완료")

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "user_id": user.user_id,
    }

@router.post("/logout", summary="사용자 로그아웃 (리프레시 토큰 무효화 포함)")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"로그아웃 시도 - User ID: {current_user.user_id}")
    
    await user_service.update_user_refresh_token(db, current_user.user_id, None)
    response.delete_cookie("refresh_token", path="/")
    
    logger.info(f"로그아웃 완료 - User ID: {current_user.user_id}")
    return {"message": "로그아웃 성공. 리프레시 토큰이 무효화되었습니다."}

# 디버깅용 엔드포인트 추가
@router.get("/debug/token-info")
async def debug_token_info(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """디버깅용: 현재 토큰 정보 확인"""
    refresh_token_cookie = request.cookies.get("refresh_token")
    
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "has_refresh_cookie": bool(refresh_token_cookie),
        "db_has_refresh_token": bool(current_user.refresh_token),
        "tokens_match": refresh_token_cookie == current_user.refresh_token if refresh_token_cookie and current_user.refresh_token else False,
        "settings": {
            "access_token_expire_minutes": security.settings.access_token_expire_minutes,
            "refresh_token_expire_days": security.settings.refresh_token_expire_days,
            "environment": security.settings.environment
        }
    }