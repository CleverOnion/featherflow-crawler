## 惠农网行情定时爬虫（无人值守 + APScheduler + MySQL）

### 功能
- **按关键词**抓取惠农网行情列表（时间/产品/产地/价格），并写入 **MySQL**。
- **分页全量**抓取（若页面存在多页）。
- **幂等入库**：同一条记录重复抓取不会重复写入。
- **按关键词跳过**：若数据库已存在该 `keyword` 当天（`YYYY-MM-DD`）任意记录，则该关键词本次直接跳过。
- **无人值守反爬处理**：疑似验证码/风控时自动退避（降频 + 延迟重试 + 下次调度再跑），不需要人工介入。

### 目录结构
- `app/`：服务代码
- `tests/`：单元测试（离线解析 `hn.html` / `玉米.html`）
- `env.example`：环境变量示例（复制为 `.env`）

### 运行环境
- Python 3.10+（推荐 3.11）
- MySQL 8.0+（或兼容版本）

### 安装依赖
建议使用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Playwright（可选兜底）
如果启用 `ENABLE_PLAYWRIGHT_FALLBACK=1`，需要额外安装浏览器依赖：

```bash
python -m playwright install chromium
```

### 配置
复制示例配置并修改：

```bash
cp env.example .env
```

关键项：
- `MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE`
- `KEYWORDS`：例如 `鹅,玉米,豆粕`
- `CRON`：例如 `30 8 * * *`

### 启动服务（定时在代码里）

```bash
python -m app.main
```

说明：
- 定时由 **APScheduler** 实现（代码层面）。
- Linux 上可用 `systemd` 或 Docker 仅做“进程保活”，**不是系统定时任务**。

### 运行单元测试

```bash
pytest -q
```

## FeatherFlow - 惠农网行情页面结构抓取脚本（开发准备）

本仓库当前阶段仅提供**页面结构快照**能力，用于后续开发“定时爬虫 + MySQL 入库 + 分页全量抓取 + 去重”服务。

### 1. 环境准备

- **Python**：建议 3.10+（Windows 可直接安装官方版本）

安装依赖：

```bash
pip install -r requirements.txt
```

如果需要使用浏览器渲染模式（用于应对 JS 渲染/反爬/验证码导致 requests 获取不到有效内容）：

```bash
python -m playwright install chromium
```

### 2. 运行结构抓取脚本

#### 2.1 requests 模式（默认优先）

```bash
python scripts/dump_cnhnb_structure.py --url "https://www.cnhnb.com/hangqing/?k=%E7%8E%89%E7%B1%B3"
```

#### 2.2 强制 playwright 模式（推荐首次对比）

```bash
python scripts/dump_cnhnb_structure.py --url "https://www.cnhnb.com/hangqing/?k=%E7%8E%89%E7%B1%B3" --engine playwright
```

### 3. 输出内容

脚本会在 `artifacts/` 下生成：

- `raw_requests.html`：requests 获取到的原始 HTML（若选择 requests）
- `rendered.html`：playwright 渲染后的 DOM（若选择 playwright）
- `page.png`：页面截图（若选择 playwright）
- `structure_summary.json`：结构摘要（包含表头、候选行、字段映射尝试、分页链接候选等）

### 4. 运行单元测试

```bash
pytest -q
```


