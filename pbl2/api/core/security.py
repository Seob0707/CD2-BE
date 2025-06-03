import os
import bcrypt
import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from api.config import settings
from api.core.auth import get_current_user

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({
        "exp": expire,
        "server_env": settings.environment
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def create_refresh_token(
    data: dict,
    expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "server_env": settings.environment, 
        "type": "refresh"
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None

def get_token_origin(token: str) -> str:
    payload = decode_token(token)
    if not payload:
        return "invalid"
    return payload.get("server_env", "unknown")

async def admin_required(current_user = Depends(get_current_user)):
    if not hasattr(current_user, 'role') or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return current_user

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password)

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

hash_password = get_password_hash

def generate_hmac(data: str, secret: str = None) -> str:
    secret_key = secret or settings.AI_SERVER_SHARED_SECRET
    if not secret_key:
        raise ValueError("HMAC secret key is not configured")
    return base64.b64encode(
        hmac.new(secret_key.encode(), data.encode(), hashlib.sha256).digest()
    ).decode()

def generate_hmac_bytes(data: bytes, secret: str = None) -> str:
    secret_key = secret or settings.AI_SERVER_SHARED_SECRET
    if not secret_key:
        raise ValueError("HMAC secret key is not configured")
    return base64.b64encode(
        hmac.new(secret_key.encode(), data, hashlib.sha256).digest()
    ).decode()

def verify_hmac_signature(data: str, received_signature: str, secret: str = None) -> bool:
    if not received_signature:
        return False
    try:
        expected_signature = generate_hmac(data, secret)
        return hmac.compare_digest(expected_signature, received_signature)
    except ValueError:
        return False

def verify_hmac_signature_bytes(data: bytes, received_signature: str, secret: str = None) -> bool:
    if not received_signature:
        return False
    try:
        expected_signature = generate_hmac_bytes(data, secret)
        return hmac.compare_digest(expected_signature, received_signature)
    except ValueError:
        return False

def serialize_json_for_hmac(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(',', ':'))

def serialize_pydantic_for_hmac(model: BaseModel) -> str:
    data_dict = model.model_dump()
    return serialize_json_for_hmac(data_dict)