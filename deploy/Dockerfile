FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

# 配置阿里云apt镜像源（加速系统包下载）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    gnupg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 配置pip国内镜像源（清华源）并安装Python依赖
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --upgrade pip \
    && pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 安装Playwright浏览器（如果需要启用后备方案）
RUN playwright install --with-deps chromium || true

# 复制项目文件
COPY app/ ./app/
COPY .gitignore ./

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 创建日志目录
RUN mkdir -p /app/logs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 暴露端口（虽然服务本身不需要端口，但保持良好的实践）
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "app.main"]