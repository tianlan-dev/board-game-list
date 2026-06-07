#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env.production.local}"
LOG_DIR="$SCRIPT_DIR/.server-logs"
ACTION="${1:-start}"

new_log_file() {
  mkdir -p "$LOG_DIR"
  printf '%s/production-%s-%s.log\n' "$LOG_DIR" "$1" "$(date +%Y%m%d-%H%M%S)"
}

load_env() {
  local require_port="${1:-true}"

  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ "$require_port" == "false" ]]; then
      return 0
    fi
    echo "Environment file not found: $ENV_FILE" >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  if [[ "$require_port" == "true" ]]; then
    : "${APP_PORT:?APP_PORT is required}"
  fi
}

image_name() {
  printf '%s\n' "${DOCKER_IMAGE_NAME:-board-game-list:local}"
}

container_name() {
  printf '%s\n' "${DOCKER_CONTAINER_NAME:-board-game-list}"
}

stop_container() {
  local action="${1:-stop}"
  load_env false

  local container log_file
  container="$(container_name)"
  log_file="$(new_log_file "$action")"

  echo "Stopping production container: $container"
  echo "Log: $log_file"
  {
    date
    echo "Action: $action"
    if docker ps -a --format '{{.Names}}' | grep -Fxq "$container"; then
      echo "Stopping production container: $container"
      docker rm -f "$container"
    else
      echo "Production container is not running: $container"
    fi
  } >"$log_file" 2>&1
}

start_container() {
  local action="${1:-start}"
  load_env true

  local image container log_file
  image="$(image_name)"
  container="$(container_name)"
  log_file="$(new_log_file "$action")"

  echo "Starting production container: $container"
  echo "Log: $log_file"
  {
    date
    echo "Action: $action"
    docker build -t "$image" "$SCRIPT_DIR"
    docker rm -f "$container" >/dev/null 2>&1 || true
    docker run -d \
      --name "$container" \
      --restart unless-stopped \
      --read-only \
      --tmpfs /tmp \
      --cap-drop ALL \
      --security-opt no-new-privileges:true \
      --env-file "$ENV_FILE" \
      -p "127.0.0.1:$APP_PORT:$APP_PORT" \
      "$image"
  } >"$log_file" 2>&1
}

case "$ACTION" in
  start) start_container start ;;
  stop) stop_container stop ;;
  restart) start_container restart ;;
  *)
    echo "Usage: $0 [start|stop|restart]" >&2
    exit 1
    ;;
esac
