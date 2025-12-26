"""
Web 端任务状态管理器（内存存储 + 数据库持久化）。

提供线程安全的任务创建、状态更新、日志记录等功能。
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class KeywordCrawlResult:
    """单个关键词的爬取结果。"""
    keyword: str
    pages_total: int
    pages_fetched: int
    rows_parsed: int
    rows_upserted: int
    blocked: bool
    blocked_reason: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "pages_total": self.pages_total,
            "pages_fetched": self.pages_fetched,
            "rows_parsed": self.rows_parsed,
            "rows_upserted": self.rows_upserted,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeywordCrawlResult":
        return cls(
            keyword=data["keyword"],
            pages_total=data["pages_total"],
            pages_fetched=data["pages_fetched"],
            rows_parsed=data["rows_parsed"],
            rows_upserted=data["rows_upserted"],
            blocked=data["blocked"],
            blocked_reason=data.get("blocked_reason"),
        )


@dataclass
class TaskInfo:
    """任务信息。"""
    task_id: str
    keywords: List[str]
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_keyword: Optional[str] = None
    keyword_index: int = 0
    total_keywords: int = 0
    force_restart: bool = False  # 是否强制重新开始（忽略断点续爬）
    logs: List[str] = field(default_factory=list)
    results: List[KeywordCrawlResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "keywords": self.keywords,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_keyword": self.current_keyword,
            "keyword_index": self.keyword_index,
            "total_keywords": self.total_keywords,
            "force_restart": self.force_restart,
            "logs": self.logs,
            "results": [r.to_dict() for r in self.results],
            "error": self.error,
        }


class TaskManager:
    """
    任务状态管理器（线程安全）。

    内存存储当前活动任务，数据库持久化历史任务。
    """

    def __init__(self, max_stored_logs: int = 1000, max_stored_tasks: int = 100):
        """
        初始化任务管理器。

        Args:
            max_stored_logs: 单个任务最多存储的日志条数
            max_stored_tasks: 内存中最多存储的任务数量
        """
        self._tasks: Dict[str, TaskInfo] = {}
        self._lock = threading.RLock()
        self._max_stored_logs = max_stored_logs
        self._max_stored_tasks = max_stored_tasks

    def create_task(self, keywords: List[str], force_restart: bool = False) -> str:
        """
        创建新任务。

        Args:
            keywords: 关键词列表
            force_restart: 是否强制重新开始（忽略断点续爬）

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()

        with self._lock:
            task = TaskInfo(
                task_id=task_id,
                keywords=keywords,
                status=TaskStatus.PENDING,
                created_at=now,
                total_keywords=len(keywords),
                keyword_index=0,
                force_restart=force_restart,
            )
            self._tasks[task_id] = task

            # 清理旧任务（保持内存占用在限制内）
            self._cleanup_old_tasks()

            logger.info("任务已创建：task_id=%s keywords=%s force_restart=%s", task_id, keywords, force_restart)

        return task_id

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息。"""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> List[TaskInfo]:
        """
        列出最近的任务（按创建时间倒序）。

        Args:
            limit: 最多返回的任务数量

        Returns:
            任务列表
        """
        with self._lock:
            tasks = list(self._tasks.values())
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        current_keyword: Optional[str] = None,
        keyword_index: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        更新任务状态。

        Args:
            task_id: 任务 ID
            status: 新状态
            current_keyword: 当前处理的关键词
            keyword_index: 当前关键词索引
            error: 错误信息

        Returns:
            是否更新成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.status = status
            if current_keyword is not None:
                task.current_keyword = current_keyword
            if keyword_index is not None:
                task.keyword_index = keyword_index
            if error is not None:
                task.error = error

            # 状态转换时更新时间戳
            if status == TaskStatus.RUNNING and task.started_at is None:
                task.started_at = datetime.now()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.completed_at is None:
                    task.completed_at = datetime.now()

            return True

    def append_log(self, task_id: str, message: str) -> bool:
        """
        向任务添加日志。

        Args:
            task_id: 任务 ID
            message: 日志消息

        Returns:
            是否添加成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            # 限制日志数量
            if len(task.logs) >= self._max_stored_logs:
                task.logs = task.logs[-(self._max_stored_logs // 2):]

            task.logs.append(message)
            return True

    def add_result(self, task_id: str, result: KeywordCrawlResult) -> bool:
        """
        向任务添加关键词爬取结果。

        Args:
            task_id: 任务 ID
            result: 爬取结果

        Returns:
            是否添加成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.results.append(result)
            return True

    def delete_task(self, task_id: str) -> bool:
        """删除任务。"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def _cleanup_old_tasks(self) -> None:
        """清理旧任务，保持内存占用在限制内。"""
        while len(self._tasks) > self._max_stored_tasks:
            # 找到最早创建的任务
            oldest_task = min(self._tasks.values(), key=lambda t: t.created_at)
            self.delete_task(oldest_task.task_id)
            logger.debug("清理旧任务：task_id=%s", oldest_task.task_id)

    def get_next_pending_task(self) -> Optional[TaskInfo]:
        """获取下一个待处理的任务（用于工作线程）。"""
        with self._lock:
            for task in self._tasks.values():
                if task.status == TaskStatus.PENDING:
                    return task
            return None

    def has_running_tasks(self) -> bool:
        """检查是否有正在运行的任务。"""
        with self._lock:
            return any(t.status == TaskStatus.RUNNING for t in self._tasks.values())
