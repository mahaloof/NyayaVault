#!/usr/bin/env bash
# Resume an already provisioned network without resetting its ledger or identities.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1 && [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi
runtime="$PWD/blockchain/runtime/fabric-samples/test-network"
if [ ! -d "$runtime/organizations/peerOrganizations" ]; then
  echo 'Fabric has not been provisioned. See docs/FABRIC.md.' >&2
  exit 1
fi
exec bash scripts/docker.sh -f docker-compose.yml -f docker-compose.fabric.yml -f docker-compose.network.yml up -d
