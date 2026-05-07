# syntax=docker/dockerfile:1.7
# =====================================================================
# AIChatBot backend image
# 单镜像支持 dev（mount 源码 + uvicorn --reload）与 prod 两种用法。
# 默认 CMD 走 dev；prod 通过 docker run --target=prod 或在 compose 指定 command。
# =====================================================================
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 切换到清华大学 Debian 镜像源，国内拉取更快更稳
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
            /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
            /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# 先复制 pyproject 触发依赖层缓存
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

# Phase1 安装运行时 + dev 依赖（容器内方便跑 pytest / ruff）
RUN python -m pip install --upgrade pip \
    && pip install -e ".[dev]"

# 默认把整套源码 COPY 进镜像；compose 中再用 volume 覆盖以获得热更新
COPY app /app/app
COPY tests /app/tests
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

EXPOSE 8000

# 默认开发模式：监听 0.0.0.0 并启用 --reload，配合 compose 的源码挂载使用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
