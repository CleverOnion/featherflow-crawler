"""
数据完整性检查器：自动检测缺失的关键词数据并触发补爬。

工作原理：
1. 定期检查所有配置的关键词是否都有当天数据
2. 发现缺失的关键词，自动触发补爬
3. 记录补爬结果，便于排查问题
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from app.config import Settings
from app.crawler.hn_crawler import HnCrawler, KeywordCrawlStats
from app.db.mysql import MySqlPool, get_missing_keywords, get_keywords_data_count

logger = logging.getLogger(__name__)


@dataclass
class IntegrityCheckResult:
    """完整性检查结果。"""
    check_time: datetime
    expected_keywords: List[str]
    missing_keywords: List[str]
    retry_results: List[KeywordCrawlStats] = field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0


class IntegrityChecker:
    """
    数据完整性检查器。

    功能：
    - 检查哪些关键词缺少当天数据
    - 自动触发缺失关键词的补爬
    - 记录补爬结果
    """

    def __init__(self, settings: Settings, db_pool: MySqlPool) -> None:
        self._s = settings
        self._db = db_pool
        # 记录每次检查的失败关键词，避免无限重试
        self._failed_keywords: set[tuple[str, date]] = set()

    def check_and_retry(self, check_date: Optional[date] = None) -> IntegrityCheckResult:
        """
        检查指定日期的数据完整性，并对缺失的关键词进行补爬。

        Args:
            check_date: 要检查的日期，默认为今天

        Returns:
            IntegrityCheckResult: 检查结果详情
        """
        if check_date is None:
            check_date = date.today()

        keywords = self._s.keyword_list()
        if not keywords:
            logger.warning("未配置 KEYWORDS，跳过完整性检查")
            return IntegrityCheckResult(
                check_time=datetime.now(),
                expected_keywords=[],
                missing_keywords=[],
            )

        logger.info(
            "开始数据完整性检查：date=%s keywords=%s",
            check_date.isoformat(),
            ",".join(keywords),
        )

        # 获取数据统计
        data_counts = get_keywords_data_count(self._db, keywords, check_date)
        logger.info("当天数据统计：%s", data_counts)

        # 检查缺失的关键词
        missing = get_missing_keywords(self._db, keywords, check_date)

        if not missing:
            logger.info("所有关键词都有数据，完整性检查通过")
            return IntegrityCheckResult(
                check_time=datetime.now(),
                expected_keywords=keywords,
                missing_keywords=[],
            )

        logger.warning(
            "发现缺失数据的关键词：missing=%s (total=%s/%s)",
            ",".join(missing),
            len(missing),
            len(keywords),
        )

        # 对缺失的关键词进行补爬
        result = IntegrityCheckResult(
            check_time=datetime.now(),
            expected_keywords=keywords,
            missing_keywords=missing,
        )

        crawler = HnCrawler(settings=self._s, db_pool=self._db)
        try:
            for kw in missing:
                # 检查是否已经在今天失败过（避免无限重试）
                key = (kw, check_date)
                if key in self._failed_keywords:
                    logger.warning("关键词今天已失败过，跳过补爬：keyword=%s", kw)
                    result.failed_count += 1
                    continue

                try:
                    logger.info("开始补爬缺失关键词：keyword=%s", kw)
                    stats = crawler.crawl_keyword(kw, force_restart=True)

                    result.retry_results.append(stats)

                    if stats.blocked:
                        logger.warning(
                            "补爬被拦截：keyword=%s reason=%s",
                            kw,
                            stats.blocked_reason,
                        )
                        self._failed_keywords.add(key)
                        result.failed_count += 1
                    elif stats.rows_upserted == 0:
                        logger.warning("补爬成功但无数据入库：keyword=%s", kw)
                        result.failed_count += 1
                    else:
                        logger.info(
                            "补爬成功：keyword=%s upserted=%s",
                            kw,
                            stats.rows_upserted,
                        )
                        result.success_count += 1
                        # 成功后从失败记录中移除
                        self._failed_keywords.discard(key)

                except Exception:
                    logger.exception("补爬异常：keyword=%s", kw)
                    self._failed_keywords.add((kw, check_date))
                    result.failed_count += 1

        finally:
            crawler.close()

        logger.info(
            "完整性检查完成：missing=%s success=%s failed=%s",
            len(missing),
            result.success_count,
            result.failed_count,
        )

        return result

    def reset_failed_records(self) -> None:
        """重置失败记录（用于新的一天或手动重置）。"""
        self._failed_keywords.clear()
        logger.info("已重置失败关键词记录")

    def get_failed_keywords_today(self) -> List[str]:
        """获取今天失败的关键词列表。"""
        today = date.today()
        return [kw for (kw, day) in self._failed_keywords if day == today]
