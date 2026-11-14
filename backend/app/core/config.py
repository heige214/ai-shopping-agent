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
    cors_origins: str = "http://localhost:5175"

    # AI：key 可选；缺失时客服退化为本地规则 + 关键词检索
    ai_provider: str = "auto"  # auto / dashscope / local / fake
    dashscope_api_key: str | None = None
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024
    vision_model: str = "qwen3-vl-flash"
    asr_model: str = "paraformer-v2"
    dashscope_native_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    llm_timeout_seconds: float = 20.0

    # 上传：单文件大小上限（MB）与落盘目录（相对 backend/）
    max_image_upload_mb: float = 5
    max_voice_upload_mb: float = 10
    upload_dir: str = "static/uploads"

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

    @field_validator("dashscope_api_key", mode="before")
    @classmethod
    def normalize_dashscope_key(cls, value: object) -> str | None:
        """.env 中留空视为未配置，避免空字符串被当成有效 key。"""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("ai_provider")
    @classmethod
    def normalize_ai_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider not in ("auto", "dashscope", "local", "fake"):
            raise ValueError("AI_PROVIDER 只能是 auto/dashscope/local/fake")
        return provider

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的前端地址转换成列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免重复读取 .env。"""
    return Settings()


settings = get_settings()
