# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis - FastAPI 后端服务入口
===================================

职责：
1. 提供 RESTful API 服务
2. 配置 CORS 跨域支持
3. 健康检查接口
4. 托管前端静态文件（生产模式）

启动方式：
    uvicorn server:app --reload --host 0.0.0.0 --port 8000
    
    或使用 main.py:
    python main.py --serve-only      # 仅启动 API 服务
    python main.py --serve           # API 服务 + 执行分析
"""

import logging
import os

from src.config import setup_env, get_config
from src.logging_config import setup_logging
from src.webui_frontend import prepare_webui_frontend_assets

# 初始化环境变量与日志
setup_env()

config = get_config()
level_name = (config.log_level or "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

setup_logging(
    log_prefix="api_server",
    log_dir=config.log_dir,
    console_level=level,
    extra_quiet_loggers=['uvicorn', 'fastapi'],
)


def _prepare_frontend_assets_for_server_entrypoint() -> None:
    """Keep direct uvicorn startup aligned with main.py --serve-only."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        return
    if not prepare_webui_frontend_assets():
        logging.getLogger(__name__).warning(
            "Frontend static assets are not ready; API will start with the fallback page."
        )


_prepare_frontend_assets_for_server_entrypoint()

# 从 api.app 导入应用实例
from api.app import app  # noqa: E402

# 导出 app 供 uvicorn 使用
__all__ = ['app']


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
