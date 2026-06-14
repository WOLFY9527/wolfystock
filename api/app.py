# -*- coding: utf-8 -*-
"""
===================================
FastAPI 应用工厂模块
===================================

职责：
1. 创建和配置 FastAPI 应用实例
2. 配置 CORS 中间件
3. 注册路由和异常处理器
4. 托管前端静态文件（生产模式）

使用方式：
    from api.app import create_app
    app = create_app()
"""

import mimetypes
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, Tuple

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy import text

from api.deps import resolve_current_user
from api.v1 import api_v1_router
from api.middlewares.auth import add_auth_middleware
from api.middlewares.error_handler import add_error_handlers
from api.security_headers import apply_security_headers
from api.v1.schemas.common import HealthResponse
from src.storage import get_db
from src.auth import is_auth_enabled, is_production_mode
from src.services.system_config_service import SystemConfigService
from src.services.crypto_realtime_service import get_crypto_realtime_service, should_auto_start_crypto_realtime
from src.services.task_queue import get_task_queue

logger = logging.getLogger(__name__)

_ROOT_OPENAPI_PATH = "/openapi.json"
_ROOT_SWAGGER_PATH = "/docs"
_ROOT_SWAGGER_OAUTH2_REDIRECT_PATH = "/docs/oauth2-redirect"
_ROOT_REDOC_PATH = "/redoc"
_SAFE_PUBLIC_READINESS_STATES = {"ready", "degraded", "unavailable", "maintenance", "unknown"}


def _iso_now() -> str:
    return datetime.now().isoformat()


def _add_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        return apply_security_headers(response, request)


def _docs_auth_error_response(request: Request, *, status_code: int, error: str, message: str) -> JSONResponse:
    return apply_security_headers(
        JSONResponse(
            status_code=status_code,
            content={"error": error, "message": message},
        ),
        request,
    )


def _require_docs_admin_user(request: Request):
    if not is_auth_enabled():
        return None

    current_user = resolve_current_user(request)
    if current_user is None:
        return _docs_auth_error_response(
            request,
            status_code=401,
            error="unauthorized",
            message="Login required",
        )
    if not current_user.is_admin:
        return _docs_auth_error_response(
            request,
            status_code=403,
            error="admin_required",
            message="Admin access required",
        )
    return None


def _build_health_payload(
    *,
    mode: str,
    ready: bool,
    checks: Optional[Dict[str, Dict[str, Any]]] = None,
    warnings: Optional[list[str]] = None,
) -> Dict[str, Any]:
    return {
        "status": "ok" if ready else "not_ready",
        "timestamp": _iso_now(),
        "service": "daily-stock-analysis-api",
        "mode": mode,
        "ready": ready,
        "checks": checks or {},
        "warnings": warnings or [],
    }


def _build_public_health_payload(*, mode: str, status: str, ready: bool) -> Dict[str, Any]:
    return {
        "status": status,
        "timestamp": _iso_now(),
        "service": "daily-stock-analysis-api",
        "mode": mode,
        "ready": ready,
    }


def _project_public_readiness_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        checks = {}

    check_statuses = {
        name: check.get("status")
        for name, check in checks.items()
        if isinstance(check, dict)
    }
    unknown_status = any(
        status not in {"ok", "not_ready", "maintenance"}
        for status in check_statuses.values()
    )
    ready = bool(payload.get("ready")) and not unknown_status

    if unknown_status:
        public_state = "unknown"
    elif any(status == "maintenance" for status in check_statuses.values()):
        public_state = "maintenance"
    elif ready and payload.get("warnings"):
        public_state = "degraded"
    elif ready:
        public_state = "ready"
    elif any(
        check_statuses.get(name) == "not_ready"
        for name in ("system_config", "storage")
    ):
        public_state = "unavailable"
    elif any(status == "not_ready" for status in check_statuses.values()):
        public_state = "degraded"
    else:
        public_state = "unknown"

    if public_state not in _SAFE_PUBLIC_READINESS_STATES:
        public_state = "unknown"

    return _build_public_health_payload(
        mode="ready",
        status=public_state,
        ready=public_state == "ready",
    )


def _storage_readiness_check() -> Tuple[bool, Dict[str, Any]]:
    try:
        db = get_db()
        session = db.get_session()
        try:
            session.execute(text("SELECT 1"))
        finally:
            session.close()
        return True, {"status": "ok", "detail": "storage session responded to SELECT 1"}
    except Exception:
        return False, {"status": "not_ready", "detail": "storage check failed"}


def _task_queue_readiness_check(app: FastAPI) -> Tuple[bool, Dict[str, Any], list[str]]:
    try:
        queue = getattr(app.state, "task_queue", None) or get_task_queue()
        runtime = queue.get_runtime_status()
    except Exception:
        return False, {"status": "not_ready", "detail": "task queue check failed"}, []

    ready = bool(runtime.get("topology_ok", True)) and not bool(runtime.get("shutdown"))
    detail = "task queue ready"
    warning = runtime.get("warning")
    warnings = [warning] if warning else []
    if bool(runtime.get("shutdown")):
        detail = "task queue is shutting down"
        status = "maintenance"
    elif not bool(runtime.get("topology_ok", True)):
        detail = (
            "process-local task queue requires single-process API deployment "
            f"(configured_worker_count={runtime.get('configured_worker_count')})"
        )
        status = "not_ready"
    else:
        status = "ok"

    return ready, {
        "status": status,
        "detail": detail,
        "mode": runtime.get("mode"),
        "single_process_required": runtime.get("single_process_required"),
        "configured_worker_count": runtime.get("configured_worker_count"),
        "worker_hints": runtime.get("worker_hints"),
    }, warnings


def _readiness_payload(app: FastAPI) -> Tuple[int, Dict[str, Any]]:
    checks: Dict[str, Dict[str, Any]] = {}
    warnings: list[str] = []
    ready = True

    system_config_ready = hasattr(app.state, "system_config_service")
    checks["system_config"] = {
        "status": "ok" if system_config_ready else "not_ready",
        "detail": "SystemConfigService initialized" if system_config_ready else "SystemConfigService missing from app state",
    }
    ready = ready and system_config_ready

    storage_ready, storage_check = _storage_readiness_check()
    checks["storage"] = storage_check
    ready = ready and storage_ready

    task_queue_ready, task_queue_check, task_queue_warnings = _task_queue_readiness_check(app)
    checks["task_queue"] = task_queue_check
    ready = ready and task_queue_ready
    warnings.extend(task_queue_warnings)

    payload = _build_health_payload(mode="ready", ready=ready, checks=checks, warnings=warnings)
    return (200 if ready else 503), payload


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Initialize and release shared services for the app lifecycle."""
    app.state.system_config_service = SystemConfigService()
    app.state.task_queue = get_task_queue()
    if should_auto_start_crypto_realtime():
        app.state.crypto_realtime_service = get_crypto_realtime_service(auto_start=True)
    runtime = app.state.task_queue.get_runtime_status()
    if not runtime.get("topology_ok", True):
        logger.warning("[App] Task queue topology warning: %s", runtime.get("warning"))
    try:
        yield
    finally:
        if hasattr(app.state, "task_queue"):
            app.state.task_queue.shutdown(wait=False, cancel_futures=True)
            delattr(app.state, "task_queue")
        if hasattr(app.state, "crypto_realtime_service"):
            app.state.crypto_realtime_service.stop()
            delattr(app.state, "crypto_realtime_service")
        if hasattr(app.state, "system_config_service"):
            delattr(app.state, "system_config_service")


def create_app(static_dir: Optional[Path] = None) -> FastAPI:
    """
    创建并配置 FastAPI 应用实例
    
    Args:
        static_dir: 静态文件目录路径（可选，默认为项目根目录下的 static）
        
    Returns:
        配置完成的 FastAPI 应用实例
    """
    # 默认静态文件目录
    if static_dir is None:
        static_dir = Path(__file__).parent.parent / "static"
    
    # 创建 FastAPI 实例
    app = FastAPI(
        title="Daily Stock Analysis API",
        description=(
            "A股/港股/美股自选股智能分析系统 API\n\n"
            "## 功能模块\n"
            "- 股票分析：触发 AI 智能分析\n"
            "- 历史记录：查询历史分析报告\n"
            "- 股票数据：获取行情数据\n\n"
            "## 认证方式\n"
            "支持可选的运行时认证（通过 WebUI 设置页面启用/关闭）"
        ),
        version="1.0.0",
        lifespan=app_lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    
    # ============================================================
    # CORS 配置
    # ============================================================
    
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # 从环境变量添加额外的允许来源
    extra_origins = os.environ.get("CORS_ORIGINS", "")
    explicit_origins = [o.strip() for o in extra_origins.split(",") if o.strip()]
    if extra_origins:
        allowed_origins.extend(explicit_origins)
    
    # 允许所有来源（开发/演示用）
    allow_all_origins = os.environ.get("CORS_ALLOW_ALL", "").lower() == "true"
    if is_production_mode() and allow_all_origins:
        raise RuntimeError("CORS_ALLOW_ALL is not allowed in production")
    if is_production_mode() and not explicit_origins:
        raise RuntimeError("CORS_ORIGINS must be explicitly configured in production")
    allow_credentials = not allow_all_origins
    if allow_all_origins:
        allowed_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _add_security_headers(app)
    add_auth_middleware(app)
    
    # ============================================================
    # 注册路由
    # ============================================================
    
    app.include_router(api_v1_router)
    add_error_handlers(app)

    @app.get(_ROOT_OPENAPI_PATH, include_in_schema=False)
    async def openapi_schema(request: Request):
        auth_error = _require_docs_admin_user(request)
        if auth_error is not None:
            return auth_error
        return JSONResponse(app.openapi())

    @app.get(_ROOT_SWAGGER_PATH, include_in_schema=False)
    async def swagger_ui(request: Request):
        auth_error = _require_docs_admin_user(request)
        if auth_error is not None:
            return auth_error
        return get_swagger_ui_html(
            openapi_url=_ROOT_OPENAPI_PATH,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=_ROOT_SWAGGER_OAUTH2_REDIRECT_PATH,
        )

    @app.get(_ROOT_SWAGGER_OAUTH2_REDIRECT_PATH, include_in_schema=False)
    async def swagger_ui_oauth2_redirect(request: Request):
        auth_error = _require_docs_admin_user(request)
        if auth_error is not None:
            return auth_error
        return get_swagger_ui_oauth2_redirect_html()

    @app.get(_ROOT_REDOC_PATH, include_in_schema=False)
    async def redoc_html(request: Request):
        auth_error = _require_docs_admin_user(request)
        if auth_error is not None:
            return auth_error
        return get_redoc_html(
            openapi_url=_ROOT_OPENAPI_PATH,
            title=f"{app.title} - ReDoc",
        )
    
    # ============================================================
    # 根路由和健康检查
    # ============================================================
    
    has_frontend = static_dir.exists() and (static_dir / "index.html").exists()
    
    if has_frontend:
        @app.get("/", include_in_schema=False)
        async def root():
            """根路由 - 返回前端页面"""
            return FileResponse(static_dir / "index.html")
    else:
        _FRONTEND_NOT_BUILT_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DSA - Frontend Not Built</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#0a0e17;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,monospace}
  .card{max-width:580px;padding:2.5rem;border:1px solid #1e293b;border-radius:12px;background:#111827}
  h1{font-size:1.25rem;color:#38bdf8;margin-bottom:.75rem}
  p{font-size:.9rem;line-height:1.7;color:#94a3b8;margin-bottom:.5rem}
  code{background:#1e293b;padding:2px 8px;border-radius:4px;font-size:.85rem;color:#67e8f9}
  .hint{margin-top:1.25rem;padding:.75rem 1rem;border-left:3px solid #f59e0b;background:#1c1917;border-radius:0 6px 6px 0}
  .hint p{color:#fbbf24;margin:0}
  a{color:#38bdf8;text-decoration:none}
  a:hover{text-decoration:underline}
  .status{margin-top:1rem;font-size:.8rem;color:#475569}
</style></head><body><div class="card">
<h1>&#9888;&#65039; Frontend Not Built</h1>
<p>API is running, but the Web UI has not been built yet.</p>
<p>Build the frontend first:</p>
<p><code>cd apps/dsa-web &amp;&amp; npm install &amp;&amp; npm run build</code></p>
<p>Or start with auto-build:</p>
<p><code>python main.py --serve-only</code></p>
<div class="hint"><p>Interactive API docs are available at <a href="/docs">/docs</a> and follow the current admin auth setting.</p></div>
<p class="status">API Version 1.0.0 &bull; <a href="/api/health">/api/health</a></p>
</div></body></html>"""

        @app.get("/", include_in_schema=False)
        async def root():
            """根路由 - 前端未构建时返回引导页面"""
            return HTMLResponse(content=_FRONTEND_NOT_BUILT_HTML)
    
    @app.get(
        "/api/health/live",
        response_model=HealthResponse,
        response_model_exclude_none=True,
        tags=["Health"],
        summary="存活检查",
        description="用于判断 API 进程是否存活"
    )
    async def live_health_check() -> HealthResponse:
        """Liveness endpoint: cheap and process-local."""
        return HealthResponse(**_build_public_health_payload(mode="live", status="ok", ready=True))

    @app.get(
        "/api/health/ready",
        response_model=HealthResponse,
        response_model_exclude_none=True,
        tags=["Health"],
        summary="就绪检查",
        description="用于判断 API 是否已准备好承接流量"
    )
    async def ready_health_check():
        """Readiness endpoint: validates core runtime dependencies."""
        status_code, payload = _readiness_payload(app)
        return JSONResponse(status_code=status_code, content=_project_public_readiness_payload(payload))

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        response_model_exclude_none=True,
        tags=["Health"],
        summary="健康检查",
        description="默认健康检查，返回就绪状态"
    )
    async def health_check():
        """Compatibility alias for readiness checks."""
        status_code, payload = _readiness_payload(app)
        return JSONResponse(status_code=status_code, content=_project_public_readiness_payload(payload))
    
    # ============================================================
    # 静态文件托管（前端 SPA）
    # ============================================================
    
    if has_frontend:
        # 挂载静态资源目录
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        
        # SPA 路由回退
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(request: Request, full_path: str):
            """SPA 路由回退 - 非 API 路由返回 index.html"""
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"error": "not_found", "message": f"API endpoint /{full_path} not found"}
                )

            file_path = static_dir / full_path
            if file_path.exists() and file_path.is_file():
                # Issue #520: Explicitly resolve MIME type to avoid
                # browsers rejecting JS modules served as text/plain.
                content_type, _ = mimetypes.guess_type(str(file_path))
                return FileResponse(file_path, media_type=content_type)

            return FileResponse(static_dir / "index.html")
    
    return app


# 默认应用实例（供 uvicorn 直接使用）
app = create_app()
