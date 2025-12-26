"""
任务历史持久化层。

将任务信息保存到数据库，支持跨服务重启恢复。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from app.db.mysql import MySqlPool

logger = logging.getLogger(__name__)


def init_task_schema(db_pool: MySqlPool) -> None:
    """初始化任务相关的数据库表。"""
    from app.db.schema_tasks import TASKS_SCHEMA

    try:
        with db_pool.connection() as conn:
            with conn.cursor() as cursor:
                for statement in TASKS_SCHEMA.split(";"):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
            logger.info("任务表初始化成功")
    except Exception as e:
        logger.error("任务表初始化失败: %s", e)
        raise


class TaskRepository:
    """任务历史数据访问层。"""

    def __init__(self, db_pool: MySqlPool):
        self._db = db_pool

    def save_task(
        self,
        task_id: str,
        keywords: List[str],
        status: str,
        created_at: datetime,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        current_keyword: Optional[str] = None,
        keyword_index: int = 0,
        total_keywords: int = 0,
        error: Optional[str] = None,
        result_summary: Optional[str] = None,
    ) -> bool:
        """
        保存或更新任务信息。

        Args:
            task_id: 任务 ID
            keywords: 关键词列表
            status: 状态
            created_at: 创建时间
            started_at: 开始时间
            completed_at: 完成时间
            current_keyword: 当前关键词
            keyword_index: 当前索引
            total_keywords: 总关键词数
            error: 错误信息
            result_summary: 结果摘要（JSON 字符串）

        Returns:
            是否成功
        """
        try:
            with self._db.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO hn_crawl_tasks (
                            task_id, keywords, status, created_at, started_at, completed_at,
                            current_keyword, keyword_index, total_keywords, error, result_summary
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON DUPLICATE KEY UPDATE
                            status = VALUES(status),
                            started_at = VALUES(started_at),
                            completed_at = VALUES(completed_at),
                            current_keyword = VALUES(current_keyword),
                            keyword_index = VALUES(keyword_index),
                            error = VALUES(error),
                            result_summary = VALUES(result_summary)
                        """,
                        (
                            task_id,
                            ",".join(keywords),
                            status,
                            created_at,
                            started_at,
                            completed_at,
                            current_keyword,
                            keyword_index,
                            total_keywords,
                            error,
                            result_summary,
                        ),
                    )
                return True
        except Exception as e:
            logger.error("保存任务失败: task_id=%s error=%s", task_id, e)
            return False

    def save_task_log(self, task_id: str, log_message: str) -> bool:
        """保存任务日志。"""
        try:
            with self._db.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO hn_task_logs (task_id, log_message)
                        VALUES (%s, %s)
                        """,
                        (task_id, log_message),
                    )
                return True
        except Exception as e:
            logger.error("保存任务日志失败: task_id=%s error=%s", task_id, e)
            return False

    def get_task_logs(self, task_id: str, limit: int = 100) -> List[str]:
        """获取任务日志。"""
        try:
            with self._db.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT log_message FROM hn_task_logs
                        WHERE task_id = %s
                        ORDER BY created_at ASC
                        LIMIT %s
                        """,
                        (task_id, limit),
                    )
                    rows = cursor.fetchall()
                    return [row[0] for row in rows] if rows else []
        except Exception as e:
            logger.error("获取任务日志失败: task_id=%s error=%s", task_id, e)
            return []

    def list_recent_tasks(self, limit: int = 20) -> List[dict]:
        """
        列出最近的任务。

        Returns:
            任务字典列表
        """
        try:
            with self._db.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT task_id, keywords, status, created_at, started_at, completed_at,
                               current_keyword, keyword_index, total_keywords, error, result_summary
                        FROM hn_crawl_tasks
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = cursor.fetchall()
                    tasks = []
                    for row in rows:
                        tasks.append({
                            "task_id": row[0],
                            "keywords": row[1],
                            "status": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "started_at": row[4].isoformat() if row[4] else None,
                            "completed_at": row[5].isoformat() if row[5] else None,
                            "current_keyword": row[6],
                            "keyword_index": row[7],
                            "total_keywords": row[8],
                            "error": row[9],
                            "result_summary": row[10],
                        })
                    return tasks
        except Exception as e:
            logger.error("列出最近任务失败: error=%s", e)
            return []

    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务详情。"""
        try:
            with self._db.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT task_id, keywords, status, created_at, started_at, completed_at,
                               current_keyword, keyword_index, total_keywords, error, result_summary
                        FROM hn_crawl_tasks
                        WHERE task_id = %s
                        """,
                        (task_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        return {
                            "task_id": row[0],
                            "keywords": row[1],
                            "status": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "started_at": row[4].isoformat() if row[4] else None,
                            "completed_at": row[5].isoformat() if row[5] else None,
                            "current_keyword": row[6],
                            "keyword_index": row[7],
                            "total_keywords": row[8],
                            "error": row[9],
                            "result_summary": row[10],
                        }
                    return None
        except Exception as e:
            logger.error("获取任务详情失败: task_id=%s error=%s", task_id, e)
            return None
