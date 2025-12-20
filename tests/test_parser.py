from __future__ import annotations

from pathlib import Path

import pytest

from app.crawler.block_detector import detect_blocked
from app.parser.hn_parser import extract_total_pages, parse_market_list, parse_price_value_unit


def _read_fixture(name: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / name).read_text(encoding="utf-8")


def test_parse_market_list_hn_html() -> None:
    html = _read_fixture("hn.html")
    items = parse_market_list(html)
    assert len(items) > 0
    # 抽样检查字段
    p = items[0]
    assert p.product
    assert p.place
    assert p.price_raw


def test_extract_total_pages_hn_html() -> None:
    html = _read_fixture("hn.html")
    total = extract_total_pages(html)
    # hn.html 中 max="5"
    assert total == 5


def test_parse_market_list_corn_html() -> None:
    html = _read_fixture("玉米.html")
    items = parse_market_list(html)
    assert len(items) > 0
    # 玉米页面示例里是“冻/熟玉米”
    assert any("玉米" in x.product for x in items)


def test_parse_price_value_unit_numeric() -> None:
    v, u = parse_price_value_unit("7.65元/斤")
    assert v == pytest.approx(7.65)
    assert u == "元/斤"


def test_parse_price_value_unit_non_numeric() -> None:
    v, u = parse_price_value_unit("面议")
    assert v is None
    assert u == "面议"


def test_block_detector_ok() -> None:
    html = _read_fixture("hn.html")
    d = detect_blocked(html, 200)
    assert d.blocked is False


def test_block_detector_blocked_by_keyword() -> None:
    d = detect_blocked("<html>请完成验证：验证码</html>", 200)
    assert d.blocked is True


def test_block_detector_blocked_by_status() -> None:
    d = detect_blocked("<html>whatever</html>", 403)
    assert d.blocked is True


