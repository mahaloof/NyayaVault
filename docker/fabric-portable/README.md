# Fabric inside the portable Docker stack

This helper runs Linux Fabric 2.5.16 administrator binaries inside a Docker image. Windows requires Docker Desktop using Linux containers; host Python, Node, Bash, Fabric binaries and a Fabric Docker socket mount are unnecessary.

The standalone `docker-compose.portable.yml` uses an isolated Compose network, generated container names and project-prefixed named volumes. Its two organizations (`Org1MSP`, `Org2MSP`) share `nyayachannel`, with one peer each and one Raft orderer. Each peer connects to its own ordinary Compose chaincode service. Chaincode endorsement requires both peers: `AND('Org1MSP.peer','Org2MSP.peer')`.

The bootstrap service accepts two commands:

1. `init`, before starting peers/orderer: generate fresh local cryptogen identities if none exist, prepare the Org1 gateway identity and deterministic CCAAS package, and generate a fresh channel block if applicable.
2. `setup`, after starting orderer, both peers and chaincode services: join a fresh channel if needed, install the package, obtain both organization approvals, commit the definition once and verify each peer's definition, package, endorsement policy and chaincode health.

The project startup wrappers run these phases in order. Administrator commands remain inside the Linux tools container.

## Persistent data interface

| Compose volume | Container path | Contents |
| --- | --- | --- |
| `fabric_crypto` | `/runtime` | Original organization certificates/keys under `organizations/`, gateway identity and bootstrap artifacts |
| `fabric_orderer` | `/var/hyperledger/production/orderer` | Orderer ledger and Raft state |
| `fabric_peer_org1` | `/var/hyperledger/production` | Org1 blocks, state database, history database and lifecycle packages |
| `fabric_peer_org2` | `/var/hyperledger/production` | Org2 blocks, state database, history database and lifecycle packages |

`init` retains published identity trees and refuses incomplete identities. Fresh generation uses a staging directory, so interrupted generation cannot replace a working tree. The deterministic package and stored package ID are reused. An implementation fingerprint prevents silently accepting changed chaincode code on a later restart.

`setup` inspects actual orderer channels, both peer memberships and committed chaincode definitions rather than trusting a completion marker. It waits for the channel's Raft leader through the orderer's internal metrics endpoint before broadcasting lifecycle transactions. Recognized transient transport and event-wait failures receive bounded retries; identity, policy and unknown errors stop setup. A retry first checks whether the exact approval or definition already committed, preventing duplicate work after a response timeout. Successfully completed installation, approval and commit operations are skipped on a rerun. It never issues channel removal, volume deletion, ledger reset or evidence replay commands. Runtime records are written beneath `/runtime/artifacts`, including `setup-result.json`.

## Restoring the existing demonstration

The transfer process restores original identities and all three ledger volumes into the portable stack. It writes `/runtime/artifacts/imported-ledger.json` containing at least:

```json
{"channel":"nyayachannel"}
```

With this marker, `init` forbids new identity generation and channel genesis creation. `setup` requires the original channel to be present on the orderer and both peers. Missing restored state stops startup instead of being replaced with a fresh chain.

The existing definition `nyayavault` version `1.0` is upgraded on the restored copy to version `1.0-portable`, at the next sequence, using the same contract implementation. This changes how peers reach the chaincode service and requires both organizations' endorsements. It adds normal lifecycle transactions to the restored ledger. It preserves original evidence proofs, original event transactions, block history and transaction identifiers; no evidence is replayed. The original deployment and transfer backup remain available for recovery.

A later restart detects the committed portable definition and verifies it without incrementing its sequence. Any unexpected chaincode version, package, policy or peer disagreement stops automatic setup. Diagnose incomplete restoration or a peer still catching up before rerunning.

Fresh demonstrations use version `1.0-portable` sequence 1. Cryptogen and unencrypted internal CCAAS traffic are local demonstration choices. Fabric peer/orderer and gateway connections use TLS; the application keeps user roles and case permissions in its backend.

Implementation follows the official [channel participation commands](https://hyperledger-fabric.readthedocs.io/en/release-2.5/commands/osnadminchannel.html), [chaincode lifecycle](https://hyperledger-fabric.readthedocs.io/en/release-2.5/commands/peerlifecycle.html), and [external chaincode service](https://hyperledger-fabric.readthedocs.io/en/release-2.5/cc_basic.html) documentation.
