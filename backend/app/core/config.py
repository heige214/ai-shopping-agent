from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：所有可变参数都从环境变量或 .env 读取。"""

    app_name: str = "AI 找货"
    api_prefix: str = "/api"
    database_url: str = "postgresql+asyncpg://shop:shop@localhost:5433/shop"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        """拒绝空值与过短密钥，强制在 .env 中配置随机字符串。"""
        secret = value.strip()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY 必须至少 32 个字符")
        return secret

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的前端地址转换成列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免重复读取 .env。"""
    return Settings()


settings = get_settings()
