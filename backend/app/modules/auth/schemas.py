from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES

USERNAME_PATTERN = r"^[A-Za-z0-9_]+$"


class RegisterRequest(BaseModel):
    """注册请求：用户名、密码与可选昵称。"""

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=6, max_length=128)
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        """去掉用户名首尾空白，避免产生不可见字符账号。"""
        return value.strip() if isinstance(value, str) else value

    @field_validator("nickname", mode="before")
    @classmethod
    def blank_nickname_to_none(cls, value: object) -> object:
        """空白昵称按未填写处理；拒绝控制字符，避免数据库编码错误。"""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError("昵称不能包含控制字符")
        return value

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """bcrypt 只支持 72 字节以内的密码。"""
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"密码不能超过 {BCRYPT_MAX_BYTES} 字节")
        return value


class UserOut(BaseModel):
    """对外返回的用户信息，不包含密码哈希。"""

    id: int
    username: str
    nickname: str | None
    avatar_url: str | None
    role: str
    height_cm: int | None
    weight_kg: int | None
    usual_size: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
