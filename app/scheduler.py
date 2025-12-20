"""
调度模块：APScheduler 常驻调度（代码层面定时）。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerHandle:
    """用于对外暴露 scheduler 句柄，便于后续扩展（如健康检查/优雅停止）。"""

    scheduler: BackgroundScheduler


def _parse_cron(cron_expr: str) -> CronTrigger:
    """
    解析五段式 cron：min hour day month day_of_week

    例：\"30 8 * * *\" => 每天 08:30
    """
    parts = (cron_expr or "").split()
    if len(parts) != 5:
        raise ValueError(f"CRON 格式错误，期望 5 段(min hour day month day_of_week)，实际：{cron_expr!r}")

    minute, hour, day, month, day_of_week = parts
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)


def start_scheduler(
    cron_expr: str,
    job_func,
    run_on_start: bool = True,
) -> SchedulerHandle:
    """
    启动 APScheduler。

    :param cron_expr: 五段式 cron
    :param job_func: 任务函数（无参）
    :param run_on_start: 是否启动后立即执行一次
    """
    scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={
            # 性能/稳定性：避免任务堆积导致频繁补跑
            "coalesce": True,
            "max_instances": 1,
        },
    )

    def _wrapped_job() -> None:
        start = time.time()
        logger.info("定时任务开始执行")
        try:
            job_func()
        finally:
            cost_ms = int((time.time() - start) * 1000)
            logger.info("定时任务执行结束，耗时=%sms", cost_ms)

    trigger = _parse_cron(cron_expr)
    scheduler.add_job(
        func=_wrapped_job,
        trigger=trigger,
        id="hn_market_crawler_job",
        name="惠农网行情抓取任务",
        replace_existing=True,
        misfire_grace_time=300,  # 容忍 5 分钟错过触发
    )

    scheduler.start()
    logger.info("APScheduler 已启动，cron=%s", cron_expr)

    if run_on_start:
        try:
            logger.info("启动后立即执行一次任务（RUN_ON_START=1）")
            job_func()
        except Exception:
            logger.exception("启动即跑失败（不会影响 scheduler 常驻）")

    return SchedulerHandle(scheduler=scheduler)


