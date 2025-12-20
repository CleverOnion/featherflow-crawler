"""
惠农网行情抓取主流程（分页 + 退避 + 入库）。
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.config import Settings
from app.crawler.block_detector import detect_blocked
from app.crawler.http_fetcher import fetch_html
from app.crawler.playwright_fetcher import PlaywrightFetcher
from app.db.mysql import MySqlPool, PriceRow, exists_today, upsert_rows
from app.parser.hn_parser import extract_total_pages, parse_market_list

logger = logging.getLogger(__name__)


# UA 池：可根据需要扩充/调整
UA_POOL: List[str] = [
    # 常见桌面 Chrome
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    ),
    # 常见桌面 Firefox
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
        "Gecko/20100101 Firefox/120.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) "
        "Gecko/20100101 Firefox/119.0"
    ),
]


@dataclass(frozen=True)
class KeywordCrawlStats:
    keyword: str
    pages_total: int
    pages_fetched: int
    rows_parsed: int
    rows_upserted: int
    blocked: bool
    blocked_reason: Optional[str]


def _backoff_seconds(base: int, max_seconds: int, attempt: int) -> int:
    """指数退避（带上限）。"""
    if base <= 0:
        base = 1
    sec = base * (2**attempt)
    return min(sec, max(max_seconds, 1))


def _build_search_url(keyword: str) -> str:
    """构建关键词搜索 URL。"""
    return f"https://www.cnhnb.com/hangqing/?k={quote(keyword)}"


def _derive_page_urls(first_url: str, first_html: str, total_pages: int) -> List[str]:
    """
    根据第一页 HTML 推导分页 URL 列表。

    优先级：
    1) 从分页控件 `a.number[href]` 推导 cdlist 模板（最可靠）；
    2) 若 URL 是 ?k=xxx，则使用 page 参数模板（经验做法）。
    """
    total_pages = max(int(total_pages or 1), 1)
    if total_pages == 1:
        return [first_url]

    soup = BeautifulSoup(first_html, "lxml")
    pager_links = soup.select(".quotation-paging .eye-pager a.number[href]")
    for a in pager_links:
        href = a.get("href") or ""
        href = href.strip()
        if not href:
            continue
        # 例：/hangqing/cdlist-2001182-0-0-0-0-3/
        if "cdlist-" in href and href.rstrip("/").split("-")[-1].isdigit():
            prefix = href.rstrip("/")
            prefix = prefix[: prefix.rfind("-") + 1]  # 保留到最后一个 '-'（含）
            return [f"https://www.cnhnb.com{prefix}{i}/" for i in range(1, total_pages + 1)]

    # 兜底：关键词页分页（不保证一定有效，但尽量覆盖可能情况）
    parsed = urlparse(first_url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "k" in q:
        urls: List[str] = []
        for i in range(1, total_pages + 1):
            q2 = dict(q)
            q2["page"] = str(i)
            new_query = urlencode(q2, doseq=True)
            urls.append(urlunparse(parsed._replace(query=new_query)))
        return urls

    # 最后兜底：只返回第一页，避免构造错误 URL
    return [first_url]


class HnCrawler:
    def __init__(self, settings: Settings, db_pool: MySqlPool) -> None:
        self._s = settings
        self._db = db_pool
        self._pw: Optional[PlaywrightFetcher] = None
        # 当前 UA 索引（在每次 crawl_keyword 开始时重新初始化）
        self._ua_index: int = 0

    def _get_pw(self) -> PlaywrightFetcher:
        if self._pw is None:
            self._pw = PlaywrightFetcher(headless=bool(self._s.playwright_headless))
        return self._pw

    def close(self) -> None:
        if self._pw is not None:
            try:
                self._pw.close()
            except Exception:
                logger.exception("关闭 Playwright 失败")
            self._pw = None

    # === UA 轮换相关 ===

    def _current_ua(self) -> Optional[str]:
        """返回当前 UA；若 UA_POOL 为空则返回 None（退化为默认 UA）。"""
        if not UA_POOL:
            return None
        # 防御性处理索引越界
        idx = max(min(self._ua_index, len(UA_POOL) - 1), 0)
        return UA_POOL[idx]

    def _rotate_ua(self, reason: str, url: str | None = None) -> None:
        """在疑似被拦截时轮换到下一个 UA。"""
        if not UA_POOL:
            return
        old_index = self._ua_index
        self._ua_index = (self._ua_index + 1) % len(UA_POOL)
        logger.warning(
            "疑似反爬，切换 UA：old_index=%s new_index=%s url=%s reason=%s",
            old_index,
            self._ua_index,
            url,
            reason,
        )

    def _fetch_page_html(self, url: str) -> tuple[str, int, str]:
        """
        两级抓取：HTTP 优先；必要时 Playwright 兜底。
        返回：(html, status_code, reason)
        """
        http_res = fetch_html(
            url=url,
            timeout_seconds=self._s.http_timeout_seconds,
            retry_times=self._s.http_retry_times,
            min_delay_ms=self._s.http_min_delay_ms,
            max_delay_ms=self._s.http_max_delay_ms,
            ua=self._current_ua(),
        )
        decision = detect_blocked(http_res.text, http_res.status_code)
        if not decision.blocked:
            return http_res.text, http_res.status_code, "http_ok"

        # HTTP 判定为疑似反爬，先轮换 UA
        self._rotate_ua(decision.reason, url=url)

        if not bool(self._s.enable_playwright_fallback):
            return http_res.text, http_res.status_code, f"http_blocked:{decision.reason}"

        # Playwright 兜底
        pw = self._get_pw()
        pw_res = pw.fetch(url=url, timeout_ms=self._s.http_timeout_seconds * 1000)
        decision2 = detect_blocked(pw_res.text, pw_res.status_code)
        if decision2.blocked:
            # Playwright 仍被判定为反爬：重启浏览器实例，交由上层做退避
            try:
                pw.restart()
            except Exception:
                logger.exception("Playwright restart 失败")
            logger.warning(
                "Playwright 抓取仍疑似被拦截，已重启浏览器实例：url=%s reason=%s",
                url,
                decision2.reason,
            )
            return pw_res.text, pw_res.status_code, f"playwright_blocked:{decision2.reason}"
        return pw_res.text, pw_res.status_code, "playwright_ok"

    def crawl_keyword(self, keyword: str) -> KeywordCrawlStats:
        """
        抓取某个关键词的全部分页，并入库。
        """
        today = date.today()
        if exists_today(self._db, keyword=keyword, day=today):
            logger.info("关键词已存在当天数据，跳过：keyword=%s day=%s", keyword, today.isoformat())
            return KeywordCrawlStats(
                keyword=keyword,
                pages_total=0,
                pages_fetched=0,
                rows_parsed=0,
                rows_upserted=0,
                blocked=False,
                blocked_reason=None,
            )

        first_url = _build_search_url(keyword)

        # 为本次 keyword 初始化一个随机起点 UA 索引（若 UA_POOL 为空则保持默认 UA）
        if UA_POOL:
            self._ua_index = random.randrange(len(UA_POOL))

        # 退避/重试：对“疑似反爬”做有限次数重试；超过后本轮放弃该 keyword
        blocked_reason: Optional[str] = None
        first_html: Optional[str] = None
        for attempt in range(self._s.blocked_max_retry + 1):
            html, status, reason = self._fetch_page_html(first_url)
            decision = detect_blocked(html, status)
            if not decision.blocked:
                first_html = html
                blocked_reason = None
                break

            blocked_reason = reason
            sec = _backoff_seconds(self._s.backoff_base_seconds, self._s.backoff_max_seconds, attempt)
            logger.warning(
                "疑似反爬/验证码，准备退避：keyword=%s url=%s attempt=%s/%s reason=%s backoff=%ss",
                keyword,
                first_url,
                attempt + 1,
                self._s.blocked_max_retry + 1,
                reason,
                sec,
            )
            time.sleep(sec)

        if first_html is None:
            return KeywordCrawlStats(
                keyword=keyword,
                pages_total=0,
                pages_fetched=0,
                rows_parsed=0,
                rows_upserted=0,
                blocked=True,
                blocked_reason=blocked_reason,
            )

        total_pages = extract_total_pages(first_html) or 1
        page_urls = _derive_page_urls(first_url, first_html, total_pages)
        total_pages = len(page_urls)

        pages_fetched = 0
        rows_parsed = 0
        rows_upserted = 0

        for page_idx, page_url in enumerate(page_urls, start=1):
            html = first_html if page_idx == 1 else None
            if html is None:
                html, status, reason = self._fetch_page_html(page_url)
                decision = detect_blocked(html, status)
                if decision.blocked:
                    # 对后续分页不再重试，直接退避并结束该关键词（无人值守策略）
                    sec = _backoff_seconds(self._s.backoff_base_seconds, self._s.backoff_max_seconds, 0)
                    logger.warning(
                        "分页抓取疑似被拦截，停止该关键词并退避：keyword=%s page=%s/%s url=%s reason=%s backoff=%ss",
                        keyword,
                        page_idx,
                        total_pages,
                        page_url,
                        reason,
                        sec,
                    )
                    time.sleep(sec)
                    return KeywordCrawlStats(
                        keyword=keyword,
                        pages_total=total_pages,
                        pages_fetched=pages_fetched,
                        rows_parsed=rows_parsed,
                        rows_upserted=rows_upserted,
                        blocked=True,
                        blocked_reason=reason,
                    )

            pages_fetched += 1

            parsed = parse_market_list(html)
            if not parsed:
                # 若出现空页，通常表示分页不可用/页面结构变化；为避免无意义请求，直接停止
                logger.info("分页无数据，停止后续分页：keyword=%s page=%s/%s url=%s", keyword, page_idx, total_pages, page_url)
                break

            rows_parsed += len(parsed)
            now = datetime.now()
            to_save = [
                PriceRow(
                    keyword=keyword,
                    price_date=p.price_date,
                    product=p.product,
                    place=p.place,
                    price_raw=p.price_raw,
                    price_value=p.price_value,
                    price_unit=p.price_unit,
                    source_url=page_url,
                    crawled_at=now,
                )
                for p in parsed
            ]
            affected = upsert_rows(self._db, to_save)
            rows_upserted += len(to_save)
            logger.info(
                "分页入库完成：keyword=%s page=%s/%s parsed=%s upserted=%s affected=%s",
                keyword,
                page_idx,
                total_pages,
                len(parsed),
                len(to_save),
                affected,
            )

        return KeywordCrawlStats(
            keyword=keyword,
            pages_total=total_pages,
            pages_fetched=pages_fetched,
            rows_parsed=rows_parsed,
            rows_upserted=rows_upserted,
            blocked=False,
            blocked_reason=None,
        )


