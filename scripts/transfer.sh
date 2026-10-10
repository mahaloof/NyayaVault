#!/usr/bin/env bash
# Linux/macOS/WSL export/import companion to Windows Export.ps1 and Import.ps1.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1 && [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi
[ "$(docker info --format '{{.OSType}}')" = linux ] || { echo 'Start Docker with Linux containers.' >&2; exit 1; }
action="${1:-}"; shift || true
snapshot_path="${1:-transfer/current}"
case "$snapshot_path" in /*|*..*) echo 'Use a transfer folder inside the project.' >&2; exit 1;; esac
root="$PWD"; image=nyayavault-portable-tools:1.0
docker build -t "$image" -f docker/portable-tools/Dockerfile .
helper=(docker run --rm -v "$root:/project" -v /var/run/docker.sock:/var/run/docker.sock "$image" python)
case "$action" in
  export|export-legacy)
    source=portable; [ "$action" = export-legacy ] && source=legacy
    "${helper[@]}" /workspace/scripts/transfer.py export --source "$source" --output "/project/$snapshot_path"
    ;;
  import)
    "${helper[@]}" /workspace/scripts/transfer.py restore --input "/project/$snapshot_path"
    bash scripts/portable.sh start --no-demo
    "${helper[@]}" /workspace/scripts/portable_verify.py --container nyayavault-portable-backend-1 --baseline "/project/$snapshot_path/baseline.json" --outputfile /project/docs/portability-restore-results.json
    ;;
  *) echo 'Usage: bash scripts/transfer.sh export|export-legacy|import [transfer/folder]' >&2; exit 1;;
esac
