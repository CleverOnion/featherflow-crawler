"""
疑似反爬/验证码检测。

注意：
- 不追求 100% 准确（这在反爬对抗中不现实），目标是“保守地识别异常页面”，
  以便触发退避策略，保证无人值守稳定运行。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BlockDecision:
    blocked: bool
    reason: str


# 关键词（可后续做成配置项）
_SUSPECT_TEXT = (
    "验证码",
    "安全验证",
    "安全校验",
    "人机",
    "访问异常",
    "请求过于频繁",
    "系统检测到",
    "请完成验证",
    "您的访问行为异常",
)

_NO_DATA_HINT = (
    "暂无行情",
    "没有找到",
    "market-null",
    "market-none",
)


def detect_blocked(html: str | None, status_code: Optional[int]) -> BlockDecision:
    """
    根据 HTTP 状态码与页面内容做“疑似反爬”判定。
    """
    if status_code in (403, 429):
        return BlockDecision(blocked=True, reason=f"http_status_{status_code}")

    if not html:
        return BlockDecision(blocked=True, reason="empty_html")

    # 正常页面应包含列表项（SSR 输出）
    has_list = "market-list-item" in html and "quotation-content" in html
    if has_list:
        return BlockDecision(blocked=False, reason="ok")

    # 无数据场景：不要误判为反爬
    for t in _NO_DATA_HINT:
        if t in html:
            return BlockDecision(blocked=False, reason="no_data")

    for t in _SUSPECT_TEXT:
        if t in html:
            return BlockDecision(blocked=True, reason=f"suspect_text:{t}")

    # 兜底：无列表且无明显关键词，判定为异常（可能是空结果，也可能是页面结构变化）
    return BlockDecision(blocked=True, reason="no_list_items")


