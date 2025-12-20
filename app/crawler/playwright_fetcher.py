"""
Playwright 兜底抓取器（必要时启用）。

注意：
- Playwright 依赖浏览器安装（chromium），请参考 README。
- 无人值守场景下建议 headless=1。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaywrightFetchResult:
    url: str
    status_code: int
    text: str


class PlaywrightFetcher:
    """复用 Playwright/Browser 实例，避免每次启动浏览器造成性能损耗。"""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser = None

    def _ensure_started(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError("Playwright 未安装或不可用，请先安装依赖与浏览器") from e

        self._playwright = sync_playwright().start()
        # Chromium 通用性更强
        self._browser = self._playwright.chromium.launch(headless=self._headless)

    def close(self) -> None:
        """关闭资源（可在服务退出时调用）。"""
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
            self._playwright = None

    def restart(self) -> None:
        """
        重启浏览器实例。

        说明：
        - 仅关闭当前 Browser/Playwright 实例，不在此处立即重新启动；
        - 下次调用 fetch 时会通过 _ensure_started() 惰性重新 launch 一个全新的浏览器进程。
        """
        logger.info("重启 Playwright 浏览器实例（restart 被调用）")
        self.close()

    def fetch(self, url: str, timeout_ms: int = 20000) -> PlaywrightFetchResult:
        """
        打开页面并获取渲染后的 HTML。

        说明：
        - 仍然以 SSR HTML 为主；Playwright 在这里的价值主要是“更像真实浏览器”。
        """
        self._ensure_started()

        context = self._browser.new_context()

        # 性能优化：拦截图片/媒体/字体
        def _route(route):
            r = route.request
            if r.resource_type in ("image", "media", "font"):
                return route.abort()
            return route.continue_()

        context.route("**/*", _route)

        page = context.new_page()
        status_code: int = 0
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if resp is not None:
                status_code = int(resp.status or 0)
            html = page.content() or ""
            return PlaywrightFetchResult(url=url, status_code=status_code, text=html)
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass


