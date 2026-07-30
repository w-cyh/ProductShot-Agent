#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.local"
RUNTIME_DIR="$ROOT_DIR/.dev-services"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.local.example and configure your SSH host alias." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${DATABASE_URL:?$ENV_FILE must export DATABASE_URL}"
: "${CELERY_BROKER_URL:?$ENV_FILE must export CELERY_BROKER_URL}"
: "${CELERY_RESULT_BACKEND:?$ENV_FILE must export CELERY_RESULT_BACKEND}"

is_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

start_tunnel() {
  local local_port="$1"
  local remote_port="$2"
  if is_listening "$local_port"; then
    return
  fi
  ssh -f -N \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -L "127.0.0.1:${local_port}:127.0.0.1:${remote_port}" \
    "$PRODUCTSHOT_DEV_SSH_HOST"
}

start_process() {
  local name="$1"
  local working_dir="$2"
  shift 2
  local pid_file="$RUNTIME_DIR/${name}.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$pid_file"))."
    return
  fi
  (
    cd "$working_dir"
    exec nohup "$@" >"$RUNTIME_DIR/${name}.log" 2>&1
  ) &
  echo $! >"$pid_file"
  echo "Started $name (pid $!)."
}

project_count() {
  local database_url="$1"
  (
    cd "$ROOT_DIR/backend"
    DATABASE_URL="$database_url" "$ROOT_DIR/backend/.venv/bin/python" -c '
from sqlalchemy import create_engine, text
from app.config import settings

with create_engine(settings.database_url).connect() as connection:
    print(connection.execute(text("SELECT COUNT(*) FROM projects")).scalar_one())
'  ) 2>/dev/null
}

guard_against_empty_remote_history() {
  local sqlite_history="$ROOT_DIR/backend/data/productshot.db"
  if [[ ! -f "$sqlite_history" || "${PRODUCTSHOT_ALLOW_EMPTY_REMOTE_DB:-0}" == "1" ]]; then
    return
  fi

  local local_count remote_count
  local_count="$(project_count "sqlite:///$sqlite_history")"
  remote_count="$(project_count "$DATABASE_URL")"
  if [[ "$local_count" -gt 0 && "$remote_count" -eq 0 ]]; then
    echo "PostgreSQL is empty while local SQLite contains $local_count project(s)." >&2
    echo "Import history first: source .env.local && backend/.venv/bin/python backend/scripts/import_sqlite_history.py" >&2
    echo "Set PRODUCTSHOT_ALLOW_EMPTY_REMOTE_DB=1 only when an empty remote database is intentional." >&2
    exit 1
  fi
}

stop_process() {
  local name="$1"
  local pid_file="$RUNTIME_DIR/${name}.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    kill "$(cat "$pid_file")"
    echo "Stopped $name."
  fi
  rm -f "$pid_file"
}

case "${1:-start}" in
  start)
    mkdir -p "$RUNTIME_DIR"
    start_tunnel "$PRODUCTSHOT_REDIS_LOCAL_PORT" 6379
    start_tunnel "$PRODUCTSHOT_POSTGRES_LOCAL_PORT" 5432
    (
      cd "$ROOT_DIR/backend"
      "$ROOT_DIR/backend/.venv/bin/alembic" upgrade head
    )
    guard_against_empty_remote_history
    if is_listening 8000; then
      echo "API port 8000 is already in use; leaving the existing API process untouched."
    else
      start_process api "$ROOT_DIR/backend" "$ROOT_DIR/backend/.venv/bin/uvicorn" app.main:app --reload --port 8000
    fi
    start_process worker "$ROOT_DIR/backend" "$ROOT_DIR/backend/.venv/bin/celery" -A app.celery_app.celery_app worker --loglevel=INFO
    if is_listening 5173; then
      echo "Frontend port 5173 is already in use; leaving the existing frontend process untouched."
    else
      start_process frontend "$ROOT_DIR" npm --prefix "$ROOT_DIR/frontend" run dev -- --host 127.0.0.1
    fi
    echo "Ready: frontend http://127.0.0.1:5173, API http://127.0.0.1:8000"
    ;;
  stop)
    stop_process frontend
    stop_process worker
    stop_process api
    echo "SSH tunnels are left running for reuse."
    ;;
  status)
    for name in api worker frontend; do
      pid_file="$RUNTIME_DIR/${name}.pid"
      if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "$name: running (pid $(cat "$pid_file"))"
      elif [[ "$name" == "api" ]] && is_listening 8000; then
        echo "api: running (existing process on port 8000)"
      elif [[ "$name" == "frontend" ]] && is_listening 5173; then
        echo "frontend: running (existing process on port 5173)"
      else
        echo "$name: stopped"
      fi
    done
    ;;
  *)
    echo "Usage: $0 [start|stop|status]" >&2
    exit 2
    ;;
esac
