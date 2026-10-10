#!/bin/sh
# No Fabric peer Docker socket is needed: this is a regular Compose service.
set -eu
id_file="${CHAINCODE_ID_FILE:-/runtime/artifacts/chaincode-id.txt}"
attempt=0
until [ -s "$id_file" ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 180 ]; then
    echo 'Chaincode package ID is missing. Run fabric-bootstrap init first.' >&2
    exit 1
  fi
  sleep 1
done
chaincode_id=$(cat "$id_file")
case "$chaincode_id" in
  nyayavault_portable_1.0:*) ;;
  *) echo 'Unexpected portable chaincode package ID; refusing to start.' >&2; exit 1 ;;
esac
exec ./node_modules/.bin/fabric-chaincode-node server --chaincode-address=0.0.0.0:9999 --chaincode-id="$chaincode_id"
