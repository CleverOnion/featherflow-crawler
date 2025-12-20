"""
MySQL 数据访问层（PyMySQL）。

设计目标：
- 连接复用（简易连接池）
- 批量 upsert（性能优化）
- 参数化 SQL（安全：避免注入）
"""

from __future__ import annotations

import logging
import queue
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor, DictCursor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceRow:
    """行情记录（入库模型）。"""

    keyword: str
    price_date: date
    product: str
    place: str
    price_raw: str
    price_value: Optional[float]
    price_unit: Optional[str]
    source_url: Optional[str]
    crawled_at: datetime


class MySqlPool:
    """
    简易连接池。

    说明：
    - 为了减少依赖，这里不引入第三方连接池库；
    - 生产环境也可以替换为 SQLAlchemy pool / DBUtils。
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        pool_size: int = 5,
    ) -> None:
        self._dsn = dict(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )
        self._pool: "queue.Queue[Connection]" = queue.Queue(maxsize=max(pool_size, 1))

        # 预热：创建连接（可减少首次延迟）
        for _ in range(max(pool_size, 1)):
            self._pool.put(self._new_conn())

    def _new_conn(self) -> Connection:
        return pymysql.connect(**self._dsn)

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        conn: Optional[Connection] = None
        try:
            conn = self._pool.get(timeout=30)
            # 避免复用到已断开的连接
            try:
                conn.ping(reconnect=True)
            except Exception:
                logger.warning("MySQL ping 失败，重建连接")
                conn.close()
                conn = self._new_conn()
            yield conn
            conn.commit()
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    logger.exception("MySQL rollback 失败")
            raise
        finally:
            if conn is not None:
                try:
                    self._pool.put(conn, timeout=30)
                except Exception:
                    # 连接池满了或 put 超时，直接关闭连接避免泄漏
                    try:
                        conn.close()
                    except Exception:
                        pass


def init_schema(pool: MySqlPool) -> None:
    """初始化表结构（执行 app/db/schema.sql）。"""
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")

    # 简化处理：按分号切分执行（schema.sql 里只有一条 CREATE TABLE）
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
    logger.info("MySQL schema 初始化完成：%s", schema_path)


def exists_today(pool: MySqlPool, keyword: str, day: date) -> bool:
    """判断某关键词在指定日期是否已入库（用于跳过）。"""
    sql = (
        "SELECT 1 FROM hn_market_price "
        "WHERE keyword=%s AND price_date=%s "
        "LIMIT 1"
    )
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (keyword, day))
            row = cur.fetchone()
            return row is not None


def upsert_rows(pool: MySqlPool, rows: Sequence[PriceRow]) -> int:
    """
    批量 upsert。

    返回：受影响行数（MySQL 对 ON DUPLICATE KEY UPDATE 的行数语义较特殊，仅作参考）。
    """
    if not rows:
        return 0

    sql = (
        "INSERT INTO hn_market_price "
        "(keyword, price_date, product, place, price_raw, price_value, price_unit, source_url, crawled_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE "
        "price_value=VALUES(price_value), "
        "price_unit=VALUES(price_unit), "
        "source_url=VALUES(source_url), "
        "crawled_at=VALUES(crawled_at)"
    )

    params: List[Tuple] = []
    for r in rows:
        params.append(
            (
                r.keyword,
                r.price_date,
                r.product,
                r.place,
                r.price_raw,
                r.price_value,
                r.price_unit,
                r.source_url,
                r.crawled_at,
            )
        )

    with pool.connection() as conn:
        with conn.cursor() as cur:
            affected = cur.executemany(sql, params)
            return int(affected or 0)


