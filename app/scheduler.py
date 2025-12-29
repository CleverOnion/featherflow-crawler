"""
调度模块：APScheduler 常驻调度（代码层面定时）。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerHandle:
    """用于对外暴露 scheduler 句柄，便于后续扩展（如健康检查/优雅停止）。"""

    scheduler: BackgroundScheduler


@dataclass
class JobConfig:
    """任务配置。"""
    cron_expr: str
    job_func: callable
    job_id: str
    job_name: str
    run_on_start: bool = False
    misfire_grace_time: int = 300


def _parse_cron(cron_expr: str) -> CronTrigger:
    """
    解析五段式 cron：min hour day month day_of_week

    例："30 8 * * *" => 每天 08:30
    """
    parts = (cron_expr or "").split()
    if len(parts) != 5:
        raise ValueError(f"CRON 格式错误，期望 5 段(min hour day month day_of_week)，实际：{cron_expr!r}")

    minute, hour, day, month, day_of_week = parts
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)


def _make_wrapped_job(job_func: callable, job_name: str) -> callable:
    """包装任务函数，添加日志和计时。"""
    def _wrapped_job() -> None:
        start = time.time()
        logger.info("定时任务开始执行：%s", job_name)
        try:
            job_func()
        finally:
            cost_ms = int((time.time() - start) * 1000)
            logger.info("定时任务执行结束：%s，耗时=%sms", job_name, cost_ms)
    return _wrapped_job


def start_scheduler(
    cron_expr: str,
    job_func,
    run_on_start: bool = True,
    integrity_check_job: Optional[JobConfig] = None,
) -> SchedulerHandle:
    """
    启动 APScheduler。

    :param cron_expr: 五段式 cron（主任务）
    :param job_func: 主任务函数（无参）
    :param run_on_start: 是否启动后立即执行一次主任务
    :param integrity_check_job: 数据完整性检查任务配置（可选）
    """
    scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={
            # 性能/稳定性：避免任务堆积导致频繁补跑
            "coalesce": True,
            "max_instances": 1,
        },
    )

    # 添加主任务（行情抓取）
    main_wrapped = _make_wrapped_job(job_func, "惠农网行情抓取任务")
    main_trigger = _parse_cron(cron_expr)
    scheduler.add_job(
        func=main_wrapped,
        trigger=main_trigger,
        id="hn_market_crawler_job",
        name="惠农网行情抓取任务",
        replace_existing=True,
        misfire_grace_time=300,  # 容忍 5 分钟错过触发
    )

    # 添加数据完整性检查任务（如果启用）
    if integrity_check_job is not None:
        check_wrapped = _make_wrapped_job(integrity_check_job.job_func, "数据完整性检查任务")
        check_trigger = _parse_cron(integrity_check_job.cron_expr)
        scheduler.add_job(
            func=check_wrapped,
            trigger=check_trigger,
            id=integrity_check_job.job_id,
            name=integrity_check_job.job_name,
            replace_existing=True,
            misfire_grace_time=integrity_check_job.misfire_grace_time,
        )
        logger.info("已添加数据完整性检查任务：cron=%s", integrity_check_job.cron_expr)

    scheduler.start()
    logger.info("APScheduler 已启动，主任务 cron=%s", cron_expr)

    if run_on_start:
        try:
            logger.info("启动后立即执行一次主任务（RUN_ON_START=1）")
            job_func()
        except Exception:
            logger.exception("启动即跑失败（不会影响 scheduler 常驻）")

    return SchedulerHandle(scheduler=scheduler)
