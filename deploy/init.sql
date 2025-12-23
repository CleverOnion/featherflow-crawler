-- FeatherFlow 数据库初始化脚本
-- 使用方法：mysql -u root -p < init.sql

-- 创建数据库
CREATE DATABASE IF NOT EXISTS tiangenexora CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE tiangenexora;

-- 创建市场价格数据表
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

  -- 快速判断"某关键词当天是否已入库"
  KEY idx_kw_date (keyword, price_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='惠农网市场价格数据';

-- 创建任务日志表
CREATE TABLE IF NOT EXISTS hn_crawler_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL COMMENT '搜索关键词',
    start_time TIMESTAMP NOT NULL COMMENT '开始时间',
    end_time TIMESTAMP NULL COMMENT '结束时间',
    status ENUM('running', 'success', 'failed', 'timeout') NOT NULL COMMENT '任务状态',
    total_pages INT DEFAULT 0 COMMENT '总页数',
    parsed_items INT DEFAULT 0 COMMENT '解析到的数据条数',
    inserted_items INT DEFAULT 0 COMMENT '插入的新数据条数',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    KEY idx_keyword_time (keyword, start_time),
    KEY idx_status (status),
    KEY idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爬虫任务日志表';

-- 创建每日处理记录表（防止重复处理，支持断点续爬）
CREATE TABLE IF NOT EXISTS hn_daily_record (
    id INT AUTO_INCREMENT PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL,
    process_date DATE NOT NULL,
    last_page INT DEFAULT 0 COMMENT '上次爬取到的页码',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_keyword_date (keyword, process_date),
    KEY idx_process_date (process_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日处理记录表';

-- 设置时区
SET time_zone = '+08:00';

-- 完成
SELECT 'FeatherFlow 数据库初始化完成！' AS message;