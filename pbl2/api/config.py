from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field
from pydantic_core.core_schema import FieldValidationInfo
import os

class Settings(BaseSettings):
    environment: str = Field("development", alias="ENVIRONMENT")
    secret_key: str = Field("default_secret", alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    db_ssl_ca: str | None = Field(None, alias="DB_SSL_CA")
    db_ssl_cert: str | None = Field(None, alias="DB_SSL_CERT")
    db_ssl_key: str | None = Field(None, alias="DB_SSL_KEY")

    UPLOAD_DIR: str = Field("uploads", alias="UPLOAD_DIR")
    AI_SERVER_URL: str = Field("http://127.0.0.1:8001/ai", alias="AI_SERVER_URL")
    AI_SERVER_TIMEOUT: int = Field(30, alias="AI_SERVER_TIMEOUT")
    AI_SERVER_SHARED_SECRET: str | None = Field(None, alias="AI_SERVER_SHARED_SECRET")

    BACKEND_INTERNAL_API_KEY: str | None = Field(None, alias="BACKEND_INTERNAL_API_KEY")

    PROJECT_NAME: str = "CD2 Project API"
    PROJECT_DESCRIPTION: str = "PBL CD2 프로젝트 백엔드 API 문서입니다."
    API_VERSION: str = "1.0.0"

    TEMP_FILE_TTL_HOURS: int = Field(3, alias="TEMP_FILE_TTL_HOURS", description="임시 파일 삭제 주기 (시간 단위)")
    CLEANUP_JOB_INTERVAL_HOURS: int = Field(1, alias="CLEANUP_JOB_INTERVAL_HOURS", description="임시 파일 정리 작업 실행 간격 (시간 단위)")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False
    )

    @field_validator("secret_key", mode="before")
    @classmethod
    def validate_secret_key(cls, v, info: FieldValidationInfo):
        env = info.data.get("environment", "development") if info.data else os.getenv("ENVIRONMENT", "development")
        if env == "production" and (not v or v == "default_secret"):
            raise ValueError("production 환경에서는 SECRET_KEY를 안전한 값으로 설정해야 합니다.")
        return v

    @field_validator("db_ssl_ca", mode="before")
    @classmethod
    def validate_db_ssl_ca(cls, v, info: FieldValidationInfo):
        env = info.data.get("environment", "development") if info.data else os.getenv("ENVIRONMENT", "development")
        if env == "production" and (v is None or v.strip() == ""):
            pass
        return v

    @field_validator("db_ssl_cert", "db_ssl_key", mode="before")
    @classmethod
    def validate_optional_db_ssl_fields(cls, v, info: FieldValidationInfo):
        return v.strip() if v is not None else v

settings = Settings()