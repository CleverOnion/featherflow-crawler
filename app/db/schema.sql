-- 惠农网行情数据表（MySQL）
-- 说明：
-- - 本 SQL 只创建表，不创建数据库；请先创建 MYSQL_DATABASE 对应库。
-- - 采用 utf8mb4，避免中文乱码。

CREATE TABLE IF NOT EXISTS hn_market_price (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',

  keyword VARCHAR(64) NOT NULL COMMENT '抓取关键词（如：鹅/玉米/豆粕）',
  price_date DATE NOT NULL COMMENT '页面时间（YYYY-MM-DD）',
  product VARCHAR(128) NOT NULL COMMENT '产品/品种',
  place VARCHAR(128) NOT NULL COMMENT '所在产地',
  price_raw VARCHAR(64) NOT NULL COMMENT '价格原始文本（如：7.65元/斤）',

  price_value DECIMAL(10,2) NULL COMMENT '价格数值（可选）',
  price_unit VARCHAR(32) NULL COMMENT '价格单位（可选，如：元/斤）',

  source_url VARCHAR(512) NULL COMMENT '来源 URL（抓取时记录）',
  crawled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '抓取入库时间',

  PRIMARY KEY (id),

  -- 幂等约束：同一关键词、同一天、同品种、同产地、同价格文本视为同一条
  UNIQUE KEY uk_kw_date_product_place_price (keyword, price_date, product, place, price_raw),

  -- 快速判断“某关键词当天是否已入库”
  KEY idx_kw_date (keyword, price_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


