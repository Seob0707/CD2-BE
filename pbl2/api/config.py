from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic import Field

class Settings(BaseSettings):
    environment: str = Field("development", alias="environment")
    secret_key: str = Field("default_secret", alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    db_ssl_ca: str | None = Field(None, alias="DB_SSL_CA")
    db_ssl_cert: str | None = Field(None, alias="DB_SSL_CERT")
    db_ssl_key: str | None = Field(None, alias="DB_SSL_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

    @field_validator("secret_key", mode="before")
    @classmethod
    def validate_secret_key(cls, v, info: FieldValidationInfo):
        env = info.data.get("environment", "development") if info.data else "development"
        if env == "production" and (not v or v == "default_secret"):
            raise ValueError("production 환경에서는 SECRET_KEY를 안전한 값으로 설정해야 합니다.")
        return v


    @field_validator("db_ssl_ca", mode="before")
    @classmethod
    def validate_db_ssl_ca(cls, v, info: FieldValidationInfo):
        env = info.data.get("environment", "development") if info.data else "development"
        if env == "production" and (v is None or v.strip() == ""):
            raise ValueError("production 환경에서는 DB_SSL_CA 값을 반드시 설정해야 합니다.")
        return v


    @field_validator("db_ssl_cert", "db_ssl_key", mode="before")
    @classmethod
    def validate_optional_db_ssl_fields(cls, v, info: FieldValidationInfo):
        return v.strip() if v is not None else v


settings = Settings()
