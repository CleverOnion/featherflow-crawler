"""
日志配置。

目标：
- 结构化日志（尽量包含 keyword/url/page 等关键字段）
- 兼容 Linux 容器/系统日志采集（输出到 stdout）
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """初始化全局日志配置。"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # 基础格式：时间 + 级别 + logger + msg
    # 说明：后续我们会在具体日志中以 key=value 方式补充结构化字段。
    fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # 降低第三方库日志噪音
    logging.getLogger("httpx").setLevel(max(numeric_level, logging.WARNING))
    logging.getLogger("apscheduler").setLevel(max(numeric_level, logging.INFO))


