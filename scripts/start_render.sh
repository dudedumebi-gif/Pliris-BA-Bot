#!/usr/bin/env bash
set -Eeuo pipefail

PUBLIC_PORT="${PORT:-10000}"
API_PORT="${PLIRIS_INTERNAL_API_PORT:-8000}"
API_HOST="127.0.0.1"
API_URL="http://${API_HOST}:${API_PORT}"

export API_URL
export PLIRIS_UI_MODE="${PLIRIS_UI_MODE:-public}"

api_pid=""
ui_pid=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if [[ -n "${ui_pid}" ]]; then
    kill "${ui_pid}" 2>/dev/null || true
  fi
  if [[ -n "${api_pid}" ]]; then
    kill "${api_pid}" 2>/dev/null || true
  fi

  wait "${ui_pid}" 2>/dev/null || true
  wait "${api_pid}" 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

uvicorn api.main:app   --host "${API_HOST}"   --port "${API_PORT}" &
api_pid=$!

for _ in $(seq 1 45); do
  if curl --fail --silent --show-error     "${API_URL}/health/live" >/dev/null; then
    break
  fi

  if ! kill -0 "${api_pid}" 2>/dev/null; then
    echo "FastAPI exited before becoming healthy." >&2
    wait "${api_pid}"
  fi

  sleep 1
done

if ! curl --fail --silent --show-error   "${API_URL}/health/live" >/dev/null; then
  echo "FastAPI did not become healthy within 45 seconds." >&2
  exit 1
fi

streamlit run streamlit_app.py   --server.address 0.0.0.0   --server.port "${PUBLIC_PORT}"   --server.headless true   --browser.gatherUsageStats false &
ui_pid=$!

wait -n "${api_pid}" "${ui_pid}"
