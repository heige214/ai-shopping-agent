import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.commerce.router import router as commerce_router
from app.modules.commerce.timeouts import order_timeout_loop
from app.modules.support.router import router as support_router

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时探测数据库并启动超时订单扫描，关闭时释放资源。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("数据库连接正常")
    except Exception:
        logger.exception("数据库连接失败，健康检查将返回 503")

    timeout_task = asyncio.create_task(order_timeout_loop())
    try:
        yield
    finally:
        timeout_task.cancel()
        try:
            await timeout_task
        except asyncio.CancelledError:
            pass
        await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(catalog_router, prefix=settings.api_prefix)
app.include_router(commerce_router, prefix=settings.api_prefix)
app.include_router(support_router, prefix=settings.api_prefix)
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR, check_dir=False),
    name="static",
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError) -> JSONResponse:
    """校验失败时不回显用户提交值，避免密码出现在响应或日志中。"""
    errors = []
    for error in exc.errors():
        error = dict(error)
        error.pop("input", None)
        errors.append(error)
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


@app.get(f"{settings.api_prefix}/health")
async def health_check() -> JSONResponse:
    """健康检查：同时确认服务与数据库可用。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "down"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
