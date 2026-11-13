"""集中导入所有 ORM 模型，供 Alembic 发现元数据。"""

from app.modules.auth.models import User  # noqa: F401
from app.modules.catalog.models import (  # noqa: F401
    Category,
    Favorite,
    Product,
    ProductSku,
)

__all__ = ["User", "Category", "Product", "ProductSku", "Favorite"]
