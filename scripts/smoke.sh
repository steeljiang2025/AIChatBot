#!/usr/bin/env bash
# =============================================================================
# Phase1 端到端冒烟测试（全栈容器化版本）
# 检查项：
#   1. Postgres 容器健康 + pgvector + meta/rag/biz/checkpoint schema + 双账号
#   2. backend 容器健康 + /health=ok + /docs 可访问 + 容器内 pytest（可选）
#   3. frontend 容器健康 + 5173 端口可达 + 容器内 vitest（可选）
# 使用：
#   bash scripts/smoke.sh                # 基础检查
#   bash scripts/smoke.sh --with-tests   # 同时跑容器内单测
# =============================================================================
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PG_CONTAINER="${PG_CONTAINER:-aichatbot-postgres}"
BE_CONTAINER="${BE_CONTAINER:-aichatbot-backend}"
FE_CONTAINER="${FE_CONTAINER:-aichatbot-frontend}"

PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-aichatbot}"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_URL="${BACKEND_URL:-http://localhost:${BACKEND_PORT}}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${FRONTEND_PORT}}"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*" >&2; }
ylw()   { printf "\033[33m%s\033[0m\n" "$*"; }

ok=0; fail=0
pass()  { green "  ✓ $1"; ok=$((ok + 1)); }
miss()  { red   "  ✗ $1"; fail=$((fail + 1)); }

check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "${label}"; else miss "${label}"; fi
}

# 容器内 psql 查询
psql_q() {
  podman exec "${PG_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

# ---------- 1) 数据库 ----------
ylw "[1/3] Postgres 容器与初始化 ..."
check "容器 ${PG_CONTAINER} 在运行"   podman inspect "${PG_CONTAINER}"
check "pg_isready 通过"               podman exec "${PG_CONTAINER}" pg_isready -U "${PG_USER}" -d "${PG_DB}"

if [[ "$(psql_q "SELECT 1 FROM pg_extension WHERE extname='vector'")" == "1" ]]; then
  pass "扩展 vector 已启用"
else
  miss "扩展 vector 未启用"
fi

for s in meta rag biz checkpoint; do
  if [[ "$(psql_q "SELECT 1 FROM information_schema.schemata WHERE schema_name='${s}'")" == "1" ]]; then
    pass "schema ${s} 已建立"
  else
    miss "schema ${s} 未建立"
  fi
done

for r in app_user biz_ro; do
  if [[ "$(psql_q "SELECT 1 FROM pg_roles WHERE rolname='${r}'")" == "1" ]]; then
    pass "账号 ${r} 已创建"
  else
    miss "账号 ${r} 未创建"
  fi
done

# ---------- 2) Backend 容器 ----------
ylw "[2/3] Backend 容器 ..."
check "容器 ${BE_CONTAINER} 在运行"   podman inspect "${BE_CONTAINER}"

if command -v curl >/dev/null 2>&1; then
    health_body="$(curl -fsS "${BACKEND_URL}/health" 2>/dev/null || true)"
    if [[ "${health_body}" == *'"status":"ok"'* ]]; then
        pass "${BACKEND_URL}/health 返回 status=ok"
    else
        miss "${BACKEND_URL}/health 异常或未启动 (响应=${health_body:-空})"
    fi

    docs_code="$(curl -fsS -o /dev/null -w "%{http_code}" "${BACKEND_URL}/docs" 2>/dev/null || echo "000")"
    if [[ "${docs_code}" == "200" ]]; then
        pass "Swagger /docs 可访问"
    else
        miss "Swagger /docs 不可访问 (HTTP ${docs_code})"
    fi
else
    ylw "  ! 跳过 HTTP 检查（宿主机无 curl）"
fi

# ---------- 3) Frontend 容器 ----------
ylw "[3/3] Frontend 容器 ..."
check "容器 ${FE_CONTAINER} 在运行"  podman inspect "${FE_CONTAINER}"

if command -v curl >/dev/null 2>&1; then
    fe_code="$(curl -fsS -o /dev/null -w "%{http_code}" "${FRONTEND_URL}/" 2>/dev/null || echo "000")"
    if [[ "${fe_code}" == "200" ]]; then
        pass "${FRONTEND_URL}/ 返回 200（Vite dev server 就绪）"
    else
        miss "${FRONTEND_URL}/ 异常 (HTTP ${fe_code})"
    fi
fi

# ---------- 容器内单测（可选） ----------
if [[ "${1:-}" == "--with-tests" ]]; then
    ylw "[+] 容器内 backend pytest ..."
    if podman exec "${BE_CONTAINER}" pytest -q; then
        pass "backend pytest 通过"
    else
        miss "backend pytest 失败"
    fi

    ylw "[+] 容器内 frontend vitest ..."
    if podman exec "${FE_CONTAINER}" pnpm test --run 2>/dev/null; then
        pass "frontend vitest 通过"
    else
        miss "frontend vitest 失败"
    fi
else
    ylw "[+] 已跳过单测 (使用 --with-tests 启用)"
fi

echo ""
green "OK : ${ok}"
[[ ${fail} -gt 0 ]] && red "FAIL: ${fail}"
exit $((fail == 0 ? 0 : 1))
