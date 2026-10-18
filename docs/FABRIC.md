# Hyperledger Fabric integration

## Executed deployment — 2026-10-06

The local Docker deployment is connected to Hyperledger Fabric 2.5.16. Two peers (Org1MSP, Org2MSP) and a Raft orderer run on `fabric_test`; both organizations approved `nyayavault` version 1.0, sequence 1 on `nyayachannel`. The gateway checks commit validation before returning transaction IDs. Eight prior PostgreSQL custody events were backfilled; six new workflow events were committed and independently queried. See [executed test report](FABRIC_TEST_REPORT.md).

This uses the official sample network with cryptogen-generated development identities, LevelDB state and default endorsement policy. It is a local academic network, not a production deployment. The older SQLite demonstration was retired during cleanup; its data and keys are retained inside the private recovery ZIP.

## Resume safely

Start Docker Desktop, then from the project directory:

```sh
bash scripts/start-fabric.sh
```

Open http://127.0.0.1:3001/settings. The status must say `Hyperledger Fabric connected`. Root `.env` sets `COMPOSE_FILE=docker-compose.yml:docker-compose.fabric.yml:docker-compose.network.yml` and holds the gateway shared secret. The gateway override routes backend requests internally; the network override groups the existing peers and orderer into the same project using their external ledger volumes. No gateway port is published; sample peer/orderer ports bind only to loopback.

To stop without deleting data:

```sh
bash scripts/docker.sh stop
# With Docker CLI on PATH:
docker stop peer0.org1.example.com peer0.org2.example.com orderer.example.com
```

Preserve `blockchain/runtime/`, root `.env`, and Docker volumes. Runtime contains private identities and is ignored by Git and excluded from the source ZIP. Do not run the sample `network.sh down` or `docker compose down -v`: those reset ledger/database volumes. The source ZIP intentionally does not contain the running network or its private keys.

Cleanup removed downloaded host binaries and unrelated Fabric examples. The live identity directories and peer configuration remain in place. Docker startup does not need host binaries; reinstall the pinned Fabric tools before using the historical manual provisioning instructions below.

## Provision a fresh machine

For the portable Windows, macOS or Linux deployment, use [WINDOWS_START_HERE.md](../WINDOWS_START_HERE.md) and `docker-compose.portable.yml`. The bootstrap tools run inside Docker and build for the destination CPU. The source-only path creates a new network; the exact-transfer path restores existing ledger/identity archives and explicitly upgrades only the copied network's chaincode runtime without replaying evidence. The manual steps below describe the original sample-network deployment retained on this Mac.

Follow the official [Fabric installation](https://hyperledger-fabric.readthedocs.io/en/latest/install.html) and [test-network guide](https://hyperledger-fabric.readthedocs.io/en/latest/test_network.html). This host used Fabric 2.5.16, CA tool version 1.5.17 and fabric-samples revision `5789681b4f4d24e58fa40f19a69f5496892374b6`. CA services are not needed for this cryptogen configuration.

Install the samples and binaries under `blockchain/runtime/fabric-samples`. Set the parent runtime directory permissions to 0700. Before startup, change published port mappings in `test-network/compose/compose-test-net.yaml` to `127.0.0.1:HOST:CONTAINER`.

From `fabric-samples/test-network`:

```sh
./network.sh up createChannel -c nyayachannel
./network.sh deployCC -ccn nyayavault -ccp /absolute/path/to/nyayavault/blockchain/chaincode -ccl javascript -c nyayachannel
```

Copy these generated Org1 files to `blockchain/runtime/gateway-identity/`:

| Destination | Source under test-network/organizations/peerOrganizations/org1.example.com |
|---|---|
| tls.crt | peers/peer0.org1.example.com/tls/ca.crt |
| cert.pem | users/User1@org1.example.com/msp/signcerts/cert.pem |
| key.pem | users/User1@org1.example.com/msp/keystore/generated-private-key-file |

The gateway runs as container user `node`. The mounted identity directory is 0755 and files 0444 so it can read them; their host parent `runtime` is 0700. Mount is read-only. Generate a random `FABRIC_GATEWAY_SECRET` in root `.env`, then build/start both Compose files:

```sh
bash scripts/docker.sh -f docker-compose.yml -f docker-compose.fabric.yml up -d --build
```

## Reconcile prior or failed events

```sh
bash scripts/docker.sh exec -T backend python -m app.retry_blockchain
```

Replay follows each evidence stream in order and stops that stream on failure. Event IDs are idempotent on-chain; replay returns the transaction ID of the original write. A timeout may happen after commit, so retry through this command. A database commit precedes network submission; no background durable retry worker is implemented yet. Inspect FAILED/PENDING events and gateway logs.

## Verify

With project Python dependencies installed:

```sh
NYAYAVAULT_TEST_PROVIDER=fabric .venv/bin/python scripts/smoke-docker.py
.venv/bin/python scripts/check-fabric-history.py
```

The first script creates synthetic records. The second compares real peer history with those records, checks idempotent replay, verifies rejection of a changed original hash, and checks gateway authentication. Reports are written under `docs/`.

## Trust boundary

Only metadata/proofs are sent to Fabric; encrypted file bytes remain in MinIO. The service signs using Org1 User1 and records the application actor separately. Login users do not each have a Fabric certificate. FastAPI enforces roles/case membership; chaincode permits Org1MSP/Org2MSP. Production needs organization-specific identities, authorization/endorsement design, managed keys, TLS between app services, durable retries and operational review. Cryptogen sample keys and demo credentials are unsuitable for production.

## Missing endorsement peers after restart

If the gateway can answer health queries but uploads fail with `no combination of peers can be derived which satisfy the endorsement policy`, inspect peer logs. A confirmed cause in the local legacy network was missing `AnchorPeers` entries for both organizations following the earlier reset. The health endpoint only evaluates a query; it does not establish that a write can obtain both endorsements.

For that specific missing-anchor condition, start the existing network and run:

```sh
bash scripts/start-fabric.sh
bash scripts/repair-fabric-discovery.sh
```

The repair builds the existing Fabric 2.5.16 administration image, fetches current channel configuration and adds missing Org1/Org2 anchor-peer entries through signed channel updates. Existing anchor settings are left untouched. It does not reset peers, replace keys, change endorsement policy or replay evidence transactions. Before/after configuration files remain under the Git-ignored `blockchain/runtime/anchor-repair/` directory. Requires Docker and network access for the first build. This wrapper targets the existing legacy local network, not the separate portable deployment.

This repair was applied on 18 October 2026. Twelve subsequent evidence uploads, twelve integrity checks and four transfers produced 28 committed transactions; decrypted originals and peer histories were checked. The initial failed upload was retried as the same previously uncommitted event with a `FABRIC_SUBMISSION_RETRY` audit entry. A failed event is not automatically repaired merely by adding anchors, and its status must never be changed to COMMITTED without a real successful Fabric commit.

Rerunning the repair when both anchor entries exist performs only configuration reads, with no additional channel updates. For other endorsement errors, investigate peer availability, chaincode readiness and policy rather than weakening the two-organization policy.
