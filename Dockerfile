FROM python:3.11-slim AS base

# 防止生成 .pyc 文件 & 让日志实时输出
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装基础系统依赖（时区 & 常用工具）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        ca-certificates \
        curl && \
    rm -rf /var/lib/apt/lists/*

# 先单独复制依赖文件，利用 Docker 层缓存
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 如果需要启用 Playwright 兜底（ENABLE_PLAYWRIGHT_FALLBACK=1），
# 可以在构建参数里开启下面这一段（默认注释以减小镜像体积）：
#
ARG INSTALL_PLAYWRIGHT_DEPS=false
RUN if [ "$INSTALL_PLAYWRIGHT_DEPS" = "true" ]; then \
      pip install --no-cache-dir playwright && \
      python -m playwright install --with-deps chromium; \
    fi

# 复制项目代码
COPY . .

# 默认通过环境变量注入 MySQL / CRON / KEYWORDS 等配置
# 可选：在运行容器时挂载 .env 或使用 docker-compose / K8s Secret 等方式

# 容器启动命令：运行 APScheduler 常驻服务
CMD ["python", "-m", "app.main"]


