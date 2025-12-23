# FeatherFlow Docker 部署指南

本文档介绍如何使用Docker部署FeatherFlow惠农网行情爬虫系统。

## 目录结构

```
FeatherFlow/
├── app/                    # 应用代码
├── deploy/                 # 部署相关文件
│   ├── Dockerfile         # Docker镜像构建文件
│   ├── docker-compose.yml # Docker Compose编排文件
│   └── .env.example       # 环境变量配置模板
└── logs/                  # 日志目录（运行时创建）
```

## 快速开始

### 1. 环境准备

确保已安装以下软件：
- Docker >= 20.10
- Docker Compose >= 2.0
- MySQL数据库（可以是本地或远程）

### 2. 配置数据库

在MySQL中创建数据库（如果不存在）：
```sql
CREATE DATABASE IF NOT EXISTS tiangenexora CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 配置环境变量

复制环境变量配置文件：
```bash
cp deploy/.env.example deploy/.env
```

**重要**：编辑 `deploy/.env` 文件，至少需要配置以下项：
```bash
# 数据库配置（必须）
MYSQL_HOST=your_mysql_host          # 数据库主机地址
MYSQL_PORT=3306                     # 数据库端口
MYSQL_USER=your_mysql_user          # 数据库用户名
MYSQL_PASSWORD=your_mysql_password  # 数据库密码（必须设置）
MYSQL_DATABASE=tiangenexora           # 数据库名称
```

其他可选配置项：
- `KEYWORDS`: 要爬取的关键词，默认：鹅,玉米,豆粕
- `CRON`: 定时执行时间，默认：30 8 * * *（每天8:30）
- `RUN_ON_START`: 启动时是否立即执行，默认：1（是）

### 4. 启动服务

```bash
# 构建并启动服务
docker-compose -f deploy/docker-compose.yml up -d

# 查看日志
docker-compose -f deploy/docker-compose.yml logs -f
```

### 5. 验证运行

```bash
# 查看服务状态
docker-compose -f deploy/docker-compose.yml ps

# 进入容器查看
docker-compose -f deploy/docker-compose.yml exec app bash

# 查看数据库中的数据
mysql -h your_mysql_host -u your_user -p tiangenexora -e "SELECT * FROM hn_market_price ORDER BY created_at DESC LIMIT 10;"
```

## 数据库配置说明

### 本地数据库

如果MySQL运行在同一台机器上：
```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
```

注意：如果Docker运行在Linux上，需要确保MySQL允许从容器网络访问。

### 远程数据库

如果MySQL在远程服务器上：
```bash
MYSQL_HOST=192.168.1.100  # 远程服务器IP
MYSQL_PORT=3306
MYSQL_USER=featherflow
MYSQL_PASSWORD=strong_password
```

### Docker网络中的数据库

如果MySQL也在Docker中运行：
```bash
# 确保两个容器在同一个Docker网络中
MYSQL_HOST=mysql_container_name
MYSQL_PORT=3306
```

## 常用操作

### 重新构建镜像

```bash
# 修改代码后重新构建
docker-compose -f deploy/docker-compose.yml build app

# 强制重新构建
docker-compose -f deploy/docker-compose.yml build --no-cache app
```

### 停止服务

```bash
# 停止服务
docker-compose -f deploy/docker-compose.yml down

# 停止并删除镜像
docker-compose -f deploy/docker-compose.yml down --rmi all
```

### 更新配置

```bash
# 修改.env文件后
docker-compose -f deploy/docker-compose.yml down
docker-compose -f deploy/docker-compose.yml up -d
```

### 查看日志

```bash
# 查看所有日志
docker-compose -f deploy/docker-compose.yml logs

# 实时查看应用日志
docker-compose -f deploy/docker-compose.yml logs -f app

# 查看最近100行日志
docker-compose -f deploy/docker-compose.yml logs --tail=100 app
```

## 监控和故障排查

### 1. 检查服务状态

```bash
# 查看容器状态
docker-compose -f deploy/docker-compose.yml ps

# 查看容器资源使用
docker stats featherflow-app

# 查看健康检查状态
docker inspect featherflow-app | grep Health
```

### 2. 常见问题

**问题：无法连接数据库**
- 检查数据库服务是否运行
- 验证网络连接（从容器内测试）
- 确认用户权限和密码

```bash
# 测试数据库连接
docker-compose -f deploy/docker-compose.yml exec app \
    python -c "
import pymysql
conn = pymysql.connect(
    host='${MYSQL_HOST}',
    port=int('${MYSQL_PORT}'),
    user='${MYSQL_USER}',
    password='${MYSQL_PASSWORD}',
    database='${MYSQL_DATABASE}'
)
print('数据库连接成功!')
"
```

**问题：爬虫被反爬**
- 调整反爬虫配置参数
- 增加请求间隔
- 启用Playwright后备方案

```bash
# 修改.env文件
BACKOFF_BASE_SECONDS=30
BACKOFF_MAX_SECONDS=1800
BLOCKED_MAX_RETRY=5
ENABLE_PLAYWRIGHT_FALLBACK=1
```

**问题：容器内存不足**
- 增加Docker内存限制
- 优化爬虫参数
- 定期清理日志

### 3. 性能监控

```bash
# 监控资源使用
docker stats featherflow-app --no-stream

# 查看磁盘使用
docker-compose -f deploy/docker-compose.yml exec app du -sh /app/logs

# 监控数据库连接数
mysql -h ${MYSQL_HOST} -u ${MYSQL_USER} -p -e "SHOW PROCESSLIST;"
```

## 数据管理

### 导出数据

```bash
# 导出爬取的数据
docker-compose -f deploy/docker-compose.yml exec app \
    python -c "
from app.db.mysql import MySQLConnection
import csv
import sys

db = MySQLConnection()
results = db.fetch_all('SELECT * FROM hn_market_price ORDER BY created_at DESC LIMIT 1000')

with open('/app/logs/export.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['关键词', '日期', '产品', '产地', '价格', '创建时间'])
    for row in results:
        writer.writerow([row[1], row[2], row[3], row[4], row[5], row[9]])

print('数据已导出到 /app/logs/export.csv')
"
```

### 清理旧数据

```bash
# 清理30天前的日志数据
docker-compose -f deploy/docker-compose.yml exec app \
    python -c "
from app.db.mysql import MySQLConnection
import datetime

db = MySQLConnection()
cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
sql = 'DELETE FROM hn_crawler_log WHERE created_at < %s'
db.execute(sql, (cutoff_date,))
print(f'已清理 {cutoff_date} 之前的日志数据')
"
```

## 配置说明

### 关键词配置

支持配置多个关键词，用英文逗号分隔：
```bash
KEYWORDS=鹅,玉米,豆粕,小麦,水稻,生猪
```

### 定时任务配置

使用标准Cron表达式（5段）：
```bash
# 每天上午8:30
CRON=30 8 * * *

# 每天上午9点和下午3点
CRON=0 9,15 * * *

# 每周一到五的上午9点
CRON=0 9 * * 1-5
```

### 反爬虫配置

根据目标网站的反爬策略调整：
```bash
# 请求间隔（秒）
HTTP_TIMEOUT_SECONDS=30

# 重试次数
HTTP_RETRY_TIMES=3

# 退避算法
BACKOFF_BASE_SECONDS=30      # 基础等待时间
BACKOFF_MAX_SECONDS=3600     # 最大等待时间
BLOCKED_MAX_RETRY=10        # 最大重试次数

# 浏览器后备方案
ENABLE_PLAYWRIGHT_FALLBACK=1  # 启用浏览器模拟
PLAYWRIGHT_HEADLESS=1        # 无头模式
```

## 安全建议

1. **数据库安全**
   - 使用强密码
   - 限制数据库用户权限
   - 启用SSL连接（如果支持）

2. **容器安全**
   - 定期更新基础镜像
   - 不要在镜像中包含敏感信息
   - 使用非root用户运行

3. **网络安全**
   - 使用防火墙限制数据库访问
   - 不要暴露不必要的端口
   - 考虑使用VPN或专用网络

## 支持和帮助

如遇到问题：
1. 查看容器日志：`docker-compose -f deploy/docker-compose.yml logs app`
2. 检查环境变量配置
3. 验证数据库连接
4. 查看GitHub Issues