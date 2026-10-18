#!/usr/bin/env bash
# Run inside the Fabric admin container via repair-fabric-discovery.sh.
# Add only missing anchor peers; existing configured anchors remain untouched.
set -euo pipefail
umask 077
export CORE_PEER_TLS_ENABLED=true
for org in 1 2; do
 export CORE_PEER_LOCALMSPID=Org${org}MSP
 export CORE_PEER_MSPCONFIGPATH=/orgs/peerOrganizations/org${org}.example.com/users/Admin@org${org}.example.com/msp
 export CORE_PEER_TLS_ROOTCERT_FILE=/orgs/peerOrganizations/org${org}.example.com/peers/peer0.org${org}.example.com/tls/ca.crt
 port=7051; [ "$org" = 1 ] || port=9051
 export CORE_PEER_ADDRESS=peer0.org${org}.example.com:$port
 cd /repair
 peer channel fetch config config-${org}.pb -o orderer.example.com:7050 -c nyayachannel --tls --cafile /orgs/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt
 configtxlator proto_decode --input config-${org}.pb --type common.Block | jq .data.data[0].payload.data.config > original-${org}.json
 if jq -e --arg m "$CORE_PEER_LOCALMSPID" '.channel_group.groups.Application.groups[$m].values.AnchorPeers.value.anchor_peers | length > 0' original-${org}.json >/dev/null; then echo "Org${org} already has anchors";continue;fi
 jq --arg m "$CORE_PEER_LOCALMSPID" --arg host "peer0.org${org}.example.com" --argjson port "$port" '.channel_group.groups.Application.groups[$m].values.AnchorPeers={"mod_policy":"Admins","value":{"anchor_peers":[{"host":$host,"port":$port}]},"version":"0"}' original-${org}.json > modified-${org}.json
 configtxlator proto_encode --input original-${org}.json --type common.Config --output original-${org}.pb
 configtxlator proto_encode --input modified-${org}.json --type common.Config --output modified-${org}.pb
 configtxlator compute_update --channel_id nyayachannel --original original-${org}.pb --updated modified-${org}.pb --output update-${org}.pb
 configtxlator proto_decode --input update-${org}.pb --type common.ConfigUpdate | jq '{payload:{header:{channel_header:{channel_id:"nyayachannel",type:2}},data:{config_update:.}}}' > envelope-${org}.json
 configtxlator proto_encode --input envelope-${org}.json --type common.Envelope --output envelope-${org}.pb
 peer channel update -f envelope-${org}.pb -c nyayachannel -o orderer.example.com:7050 --tls --cafile /orgs/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt
 sleep 2
done
