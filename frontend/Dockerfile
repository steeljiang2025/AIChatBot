# syntax=docker/dockerfile:1.7
# =====================================================================
# AIChatBot frontend image (Vite dev server)
# 镜像只装好依赖，源码通过 compose volume mount 进来，开启 HMR
# =====================================================================
FROM node:22-bookworm-slim AS base

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NODE_ENV=development \
    CHOKIDAR_USEPOLLING=true \
    WATCHPACK_POLLING=true

WORKDIR /app

# 启用 pnpm（通过 corepack）
RUN corepack enable \
    && corepack prepare pnpm@10.0.0 --activate

# 先安装依赖（缓存层）
COPY package.json pnpm-lock.yaml* /app/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm config set registry https://registry.npmmirror.com \
    && (pnpm install --frozen-lockfile || pnpm install)

# 把项目源码也 COPY 进去（compose 会再用 volume 覆盖以热更）
COPY . /app

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]
