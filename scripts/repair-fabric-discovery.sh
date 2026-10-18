#!/usr/bin/env bash
# Repair missing legacy Fabric anchor peers without resetting ledger data.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1 && [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi
orgs="$PWD/blockchain/runtime/fabric-samples/test-network/organizations"
[ -d "$orgs/peerOrganizations" ] || { echo 'Existing legacy Fabric identities are required.' >&2; exit 1; }
for service in peer0.org1.example.com peer0.org2.example.com orderer.example.com; do
  [ "$(docker inspect --format '{{.State.Running}}' "$service")" = true ] || { echo "Start the existing network before repair: $service is stopped." >&2; exit 1; }
done
umask 077
mkdir -p blockchain/runtime/anchor-repair
repair_dir=$(mktemp -d "$PWD/blockchain/runtime/anchor-repair/run-XXXXXX")
image=nyayavault-fabric-admin:2.5.16
docker build -t "$image" -f docker/fabric-portable/Dockerfile .
docker run --rm --network fabric_test --entrypoint bash \
  -v "$orgs:/orgs:ro" \
  -v "$repair_dir:/repair" \
  -v "$PWD/scripts/fabric-anchor-update.sh:/anchor-update.sh:ro" \
  "$image" /anchor-update.sh
echo "Anchor configuration checked. Private before/after configuration retained in $repair_dir"
echo 'Existing anchors are not overwritten. No evidence event is replayed by this script.'
