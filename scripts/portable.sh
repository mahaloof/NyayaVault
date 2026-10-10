#!/usr/bin/env bash
# Docker-only equivalent of scripts/windows/Start.ps1, for macOS, Linux and WSL.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1 && [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi
if ! command -v docker >/dev/null 2>&1; then
  echo 'Docker was not found. Install and start Docker Desktop, then retry.' >&2
  exit 1
fi
if [ "$(docker info --format '{{.OSType}}' 2>/dev/null || true)" != linux ]; then
  echo 'Start Docker Desktop with Linux containers (WSL 2 on Windows), then retry.' >&2
  exit 1
fi
docker compose version >/dev/null
# Make the retained portable file authoritative instead of inherited shell
# credentials or keys. This script runs in its own process.
unset COMPOSE_FILE COMPOSE_PROFILES POSTGRES_PASSWORD MINIO_ACCESS_KEY MINIO_SECRET_KEY \
  JWT_SECRET EVIDENCE_MASTER_KEY FABRIC_GATEWAY_SECRET FRONTEND_PORT BACKEND_PORT MINIO_CONSOLE_PORT
project_root="$PWD"
tools_image='nyayavault-portable-tools:1.0'
compose=(docker compose --project-name nyayavault-portable --env-file "$project_root/.env.portable" -f "$project_root/docker-compose.portable.yml")

require_config() {
  if [ ! -f .env.portable ]; then
    echo 'Portable configuration is missing. Run the start command or restore the original .env.portable with your backup.' >&2
    exit 1
  fi
}
show_urls() {
  docker run --rm --volume "$project_root:/project:ro" "$tools_image" python /opt/nyayavault/config.py urls
}
action="${1:-start}"
if [ "$#" -gt 0 ]; then shift; fi
case "$action" in
  start)
    no_demo=0
    frontend_port=3001
    backend_port=8001
    minio_console_port=9001
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --no-demo) no_demo=1; shift ;;
        --frontend-port|--backend-port|--minio-console-port)
          if [ "$#" -lt 2 ]; then echo "Missing port after $1" >&2; exit 1; fi
          case "$1" in
            --frontend-port) frontend_port="$2" ;;
            --backend-port) backend_port="$2" ;;
            --minio-console-port) minio_console_port="$2" ;;
          esac
          shift 2 ;;
        *) echo "Unknown start option: $1" >&2; exit 1 ;;
      esac
    done
    docker build --tag "$tools_image" --file docker/portable-tools/Dockerfile .
    docker run --rm --volume "$project_root:/project" "$tools_image" python /opt/nyayavault/config.py ensure --frontend-port "$frontend_port" --backend-port "$backend_port" --minio-console-port "$minio_console_port"
    "${compose[@]}" --profile tools build
    "${compose[@]}" --profile tools run --rm --no-deps fabric-bootstrap init
    "${compose[@]}" up -d --force-recreate
    "${compose[@]}" --profile tools run --rm --no-deps fabric-bootstrap setup
    "${compose[@]}" --profile tools run --rm --no-deps tools python /opt/nyayavault/config.py wait --url http://backend:8000/api/health --url http://frontend:3000 --timeout 180
    if [ "$no_demo" -eq 0 ]; then
      "${compose[@]}" --profile tools run --rm --no-deps demo
    fi
    echo 'NyayaVault is ready. Its database, encrypted evidence, identities and blockchain stay in Docker volumes.'
    show_urls
    ;;
  stop)
    if [ "$#" -ne 0 ]; then echo 'The stop command does not take options.' >&2; exit 1; fi
    require_config
    "${compose[@]}" stop
    echo 'NyayaVault stopped. All database, evidence, keys and blockchain volumes were retained.'
    ;;
  status)
    if [ "$#" -ne 0 ]; then echo 'The status command does not take options.' >&2; exit 1; fi
    require_config
    "${compose[@]}" ps -a
    show_urls
    ;;
  *)
    echo 'Usage: bash scripts/portable.sh start [--no-demo] [--frontend-port PORT --backend-port PORT --minio-console-port PORT] | stop | status' >&2
    exit 1
    ;;
esac
