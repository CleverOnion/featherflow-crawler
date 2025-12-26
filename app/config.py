"""
配置模块：从环境变量读取运行参数。

说明：
- 优先读取 .env（若存在），便于本地/容器化部署；
- 生产环境推荐直接注入环境变量，避免在镜像/服务器落盘敏感信息。
"""

from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置（Pydantic v2）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---------- MySQL ----------
    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_database: str = Field(default="hn_market", alias="MYSQL_DATABASE")
    mysql_pool_size: int = Field(default=5, alias="MYSQL_POOL_SIZE")

    # ---------- 业务 ----------
    keywords: str = Field(default="鹅,玉米,豆粕", alias="KEYWORDS")

    # Cron（五段式：min hour day month day_of_week）
    cron: str = Field(default="30 8 * * *", alias="CRON")
    run_on_start: int = Field(default=1, alias="RUN_ON_START")

    # ---------- HTTP 抓取 ----------
    http_timeout_seconds: int = Field(default=20, alias="HTTP_TIMEOUT_SECONDS")
    http_retry_times: int = Field(default=2, alias="HTTP_RETRY_TIMES")
    http_min_delay_ms: int = Field(default=200, alias="HTTP_MIN_DELAY_MS")
    http_max_delay_ms: int = Field(default=600, alias="HTTP_MAX_DELAY_MS")

    # ---------- 退避 ----------
    backoff_base_seconds: int = Field(default=10, alias="BACKOFF_BASE_SECONDS")
    backoff_max_seconds: int = Field(default=600, alias="BACKOFF_MAX_SECONDS")
    blocked_max_retry: int = Field(default=2, alias="BLOCKED_MAX_RETRY")

    # ---------- Playwright 兜底 ----------
    enable_playwright_fallback: int = Field(default=1, alias="ENABLE_PLAYWRIGHT_FALLBACK")
    playwright_headless: int = Field(default=1, alias="PLAYWRIGHT_HEADLESS")

    # ---------- 日志 ----------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---------- Flask Web Server ----------
    flask_enabled: int = Field(default=1, alias="FLASK_ENABLED")
    flask_host: str = Field(default="0.0.0.0", alias="FLASK_HOST")
    flask_port: int = Field(default=5000, alias="FLASK_PORT")
    flask_debug: int = Field(default=0, alias="FLASK_DEBUG")

    def keyword_list(self) -> List[str]:
        """把 KEYWORDS 拆成列表，并做去重/去空。"""
        items = [x.strip() for x in (self.keywords or "").split(",")]
        return [x for x in items if x]


settings = Settings()


