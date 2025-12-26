"""
任务追踪相关的数据库表结构。
"""

TASKS_SCHEMA = """
-- 任务执行历史表
CREATE TABLE IF NOT EXISTS hn_crawl_tasks (
  task_id VARCHAR(36) PRIMARY KEY COMMENT '任务 UUID',
  keywords VARCHAR(500) NOT NULL COMMENT '逗号分隔的关键词',
  status VARCHAR(20) NOT NULL COMMENT 'pending/running/completed/failed/cancelled',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  started_at DATETIME NULL COMMENT '开始时间',
  completed_at DATETIME NULL COMMENT '完成时间',
  current_keyword VARCHAR(64) NULL COMMENT '当前处理的关键词',
  keyword_index INT DEFAULT 0 COMMENT '当前关键词索引',
  total_keywords INT NOT NULL COMMENT '总关键词数',
  error TEXT NULL COMMENT '错误信息',
  result_summary TEXT NULL COMMENT '结果摘要（JSON）',

  KEY idx_status_created (status, created_at),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫任务历史';

-- 任务日志表
CREATE TABLE IF NOT EXISTS hn_task_logs (
  log_id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '日志 ID',
  task_id VARCHAR(36) NOT NULL COMMENT '任务 UUID',
  log_message TEXT NOT NULL COMMENT '日志内容',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

  KEY idx_task_created (task_id, created_at),
  FOREIGN KEY (task_id) REFERENCES hn_crawl_tasks(task_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务执行日志';
"""
