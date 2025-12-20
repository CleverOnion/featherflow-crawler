"""
惠农网行情页面解析器（SSR HTML）。

说明：
- 我们优先解析页面中已 SSR 输出的列表 DOM：
  `li.market-list-item` 内部包含 `span.time/product/place/price`
- 该解析器可用于离线 HTML（hn.html / 玉米.html），也可用于在线抓取的 HTML。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


_PRICE_RE = re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>.*)\s*$")


@dataclass(frozen=True)
class ParsedPrice:
    """解析后的行情记录（还未入库）。"""

    price_date: date
    product: str
    place: str
    price_raw: str
    price_value: Optional[float]
    price_unit: Optional[str]


def parse_price_value_unit(price_raw: str) -> Tuple[Optional[float], Optional[str]]:
    """
    从价格原文中解析数值与单位。

    示例：
    - \"7.65元/斤\" => (7.65, \"元/斤\")
    - \"面议\" => (None, \"面议\")
    """
    text = (price_raw or "").strip()
    if not text:
        return None, None

    m = _PRICE_RE.match(text)
    if not m:
        # 非数字开头的价格（如：面议）
        return None, text

    try:
        value = float(m.group("value"))
    except Exception:
        value = None

    unit = (m.group("unit") or "").strip() or None
    return value, unit


def parse_market_list(html: str) -> List[ParsedPrice]:
    """
    解析行情列表。

    :param html: 页面 HTML 文本
    :return: ParsedPrice 列表
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    items = soup.select("li.market-list-item")
    results: List[ParsedPrice] = []

    for idx, li in enumerate(items):
        time_el = li.select_one("span.time")
        product_el = li.select_one("span.product")
        place_el = li.select_one("span.place")
        price_el = li.select_one("span.price")

        if not (time_el and product_el and place_el and price_el):
            # 容错：某些条目可能结构异常，直接跳过并记录 debug
            logger.debug("行情条目字段缺失，idx=%s", idx)
            continue

        time_text = time_el.get_text(strip=True)
        product = product_el.get_text(strip=True)
        place = place_el.get_text(strip=True)
        price_raw = price_el.get_text(strip=True)

        # 基本校验
        if not (time_text and product and place and price_raw):
            logger.debug("行情条目存在空字段，idx=%s time=%r product=%r place=%r price=%r", idx, time_text, product, place, price_raw)
            continue

        try:
            price_date = datetime.strptime(time_text, "%Y-%m-%d").date()
        except Exception:
            logger.debug("时间字段格式不符合 YYYY-MM-DD，idx=%s time=%r", idx, time_text)
            continue

        price_value, price_unit = parse_price_value_unit(price_raw)
        results.append(
            ParsedPrice(
                price_date=price_date,
                product=product,
                place=place,
                price_raw=price_raw,
                price_value=price_value,
                price_unit=price_unit,
            )
        )

    return results


def extract_total_pages(html: str) -> Optional[int]:
    """
    从分页控件解析总页数（优先取 input[max]）。

    在 `hn.html` 中能看到类似：
    `<input ... max="5" min="1" ... value="4" class="eye-input__inner">`
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    input_el = soup.select_one(".quotation-paging input.eye-input__inner")
    if not input_el:
        return None
    max_val = input_el.get("max")
    if not max_val:
        return None
    try:
        return int(max_val)
    except Exception:
        return None


