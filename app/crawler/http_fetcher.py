"""
HTTP 抓取器（优先路径）。

目标：
- 轻量、稳定、低触发反爬概率
- 内置重试、超时、限速抖动（performance + anti-ban）
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpFetchResult:
    url: str
    final_url: str
    status_code: int
    text: str


def _sleep_jitter(min_delay_ms: int, max_delay_ms: int) -> None:
    """随机延迟（毫秒），降低请求特征。"""
    if max_delay_ms <= 0:
        return
    lo = max(min_delay_ms, 0)
    hi = max(max_delay_ms, lo)
    time.sleep(random.uniform(lo, hi) / 1000.0)


def _default_headers() -> Dict[str, str]:
    # 伪装成常见浏览器（不追求极致对抗，只做基础降低风控）
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Connection": "keep-alive",
    }


def fetch_html(
    url: str,
    timeout_seconds: int = 20,
    retry_times: int = 2,
    min_delay_ms: int = 200,
    max_delay_ms: int = 600,
    ua: Optional[str] = None,
) -> HttpFetchResult:
    """
    获取页面 HTML。

    :param url: 目标 URL
    :param timeout_seconds: 超时（秒）
    :param retry_times: 重试次数（网络异常/超时会重试）
    :param min_delay_ms: 请求间最小随机延迟（毫秒）
    :param max_delay_ms: 请求间最大随机延迟（毫秒）
    :param ua: 可选自定义 User-Agent（用于 UA 轮换）；若为 None 则使用默认 UA
    """
    headers = _default_headers()
    if ua:
        headers["User-Agent"] = ua
    last_exc: Optional[Exception] = None

    # 使用 Client 复用连接（性能优化）
    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(timeout_seconds),
    ) as client:
        for attempt in range(retry_times + 1):
            _sleep_jitter(min_delay_ms, max_delay_ms)
            try:
                resp = client.get(url)
                text = resp.text or ""
                return HttpFetchResult(
                    url=url,
                    final_url=str(resp.url),
                    status_code=int(resp.status_code),
                    text=text,
                )
            except Exception as e:
                last_exc = e
                logger.warning("HTTP 抓取失败，将重试：url=%s attempt=%s/%s err=%s", url, attempt + 1, retry_times + 1, repr(e))
                # 简单退避：线性等待
                time.sleep(min(2 * (attempt + 1), 10))

    # 走到这里说明全部失败
    raise RuntimeError(f"HTTP 抓取失败：url={url!r} err={last_exc!r}")


