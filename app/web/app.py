"""
Flask 应用工厂。

创建和配置 Flask 应用实例。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import flask
from flask import Flask, jsonify

from app.config import Settings
from app.crawler.hn_crawler import HnCrawler, KeywordCrawlStats
from app.crawler.playwright_fetcher import PlaywrightFetcher
from app.db.mysql import MySqlPool
from app.web.task_manager import KeywordCrawlResult, TaskManager, TaskStatus

logger = logging.getLogger(__name__)


class TaskWorker:
    """
    任务工作线程。

    从 TaskManager 获取待处理任务，并在后台执行爬虫。
    """

    def __init__(self, settings: Settings, db_pool: MySqlPool, task_manager: TaskManager):
        self._s = settings
        self._db = db_pool
        self._tm = task_manager
        self._running = True
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """启动工作线程。"""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="TaskWorker")
        self._thread.start()
        logger.info("任务工作线程已启动")

    def stop(self) -> None:
        """停止工作线程。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            logger.info("任务工作线程已停止")

    def _run_loop(self) -> None:
        """工作线程主循环。"""
        while self._running:
            task = self._tm.get_next_pending_task()
            if task:
                with self._lock:
                    self._execute_task(task)
            else:
                time.sleep(1)

    def _execute_task(self, task: Any) -> None:
        """执行单个任务。"""
        task_id = task.task_id
        keywords = task.keywords
        force_restart = task.force_restart  # 获取是否强制重新开始

        logger.info("开始执行任务：task_id=%s keywords=%s force_restart=%s", task_id, keywords, force_restart)

        # 更新状态为运行中
        self._tm.update_task_status(task_id, TaskStatus.RUNNING, keyword_index=0)
        restart_mode = "重新爬取" if force_restart else "断点续爬"
        self._tm.append_log(task_id, f"任务开始执行（{restart_mode}），共 {len(keywords)} 个关键词")

        results = []
        error = None

        for idx, keyword in enumerate(keywords):
            # 检查是否已停止
            if not self._running:
                self._tm.update_task_status(task_id, TaskStatus.CANCELLED)
                self._tm.append_log(task_id, "任务已取消")
                return

            # 更新当前进度
            self._tm.update_task_status(
                task_id,
                TaskStatus.RUNNING,
                current_keyword=keyword,
                keyword_index=idx,
            )
            self._tm.append_log(task_id, f"[{idx + 1}/{len(keywords)}] 开始爬取关键词：{keyword}")

            try:
                # 创建爬虫实例
                crawler = HnCrawler(self._s, self._db)

                # 执行爬取（传递 force_restart 参数）
                stats = crawler.crawl_keyword(keyword, force_restart=force_restart)

                # 转换结果
                result = KeywordCrawlResult(
                    keyword=stats.keyword,
                    pages_total=stats.pages_total,
                    pages_fetched=stats.pages_fetched,
                    rows_parsed=stats.rows_parsed,
                    rows_upserted=stats.rows_upserted,
                    blocked=stats.blocked,
                    blocked_reason=stats.blocked_reason,
                )
                results.append(result)
                self._tm.add_result(task_id, result)

                # 记录结果
                log_msg = f"[{idx + 1}/{len(keywords)}] {keyword} 完成"
                if stats.blocked:
                    log_msg += f"（被拦截：{stats.blocked_reason}）"
                else:
                    log_msg += f"（{stats.pages_fetched}/{stats.pages_total} 页，{stats.rows_upserted} 条数据）"
                self._tm.append_log(task_id, log_msg)

                # 关闭爬虫
                crawler.close()

            except Exception as e:
                logger.exception("爬取关键词失败：keyword=%s error=%s", keyword, e)
                self._tm.append_log(task_id, f"[{idx + 1}/{len(keywords)}] {keyword} 失败：{str(e)}")
                # 继续处理下一个关键词

        # 任务完成
        final_status = TaskStatus.COMPLETED
        final_msg = f"任务完成，共处理 {len(keywords)} 个关键词"
        if error:
            final_status = TaskStatus.FAILED
            final_msg = f"任务失败：{error}"

        self._tm.update_task_status(
            task_id,
            final_status,
            keyword_index=len(keywords),
            error=error,
        )
        self._tm.append_log(task_id, final_msg)

        logger.info("任务执行完成：task_id=%s status=%s", task_id, final_status.value)


def create_flask_app(
    settings: Settings,
    db_pool: MySqlPool,
    task_manager: TaskManager,
) -> Flask:
    """
    创建 Flask 应用实例。

    Args:
        settings: 应用配置
        db_pool: 数据库连接池
        task_manager: 任务管理器

    Returns:
        Flask 应用实例
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["JSON_AS_ASCII"] = False  # 支持中文 JSON

    # 创建任务工作线程
    task_worker = TaskWorker(settings, db_pool, task_manager)
    task_worker.start()

    # 保存到 app context，供路由使用
    app.config["TASK_MANAGER"] = task_manager
    app.config["TASK_WORKER"] = task_worker

    # 注册路由
    from app.web import routes

    routes.init_routes(app, settings, task_manager)

    # 健康检查
    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok", "service": "FeatherFlow Web"})

    logger.info("Flask 应用创建成功")

    return app


def run_flask_in_thread(
    app: Flask,
    host: str,
    port: int,
    debug: bool = False,
) -> None:
    """
    在后台线程中运行 Flask 应用。

    Args:
        app: Flask 应用实例
        host: 监听地址
        port: 监听端口
        debug: 调试模式
    """
    # 禁用 Flask 的重载器（在后台线程中不兼容）
    app.run(host=host, port=port, debug=debug, use_reloader=False)
