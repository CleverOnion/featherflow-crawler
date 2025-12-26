"""
Flask 路由定义。

提供所有 API 端点和页面路由。
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, render_template, request

from app.config import Settings
from app.web.task_manager import TaskManager, TaskStatus

logger = logging.getLogger(__name__)

# 创建蓝图
api_bp = Blueprint("api", __name__, url_prefix="/api")


def init_routes(app: Any, settings: Settings, task_manager: TaskManager) -> None:
    """
    初始化所有路由。

    Args:
        app: Flask 应用实例
        settings: 应用配置
        task_manager: 任务管理器
    """

    @app.route("/")
    def index():
        """主页面。"""
        return render_template("index.html")

    # ========== API: 任务管理 ==========

    @api_bp.route("/tasks", methods=["POST"])
    def create_task():
        """
        创建并启动爬虫任务。

        Request Body:
            {"keywords": "关键词1,关键词2,...", "force_restart": false}

        Response:
            {"task_id": "...", "status": "pending", "total_keywords": 3}
        """
        try:
            data = request.get_json()
            if not data or "keywords" not in data:
                return jsonify({"error": "缺少 keywords 参数"}), 400

            keywords_str = data["keywords"]
            if not keywords_str or not isinstance(keywords_str, str):
                return jsonify({"error": "keywords 必须是非空字符串"}), 400

            # 解析关键词
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
            if not keywords:
                return jsonify({"error": "至少需要一个有效关键词"}), 400

            # 限制关键词数量
            if len(keywords) > 50:
                return jsonify({"error": "关键词数量不能超过 50 个"}), 400

            # 获取是否强制重新开始（默认 false = 续爬）
            force_restart = data.get("force_restart", False)

            # 创建任务
            task_id = task_manager.create_task(keywords, force_restart=force_restart)

            return jsonify({
                "task_id": task_id,
                "status": "pending",
                "total_keywords": len(keywords),
                "force_restart": force_restart,
            }), 201

        except Exception as e:
            logger.exception("创建任务失败")
            return jsonify({"error": f"服务器错误: {str(e)}"}), 500

    @api_bp.route("/tasks/<task_id>", methods=["GET"])
    def get_task(task_id: str):
        """
        获取任务状态。

        Response:
            {
                "task_id": "...",
                "keywords": ["..."],
                "status": "running",
                "created_at": "...",
                "started_at": "...",
                "completed_at": "...",
                "current_keyword": "...",
                "keyword_index": 1,
                "total_keywords": 3,
                "logs": ["..."],
                "results": [...],
                "error": null
            }
        """
        try:
            task = task_manager.get_task(task_id)
            if not task:
                return jsonify({"error": "任务不存在"}), 404

            return jsonify(task.to_dict()), 200

        except Exception as e:
            logger.exception("获取任务失败: task_id=%s", task_id)
            return jsonify({"error": f"服务器错误: {str(e)}"}), 500

    @api_bp.route("/tasks", methods=["GET"])
    def list_tasks():
        """
        列出最近的任务。

        Query Params:
            limit: 返回数量（默认 20）

        Response:
            [
                {
                    "task_id": "...",
                    "keywords": ["..."],
                    "status": "...",
                    "created_at": "...",
                    "current_keyword": "...",
                    "keyword_index": 1,
                    "total_keywords": 3,
                    "error": null
                },
                ...
            ]
        """
        try:
            limit = request.args.get("limit", 20, type=int)
            limit = min(max(1, limit), 100)  # 限制在 1-100 之间

            tasks = task_manager.list_tasks(limit)

            # 返回精简的任务信息
            result = []
            for task in tasks:
                result.append({
                    "task_id": task.task_id,
                    "keywords": task.keywords,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "current_keyword": task.current_keyword,
                    "keyword_index": task.keyword_index,
                    "total_keywords": task.total_keywords,
                    "error": task.error,
                })

            return jsonify(result), 200

        except Exception as e:
            logger.exception("列出任务失败")
            return jsonify({"error": f"服务器错误: {str(e)}"}), 500

    @api_bp.route("/tasks/<task_id>/logs", methods=["GET"])
    def get_task_logs(task_id: str):
        """
        获取任务日志。

        Response:
            {"logs": ["..."]}
        """
        try:
            task = task_manager.get_task(task_id)
            if not task:
                return jsonify({"error": "任务不存在"}), 404

            return jsonify({"logs": task.logs}), 200

        except Exception as e:
            logger.exception("获取任务日志失败: task_id=%s", task_id)
            return jsonify({"error": f"服务器错误: {str(e)}"}), 500

    @api_bp.route("/tasks/<task_id>/cancel", methods=["POST"])
    def cancel_task(task_id: str):
        """
        取消正在运行的任务。

        注意：当前实现只标记状态，不中断正在执行的爬虫。
        """
        try:
            task = task_manager.get_task(task_id)
            if not task:
                return jsonify({"error": "任务不存在"}), 404

            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return jsonify({"error": f"任务状态为 {task.status.value}，无法取消"}), 400

            task_manager.update_task_status(task_id, TaskStatus.CANCELLED)
            task_manager.append_log(task_id, "任务已被用户取消")

            return jsonify({"cancelled": True}), 200

        except Exception as e:
            logger.exception("取消任务失败: task_id=%s", task_id)
            return jsonify({"error": f"服务器错误: {str(e)}"}), 500

    # 注册蓝图
    app.register_blueprint(api_bp)

    logger.info("路由注册完成")
