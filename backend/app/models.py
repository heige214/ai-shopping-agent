"""集中导入所有 ORM 模型，供 Alembic 发现元数据。"""

from app.modules.auth.models import User  # noqa: F401

__all__ = ["User"]
