from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    confirm_pwd: str
    nickname: Optional[str] = None

    @field_validator("password")
    def password_complexity(cls, v: str) -> str:
        if not (6 <= len(v) <= 20):
            raise ValueError("비밀번호는 6자 이상 20자 이하이어야 합니다.")
        if not any(c.isalpha() for c in v):
            raise ValueError("비밀번호는 최소 하나의 영문을 포함해야 합니다.")
        if not any(c.isdigit() for c in v):
            raise ValueError("비밀번호는 최소 하나의 숫자를 포함해야 합니다.")
        return v

    @field_validator("confirm_pwd")
    def passwords_match(cls, v: str, info) -> str:
        if v != info.data.get("password"):
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    refresh_token: str

class UserOAuthCreate(BaseModel):
    email: EmailStr
    nickname: Optional[str] = None