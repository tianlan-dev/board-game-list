#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env.development.local}"
LOG_DIR="$SCRIPT_DIR/.server-logs"
ACTION="${1:-start}"
NEEDS_BUILD=false

new_log_file() {
  mkdir -p "$LOG_DIR"
  printf '%s/development-%s-%s.log\n' "$LOG_DIR" "$1" "$(date +%Y%m%d-%H%M%S)"
}

load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Environment file not found: $ENV_FILE" >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  : "${APP_PORT:?APP_PORT is required}"
}

stop_server() {
  local action="${1:-stop}"
  load_env
  local log_file
  log_file="$(new_log_file "$action")"

  echo "Stopping development server on port $APP_PORT"
  echo "Log: $log_file"
  {
    date
    echo "Action: $action"
    stop_server_on_port
  } >"$log_file" 2>&1
}

stop_server_on_port() {
  local pids
  pids="$(lsof -tiTCP:"$APP_PORT" -sTCP:LISTEN || true)"
  if [[ -n "$pids" ]]; then
    echo "Stopping development server on port $APP_PORT"
    kill $pids 2>/dev/null || true
  else
    echo "Development server is not running on port $APP_PORT"
  fi
}

start_server() {
  local action="${1:-start}"
  load_env
  local log_file
  log_file="$(new_log_file "$action")"

  echo "Starting development server on port $APP_PORT"
  echo "Log: $log_file"
  nohup perl -MPOSIX=setsid -e 'setsid or die "setsid: $!"; exec @ARGV' bash -c '
    cd "$1"
    action="$2"
    app_port="$3"
    needs_build="$4"
    date
    echo "Action: $action"
    echo "Stopping existing development server on port $app_port"
    pids="$(lsof -tiTCP:"$app_port" -sTCP:LISTEN || true)"
    if [[ -n "$pids" ]]; then
      kill $pids 2>/dev/null || true
    else
      echo "Development server is not running on port $app_port"
    fi
    if [[ "$needs_build" == "true" ]]; then
      npm run build
    fi
    exec npm run start
  ' bash "$SCRIPT_DIR" "$action" "$APP_PORT" "$NEEDS_BUILD" >"$log_file" 2>&1 &
}

case "$ACTION" in
  start) start_server ;;
  stop) stop_server ;;
  restart) start_server restart ;;
  *)
    echo "Usage: $0 [start|stop|restart]" >&2
    exit 1
    ;;
esac
