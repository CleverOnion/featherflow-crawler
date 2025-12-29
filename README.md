# FeatherFlow

<div align="center">

**惠农网行情定时爬虫系统**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

无人值守 | 定时调度 | 数据完整性检查 | Web管理界面

</div>

---

## 简介

FeatherFlow 是一个基于 Python 的惠农网（cnhnb.com）农产品行情爬虫系统，支持定时抓取、数据持久化、反爬虫处理和 Web 管理界面。

### 核心特性

- **定时调度** - 基于 APScheduler 的 Cron 定时任务，灵活配置执行时间
- **分页抓取** - 自动识别并抓取所有分页数据
- **幂等入库** - 唯一约束保证数据不重复
- **断点续爬** - 支持从中断位置继续抓取
- **反爬虫处理** - 多层反爬策略（UA轮换、指数退避、Playwright兜底）
- **数据完整性检查** - 自动检测缺失关键词并触发补爬
- **Web 管理界面** - Newsprint 风格的 Web UI，支持手动执行和实时监控
- **Docker 部署** - 开箱即用的容器化部署方案

---

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 8.0+

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/CleverOnion/featherflow-crawler.git
cd featherflow-crawler

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp env.example .env

# 编辑 .env 配置数据库连接
# vim .env

# 启动服务
python -m app.main
```

服务启动后，Web 管理界面：http://localhost:5000

### Docker 部署

```bash
# 进入部署目录
cd deploy

# 配置环境变量
cp .env.example .env
vim .env  # 必须配置数据库连接信息

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

Web 管理界面：http://localhost:10500

---

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MYSQL_HOST` | 127.0.0.1 | MySQL 主机地址 |
| `MYSQL_PORT` | 3306 | MySQL 端口 |
| `MYSQL_USER` | root | MySQL 用户名 |
| `MYSQL_PASSWORD` | - | MySQL 密码（必填） |
| `MYSQL_DATABASE` | hn_market | 数据库名称 |
| `KEYWORDS` | 鹅,玉米,豆粕 | 爬取关键词（逗号分隔） |
| `CRON` | 30 8 * * * | 定时任务 Cron 表达式 |
| `RUN_ON_START` | 1 | 启动时是否立即执行 |
| `INTEGRITY_CHECK_ENABLED` | 1 | 是否启用数据完整性检查 |
| `INTEGRITY_CHECK_CRON` | */10 * * * * | 完整性检查频率 |
| `FLASK_ENABLED` | 1 | 是否启用 Web 界面 |
| `FLASK_PORT` | 5000 | Web 服务端口 |

### Cron 表达式格式

```
分钟 小时 日期 月份 星期
30   8    *    *     *     # 每天 08:30
0    */2  *    *     *     # 每 2 小时
0    9    *    *     1-5   # 周一到周五 09:00
```

---

## Web 管理界面

FeatherFlow 提供了 Newspaper 风格的 Web 管理界面：

### 功能

- **手动执行** - 立即触发指定关键词的爬取任务
- **续爬/重爬** - 支持断点续爬或从头开始
- **实时监控** - 查看任务执行状态和进度
- **日志查看** - 实时显示执行日志
- **任务历史** - 查看最近执行的任务记录

### API 接口

```bash
# 创建任务
POST /api/tasks
{
    "keywords": "鹅,玉米",
    "force_restart": false
}

# 查看任务状态
GET /api/tasks/{task_id}

# 获取任务日志
GET /api/tasks/{task_id}/logs

# 取消任务
POST /api/tasks/{task_id}/cancel

# 获取任务列表
GET /api/tasks
```

---

## 数据完整性检查

系统会定期检查所有配置的关键词是否都有当天数据：

1. **检测机制** - 每 10 分钟检查一次（可配置）
2. **自动补爬** - 发现缺失的关键词自动触发补爬
3. **失败保护** - 记录当天失败的关键词，避免无限重试
4. **详细日志** - 记录补爬结果，便于排查问题

### 配置选项

```bash
INTEGRITY_CHECK_ENABLED=1           # 启用完整性检查
INTEGRITY_CHECK_CRON=*/10 * * * *   # 每 10 分钟检查一次
```

---

## 项目结构

```
FeatherFlow/
├── app/
│   ├── crawler/           # 爬虫模块
│   │   ├── hn_crawler.py      # 主爬虫逻辑
│   │   ├── block_detector.py  # 反爬检测
│   │   ├── http_fetcher.py    # HTTP 请求
│   │   └── playwright_fetcher.py  # 浏览器兜底
│   ├── parser/            # 解析模块
│   │   └── hn_parser.py        # 页面解析
│   ├── db/                # 数据库模块
│   │   ├── mysql.py           # MySQL 操作
│   │   └── schema.sql         # 表结构
│   ├── web/               # Web 界面
│   │   ├── templates/         # HTML 模板
│   │   ├── static/            # 静态资源
│   │   ├── app.py             # Flask 应用
│   │   └── routes.py          # API 路由
│   ├── scheduler.py       # 定时调度
│   ├── integrity_checker.py  # 完整性检查
│   ├── config.py          # 配置管理
│   └── main.py            # 程序入口
├── tests/                # 单元测试
├── deploy/               # Docker 部署
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt      # Python 依赖
└── README.md            # 项目文档
```

---

## 反爬虫策略

### 多层防护

1. **UA 轮换** - 模拟真实浏览器访问
2. **指数退避** - 检测到反爬自动延迟重试
3. **Playwright 兜底** - HTTP 失败时使用浏览器渲染
4. **浏览器重启** - 检测到封禁自动重启浏览器实例

### 配置参数

```bash
HTTP_TIMEOUT_SECONDS=20         # 请求超时时间
HTTP_RETRY_TIMES=2              # HTTP 重试次数
BACKOFF_BASE_SECONDS=10         # 退避基础时间
BACKOFF_MAX_SECONDS=600         # 退避最大时间
BLOCKED_MAX_RETRY=2             # 反爬重试次数
ENABLE_PLAYWRIGHT_FALLBACK=1    # 启用 Playwright
```

---

## 数据库表结构

### hn_market_price（行情数据表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| keyword | VARCHAR(50) | 关键词 |
| price_date | DATE | 价格日期 |
| product | VARCHAR(100) | 产品名称 |
| place | VARCHAR(100) | 产地 |
| price_raw | VARCHAR(50) | 原始价格 |
| price_value | DECIMAL(10,2) | 价格数值 |
| price_unit | VARCHAR(20) | 价格单位 |
| source_url | VARCHAR(500) | 来源 URL |
| crawled_at | DATETIME | 爬取时间 |

**唯一约束**: `(keyword, price_date, product, place, price_raw)`

---

## 故障排查

### 问题：数据库连接失败

```bash
# 检查 MySQL 服务状态
systemctl status mysql

# 测试连接
mysql -h 127.0.0.1 -u root -p

# 检查防火墙
sudo ufw allow 3306
```

### 问题：爬虫被反爬

```bash
# 调整反爬参数
BACKOFF_BASE_SECONDS=30
BACKOFF_MAX_SECONDS=1800
BLOCKED_MAX_RETRY=5

# 启用 Playwright
ENABLE_PLAYWRIGHT_FALLBACK=1
python -m playwright install chromium
```

### 问题：Docker 容器无法连接数据库

```bash
# 检查网络配置
docker network ls

# 使用 host 网络模式（Linux）
# 在 docker-compose.yml 中添加：
network_mode: "host"
```

---

## 运行测试

```bash
# 运行所有测试
pytest -v

# 运行指定测试
pytest tests/test_hn_parser.py -v

# 查看覆盖率
pytest --cov=app tests/
```

---

## 许可证

[MIT License](LICENSE)

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

<div align="center">

**Made with ❤️ by CleverOnion**

</div>
