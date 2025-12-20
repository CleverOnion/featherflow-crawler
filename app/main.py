"""
程序入口：常驻服务 + APScheduler 定时。

运行：
    python -m app.main
"""

from __future__ import annotations

import logging
import signal
import threading
import time

from app.config import settings
from app.crawler.hn_crawler import HnCrawler
from app.db.mysql import MySqlPool, init_schema
from app.logging_config import setup_logging
from app.scheduler import start_scheduler

logger = logging.getLogger(__name__)

_db_pool: MySqlPool | None = None


def _get_db_pool() -> MySqlPool:
    """延迟创建 DB 连接池，避免启动阶段因短暂抖动直接崩溃。"""
    global _db_pool
    if _db_pool is None:
        _db_pool = MySqlPool(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            pool_size=settings.mysql_pool_size,
        )
    return _db_pool


def job_entry() -> None:
    """
    定时任务入口（后续会在这里串起来：DB 检查 -> 抓取 -> 解析 -> 入库）。

    这里先留空实现，保证服务骨架可启动。
    """
    crawler = HnCrawler(settings=settings, db_pool=_get_db_pool())
    try:
        keywords = settings.keyword_list()
        if not keywords:
            logger.warning("未配置 KEYWORDS，任务直接返回")
            return

        logger.info("任务开始：keywords=%s", ",".join(keywords))
        for kw in keywords:
            try:
                stats = crawler.crawl_keyword(kw)
                logger.info(
                    "关键词任务结束：keyword=%s pages=%s fetched=%s parsed=%s upserted=%s blocked=%s reason=%s",
                    stats.keyword,
                    stats.pages_total,
                    stats.pages_fetched,
                    stats.rows_parsed,
                    stats.rows_upserted,
                    stats.blocked,
                    stats.blocked_reason,
                )
            except Exception:
                logger.exception("关键词任务异常：keyword=%s", kw)
        logger.info("任务结束")
    finally:
        crawler.close()


def _wait_forever(stop_event: threading.Event) -> None:
    """保持主线程常驻，直到收到退出信号。"""
    while not stop_event.is_set():
        time.sleep(1)


def main() -> None:
    setup_logging(settings.log_level)
    logger.info("服务启动：惠农网行情定时爬虫（无人值守）")

    # 尝试初始化 MySQL 表结构（失败不阻塞常驻，但会记录错误；后续任务执行时会再尝试）
    try:
        init_schema(_get_db_pool())
    except Exception:
        logger.exception("MySQL 初始化失败：请检查 MYSQL_* 配置与权限（服务仍会常驻）")

    stop_event = threading.Event()

    def _handle_signal(signum, _frame) -> None:
        logger.info("收到退出信号：%s，准备退出", signum)
        stop_event.set()

    # Linux 常用信号
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # 启动 scheduler
    handle = start_scheduler(
        cron_expr=settings.cron,
        job_func=job_entry,
        run_on_start=bool(settings.run_on_start),
    )

    try:
        _wait_forever(stop_event)
    finally:
        try:
            handle.scheduler.shutdown(wait=False)
        except Exception:
            logger.exception("scheduler 关闭失败")
        logger.info("服务已退出")


if __name__ == "__main__":
    main()


