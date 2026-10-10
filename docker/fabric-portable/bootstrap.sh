#!/usr/bin/env bash
# All Fabric admin operations run in this Linux container on every host OS.
# This helper never removes a channel, resets volumes, or replays custody data.
set -euo pipefail
export FABRIC_CFG_PATH=/opt/fabric/config
runtime=/runtime
artifacts="$runtime/artifacts"
organizations="$runtime/organizations"
channel=nyayachannel
chaincode=nyayavault
version=1.0-portable
label=nyayavault_portable_1.0
policy="AND('Org1MSP.peer','Org2MSP.peer')"
orderer_tls="$organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls"
mkdir -p "$artifacts"
exec 9>"$runtime/bootstrap.lock"
flock -w 180 9 || { echo 'Another bootstrap operation is running.' >&2; exit 1; }

fail() { echo "ERROR: $*" >&2; exit 1; }
retry() {
  local attempt
  for attempt in $(seq 1 45); do
    if "$@"; then return 0; fi
    sleep 2
  done
  fail "Operation did not become ready: $*"
}
imported() { [ -f "$artifacts/imported-ledger.json" ]; }
validate_crypto() {
  local org
  test -s "$orderer_tls/server.crt" && test -s "$orderer_tls/server.key" && test -s "$orderer_tls/ca.crt" || fail 'Orderer identity is incomplete; restore the original identity backup.'
  for org in 1 2; do
    test -s "$organizations/peerOrganizations/org${org}.example.com/peers/peer0.org${org}.example.com/tls/server.crt" || fail "Org${org} peer identity is incomplete."
    test -d "$organizations/peerOrganizations/org${org}.example.com/users/Admin@org${org}.example.com/msp" || fail "Org${org} administrator identity is missing."
  done
  test -d "$organizations/peerOrganizations/org1.example.com/users/User1@org1.example.com/msp" || fail 'Gateway user identity is missing.'
}
init() {
  if imported; then
    jq -e --arg channel "$channel" '.channel == $channel' "$artifacts/imported-ledger.json" >/dev/null || fail 'Imported-ledger marker has an unexpected channel.'
    test -d "$organizations" || fail 'Imported ledger requires the original organizations; cryptogen is forbidden.'
    validate_crypto
  elif [ -d "$organizations" ]; then
    validate_crypto
  else
    # Generate into a staging directory so interruption cannot publish half an
    # identity tree. Existing published identities are never replaced.
    staging=$(mktemp -d "$runtime/crypto-building.XXXXXXXX")
    cryptogen generate --config=/bootstrap/crypto-config.yaml --output="$staging/organizations"
    mv "$staging/organizations" "$organizations"
    rmdir "$staging"
    validate_crypto
  fi
  mkdir -p "$runtime/gateway-identity"
  source_msp="$organizations/peerOrganizations/org1.example.com/users/User1@org1.example.com/msp"
  shopt -s nullglob
  certs=("$source_msp"/signcerts/*)
  keys=("$source_msp"/keystore/*)
  [ "${#certs[@]}" -eq 1 ] && [ "${#keys[@]}" -eq 1 ] || fail 'Gateway user must have exactly one original signing certificate and key.'
  for entry in cert.pem key.pem tls.crt; do
    case "$entry" in
      cert.pem) source="${certs[0]}" ;;
      key.pem) source="${keys[0]}" ;;
      tls.crt) source="$organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" ;;
    esac
    if [ -e "$runtime/gateway-identity/$entry" ]; then
      cmp -s "$source" "$runtime/gateway-identity/$entry" || fail "Existing gateway $entry differs from original Org1 identity."
    else
      cp "$source" "$runtime/gateway-identity/$entry"
    fi
    chmod 644 "$runtime/gateway-identity/$entry"
  done
  chmod 755 "$runtime" "$runtime/gateway-identity" "$artifacts"
  implementation_hash=$(cat /implementation/index.js /implementation/package.json /implementation/package-lock.json | sha256sum | cut -d' ' -f1)
  if [ -f "$artifacts/implementation.sha256" ]; then
    [ "$(cat "$artifacts/implementation.sha256")" = "$implementation_hash" ] || fail 'Chaincode implementation changed; an explicit reviewed lifecycle upgrade is required.'
  fi
  if [ ! -s "$artifacts/chaincode.tgz" ]; then
    staging=$(mktemp -d "$artifacts/package-building.XXXXXXXX")
    printf '%s\n' '{"address":"{{.peername}}:9999","dial_timeout":"10s","tls_required":false}' >"$staging/connection.json"
    printf '{"type":"ccaas","label":"%s"}\n' "$label" >"$staging/metadata.json"
    tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -czf "$staging/code.tar.gz" -C "$staging" connection.json
    tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -czf "$staging/package.tgz" -C "$staging" metadata.json code.tar.gz
    mv "$staging/package.tgz" "$artifacts/chaincode.tgz"
    rm -rf "$staging"
  fi
  use_org 1
  package_id=$(peer lifecycle chaincode calculatepackageid "$artifacts/chaincode.tgz")
  case "$package_id" in "$label":*) ;; *) fail 'Existing chaincode package does not have the expected portable label.' ;; esac
  if [ -f "$artifacts/chaincode-id.txt" ]; then
    [ "$(cat "$artifacts/chaincode-id.txt")" = "$package_id" ] || fail 'Stored chaincode package ID does not match the package bytes.'
  else
    printf '%s\n' "$package_id" >"$artifacts/chaincode-id.txt.tmp"
    mv "$artifacts/chaincode-id.txt.tmp" "$artifacts/chaincode-id.txt"
  fi
  printf '%s\n' "$implementation_hash" >"$artifacts/implementation.sha256"
  if ! imported && [ ! -s "$artifacts/channel.block" ]; then
    FABRIC_CFG_PATH=/bootstrap configtxgen -profile NyayaVaultChannel -channelID "$channel" -outputBlock "$artifacts/channel.block.tmp"
    mv "$artifacts/channel.block.tmp" "$artifacts/channel.block"
  fi
  echo 'Fabric identities and portable chaincode package are ready; existing keys were retained.'
}
use_org() {
  local org="$1" port=7051
  [ "$org" = 2 ] && port=9051
  export CORE_PEER_TLS_ENABLED=true
  export CORE_PEER_LOCALMSPID="Org${org}MSP"
  export CORE_PEER_ADDRESS="peer0.org${org}.example.com:$port"
  export CORE_PEER_TLS_ROOTCERT_FILE="$organizations/peerOrganizations/org${org}.example.com/peers/peer0.org${org}.example.com/tls/ca.crt"
  export CORE_PEER_MSPCONFIGPATH="$organizations/peerOrganizations/org${org}.example.com/users/Admin@org${org}.example.com/msp"
}
osn() {
  osnadmin channel "$@" -o orderer.example.com:7053 --ca-file "$orderer_tls/ca.crt" --client-cert "$orderer_tls/server.crt" --client-key "$orderer_tls/server.key" --no-status
}
list_orderer() { osn list >"$artifacts/orderer-channels.json"; }
orderer_leader_ready() {
  curl -fsS --connect-timeout 2 --max-time 5 http://orderer.example.com:9443/metrics >"$artifacts/orderer-metrics.txt" || return 1
  grep -Eq "^consensus_etcdraft_is_leader\\{[^}]*channel=\"$channel\"[^}]*\\}[[:space:]]+1(\\.0+)?([[:space:]]|$)" "$artifacts/orderer-metrics.txt"
}
peer_ready() { peer channel list >"$artifacts/peer-channels-${CORE_PEER_LOCALMSPID}.txt"; }
joined() { grep -Fxq "$channel" "$artifacts/peer-channels-${CORE_PEER_LOCALMSPID}.txt"; }
query_committed() {
  peer lifecycle chaincode querycommitted -C "$channel" --output json >"$artifacts/definitions-${CORE_PEER_LOCALMSPID}.json"
}
query_approved() {
  peer lifecycle chaincode queryapproved -C "$channel" -n "$chaincode" --sequence "$sequence" --output json >"$artifacts/approval-${CORE_PEER_LOCALMSPID}.json"
}
policy_matches() {
  # Decode the committed protobuf policy, then inspect both MSP peer principals
  # and the exact two-of-two signature rule rather than trusting a text label.
  test -s "$1" || return 1
  jq -er -s 'if length == 1 then .[0].validation_parameter | select(type == "string" and length > 0) else error("Expected one policy object") end' "$1" | base64 -d >"$artifacts/policy.pb" || return 1
  test -s "$artifacts/policy.pb" || return 1
  # Fabric 2.5's registered protobuf names differ from source package paths.
  # Explicit guards are required: Bash suppresses errexit inside an if-tested
  # function, and jq may exit successfully without reading any JSON value.
  rm -f "$artifacts/policy.json"
  configtxlator proto_decode --type protos.ApplicationPolicy --input "$artifacts/policy.pb" --output "$artifacts/policy.json" || return 1
  test -s "$artifacts/policy.json" || return 1
  jq -e -s 'length == 1 and (.[0] | .signature_policy.rule.n_out_of.n == 2 and (.signature_policy.rule.n_out_of.rules | length) == 2 and (.signature_policy.identities | length) == 2 and .signature_policy.rule.n_out_of.rules[0].signed_by == 0 and .signature_policy.rule.n_out_of.rules[1].signed_by == 1 and .signature_policy.identities[0].principal_classification == "ROLE" and .signature_policy.identities[1].principal_classification == "ROLE")' "$artifacts/policy.json" >/dev/null || return 1
  local index org
  for index in 0 1; do
    org=$((index + 1))
    jq -er ".signature_policy.identities[$index].principal | select(type == \"string\" and length > 0)" "$artifacts/policy.json" | base64 -d >"$artifacts/principal.pb" || return 1
    test -s "$artifacts/principal.pb" || return 1
    rm -f "$artifacts/principal.json"
    configtxlator proto_decode --type common.MSPRole --input "$artifacts/principal.pb" --output "$artifacts/principal.json" || return 1
    test -s "$artifacts/principal.json" || return 1
    jq -e -s --arg msp "Org${org}MSP" 'length == 1 and .[0].msp_identifier == $msp and .[0].role == "PEER"' "$artifacts/principal.json" >/dev/null || return 1
  done
}
approved_exact() {
  query_approved >/dev/null 2>&1 || return 1
  test -s "$artifacts/approval-${CORE_PEER_LOCALMSPID}.json" || return 1
  jq -e -s --arg id "$package_id" --arg version "$version" --argjson sequence "$sequence" 'length == 1 and .[0].version == $version and .[0].sequence == $sequence and .[0].source.Type.LocalPackage.package_id == $id and (.[0].init_required // false) == false' "$artifacts/approval-${CORE_PEER_LOCALMSPID}.json" >/dev/null || return 1
  policy_matches "$artifacts/approval-${CORE_PEER_LOCALMSPID}.json" || return 1
}
committed_exact() {
  peer lifecycle chaincode querycommitted -C "$channel" -n "$chaincode" --output json >"$artifacts/committed-${CORE_PEER_LOCALMSPID}.json" 2>/dev/null || return 1
  test -s "$artifacts/committed-${CORE_PEER_LOCALMSPID}.json" || return 1
  jq -e -s --arg version "$version" --argjson sequence "$sequence" 'length == 1 and .[0].version == $version and .[0].sequence == $sequence and (.[0].init_required // false) == false' "$artifacts/committed-${CORE_PEER_LOCALMSPID}.json" >/dev/null || return 1
  policy_matches "$artifacts/committed-${CORE_PEER_LOCALMSPID}.json" || return 1
}
transient_lifecycle_error() {
  # Identity, policy and validation failures need intervention. Retry only
  # explicitly recognized transport, leader-election and event-wait failures.
  grep -Eiq 'x509:|certificate|access denied|permission denied|BAD_REQUEST|ENDORSEMENT_POLICY_FAILURE|MVCC_READ_CONFLICT|invalid signature|invalid sequence' "$1" && return 1
  grep -Eiq 'SERVICE_UNAVAILABLE|no Raft leader|connection refused|connection reset|transport is closing|code = Unavailable|context deadline exceeded|timed out waiting|timeout expired|failed to read from deliver stream|failed to connect' "$1"
}
retry_lifecycle() {
  local kind="$1" attempt log confirmation
  shift
  log="$artifacts/lifecycle-${CORE_PEER_LOCALMSPID}-${kind}.log"
  case "$kind" in approve) confirmation=approved_exact ;; commit) confirmation=committed_exact ;; *) fail 'Unexpected lifecycle operation.' ;; esac
  for attempt in $(seq 1 12); do
    # A previous submit may have committed even when its event stream timed
    # out. Check state before resubmitting to prevent duplicate lifecycle work.
    if "$confirmation"; then return 0; fi
    if "$@" >"$log" 2>&1; then cat "$log"; return 0; fi
    cat "$log" >&2
    if "$confirmation"; then
      echo "The $kind transaction committed despite the interrupted response."
      return 0
    fi
    transient_lifecycle_error "$log" || fail "Permanent or unrecognized $kind error; no automatic retry."
    [ "$attempt" -lt 12 ] || fail "Transient $kind errors persisted through 12 attempts."
    echo "Waiting for Fabric to finish starting before retrying $kind ($attempt/12)."
    sleep 2
  done
}
commit_readiness() {
  peer lifecycle chaincode checkcommitreadiness "${definition_args[@]}" --output json >"$artifacts/readiness.json" 2>"$artifacts/readiness-error.log" || {
    transient_lifecycle_error "$artifacts/readiness-error.log" && return 1
    cat "$artifacts/readiness-error.log" >&2
    fail 'Permanent or unrecognized commit-readiness error.'
  }
  test -s "$artifacts/readiness.json" || return 1
  jq -e -s 'length == 1 and ((.[0].approvals // .[0].Approvals).Org1MSP == true and (.[0].approvals // .[0].Approvals).Org2MSP == true)' "$artifacts/readiness.json" >/dev/null
}
setup() {
  validate_crypto
  test -s "$artifacts/chaincode-id.txt" || fail 'Run fabric-bootstrap init before setup.'
  package_id=$(cat "$artifacts/chaincode-id.txt")
  retry list_orderer
  if ! jq -e --arg channel "$channel" '.channels[]? | select(.name == $channel)' "$artifacts/orderer-channels.json" >/dev/null; then
    imported && fail 'Restored orderer is missing the original channel; restore its ledger instead of creating a new channel.'
    test -s "$artifacts/channel.block" || fail 'Channel genesis artifact is missing.'
    osn join --channelID "$channel" --config-block "$artifacts/channel.block"
    retry list_orderer
  fi
  # Channel-participation status "active" only means the ledger is joined;
  # broadcasting lifecycle transactions additionally needs the Raft leader.
  retry orderer_leader_ready
  for org in 1 2; do
    use_org "$org"
    retry peer_ready
    if ! joined; then
      imported && fail "Restored Org${org} peer is missing the original channel; restore its ledger."
      peer channel join -b "$artifacts/channel.block"
      retry peer_ready
      joined || fail "Org${org} did not join the channel."
    fi
    retry query_committed
  done
  # Read all definitions successfully first; a failed query must never be
  # mistaken for an empty ledger and trigger a replacement deployment.
  jq --arg name "$chaincode" '.chaincode_definitions[]? | select(.name == $name)' "$artifacts/definitions-Org1MSP.json" >"$artifacts/current-definition.json"
  jq --arg name "$chaincode" '.chaincode_definitions[]? | select(.name == $name)' "$artifacts/definitions-Org2MSP.json" >"$artifacts/current-definition-org2.json"
  cmp -s "$artifacts/current-definition.json" "$artifacts/current-definition-org2.json" || fail 'Peers disagree on the current definition; wait for synchronization and rerun setup.'
  committed=false
  if [ -s "$artifacts/current-definition.json" ]; then
    current_version=$(jq -r '.version' "$artifacts/current-definition.json")
    current_sequence=$(jq -r '.sequence' "$artifacts/current-definition.json")
    [[ "$current_sequence" =~ ^[1-9][0-9]*$ ]] || fail 'Current definition sequence is invalid.'
    if [ "$current_version" = "$version" ]; then
      sequence="$current_sequence"
      committed=true
    elif imported && [ "$current_version" = 1.0 ]; then
      sequence=$((current_sequence + 1))
      echo "Upgrading only the restored ledger's chaincode runtime to CCAAS (sequence $sequence); original evidence events and transaction IDs remain intact."
    else
      fail "Unexpected existing definition version $current_version; automatic redeployment refused."
    fi
  else
    imported && fail 'Imported ledger has no original NyayaVault definition; refusing a fresh deployment.'
    sequence=1
  fi
  orderer_args=(-o orderer.example.com:7050 --ordererTLSHostnameOverride orderer.example.com --tls --cafile "$orderer_tls/ca.crt")
  definition_args=(-C "$channel" -n "$chaincode" --version "$version" --sequence "$sequence" --signature-policy "$policy")
  peer_args=(--peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles "$organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" --peerAddresses peer0.org2.example.com:9051 --tlsRootCertFiles "$organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt")
  for org in 1 2; do
    use_org "$org"
    peer lifecycle chaincode queryinstalled --output json >"$artifacts/installed-Org${org}MSP.json"
    if ! jq -e --arg id "$package_id" '.installed_chaincodes[]? | select(.package_id == $id)' "$artifacts/installed-Org${org}MSP.json" >/dev/null; then
      peer lifecycle chaincode install "$artifacts/chaincode.tgz"
    fi
    approved=false
    if approved_exact; then approved=true; fi
    if [ "$approved" = false ]; then
      [ "$committed" = false ] || fail "Committed portable definition has an unexpected Org${org} package or policy; refusing to silently change it."
      retry_lifecycle approve peer lifecycle chaincode approveformyorg "${orderer_args[@]}" "${definition_args[@]}" --package-id "$package_id" --waitForEvent --waitForEventTimeout 30s
    fi
  done
  use_org 1
  if [ "$committed" = false ]; then
    retry commit_readiness
    retry_lifecycle commit peer lifecycle chaincode commit "${orderer_args[@]}" "${definition_args[@]}" "${peer_args[@]}" --waitForEvent --waitForEventTimeout 30s
  fi
  for org in 1 2; do
    use_org "$org"
    peer lifecycle chaincode querycommitted -C "$channel" -n "$chaincode" --output json >"$artifacts/committed-Org${org}MSP.json"
    jq -e --arg version "$version" --argjson sequence "$sequence" '.version == $version and .sequence == $sequence and (.init_required // false) == false' "$artifacts/committed-Org${org}MSP.json" >/dev/null || fail "Org${org} committed definition differs."
    policy_matches "$artifacts/committed-Org${org}MSP.json" || fail "Org${org} endorsement policy is not both peers."
    retry query_approved
    jq -e --arg id "$package_id" '.source.Type.LocalPackage.package_id == $id' "$artifacts/approval-${CORE_PEER_LOCALMSPID}.json" >/dev/null || fail "Org${org} approved package differs."
    retry peer chaincode query -C "$channel" -n "$chaincode" -c '{"Args":["Health"]}'
  done
  imported_json=false
  imported && imported_json=true
  jq -n --arg channel "$channel" --arg version "$version" --argjson sequence "$sequence" --arg package_id "$package_id" --argjson imported "$imported_json" --arg completed_at "$(date -u +%FT%TZ)" '{channel:$channel,organizations:["Org1MSP","Org2MSP"],peer_count:2,orderer_count:1,chaincode_version:$version,sequence:$sequence,package_id:$package_id,endorsement_policy:"AND(Org1MSP.peer,Org2MSP.peer)",imported_ledger:$imported,completed_at:$completed_at}' >"$artifacts/setup-result.json.tmp"
  mv "$artifacts/setup-result.json.tmp" "$artifacts/setup-result.json"
  echo 'Two organizations, two peers and one shared channel are ready. Bootstrap is safe to rerun.'
}
case "${1:-setup}" in
  init) init ;;
  setup) setup ;;
  *) fail 'Use init (before network start) or setup (after peers and orderer start).' ;;
esac
