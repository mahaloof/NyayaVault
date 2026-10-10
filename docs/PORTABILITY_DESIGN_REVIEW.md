# Exact-data portability design review

Reviewed 8 October 2026 (India time). This is a read-only design review of the source, current Compose files, existing chaincode archive and saved validation reports. It does not claim that a Windows restore has been performed. No live Docker containers, volumes, keys or application data were modified for this review.

## What must travel together

The source ZIP alone cannot reproduce the current deployment: it deliberately excludes databases, encrypted originals, Fabric ledgers and private keys. An exact transfer needs a separate private data bundle plus the application source and target-compatible container images. Restoring that bundle must preserve the same channel, chaincode namespace, evidence IDs, custody event IDs and original transaction references.

The saved `demo-preservation-results.json` reports five users, nine cases (four active and five archived), 70 custody events, chaincode version `1.0` / sequence `1`, both organization approvals, and the shared channel's majority endorsement policy. These are saved report values, not a replacement for recording the actual counts and block heights at export time.

| Component | Required data | Restore approach |
|---|---|---|
| Backend configuration | Root `.env`, especially `EVIDENCE_MASTER_KEY`, `JWT_SECRET`, MinIO credentials, gateway secret and existing ports | Keep the encryption and signing secrets unchanged; adapt only deployment selection/ports explicitly |
| PostgreSQL | Users/password hashes, cases, memberships, all evidence metadata, custody/audit/verification records, original hashes, submission records and migrations | Logical dump and restore into PostgreSQL 17 |
| MinIO | Complete stopped `/data` volume, including internal `.minio.sys` metadata and all encrypted objects | Archive and restore into a Linux named volume with the same MinIO server version |
| Both Fabric peers | Full ledger, state/history/index databases, private organization approval data, installed chaincode packages and build metadata | Archive every mounted volume after clean peer shutdown |
| Orderer | Complete ledger plus Raft/channel-participation state and relevant configuration | Archive every mounted volume after clean orderer shutdown |
| Fabric identities | Organization MSPs, TLS directories, existing admin/user identities, gateway signing identity and certificates | Preserve directory contents and names; do not regenerate certificates |
| Contract and configuration | Original installed chaincode archive, `core.yaml`, channel artifacts and exact environment configuration | Include source and configuration in the transfer bundle |

Fabric's official recovery guidance describes backing up the ledger and MSP after stopping the node; the default peer directory contains chaincode data as well as ledger data. Preserve the full data here rather than omit reconstructible databases. [Fabric component backup and restore](https://hyperledger-fabric.readthedocs.io/en/release-2.5/upgrading_your_components.html).

## Actual Fabric mount layout to preserve

The checked-in `docker-compose.network.yml` maps seven existing volumes, including four anonymous volumes. Export must inspect the running containers and confirm this map rather than guess names. Anonymous parent mounts can contain data that is absent from the obvious named production volume.

| Service | Container path | Current source volume in configuration |
|---|---|---|
| Orderer | `/var/hyperledger` | `1091e7fbf472d0aa20706d59bc4cb13674d8e1e7995e6338f2b53d578d646fe2` |
| Orderer | `/etc/hyperledger/fabric` | `5891e1aa6980b15c09ca99c519683a5823bc69cb01d0057940eb0f1cf6674e82` |
| Orderer | `/var/hyperledger/production/orderer` | `compose_orderer.example.com` |
| Org1 peer | `/var/hyperledger` | `e0ee2836061ab1528e964fc06ee647d04aaa862293d52ebaac5f5805e200b2e2` |
| Org1 peer | `/var/hyperledger/production` | `compose_peer0.org1.example.com` |
| Org2 peer | `/var/hyperledger` | `406f2aa4d77a9e277a0428dba19705dda5a5ed8e196bdcc7a649b57b46eaea73` |
| Org2 peer | `/var/hyperledger/production` | `compose_peer0.org2.example.com` |

Peer certificates/MSPs are additionally mounted from `blockchain/runtime/fabric-samples/test-network/organizations/peerOrganizations/`. The orderer mounts its existing MSP and TLS directories from the corresponding `ordererOrganizations/` tree. Both peers use `test-network/compose/docker/peercfg/core.yaml`. The gateway mounts `blockchain/runtime/gateway-identity/`.

Nested mounts matter: restoring the parent archive does not restore the separate volume mounted over its production subdirectory. Restore each archive into its own new named volume and recreate the same target paths. Export MinIO and PostgreSQL from the actual mounts of their running service containers; the base Compose declarations use `minio_data` and `postgres_data` under the `nyayavault` project.

Docker documents helper-container volume backup/restore. Use that approach so numeric ownership, permissions, symlinks and Linux filenames remain in the archive and the restored Linux volume. Do not unpack Fabric ledger data into a Windows host directory and then use NTFS as the ledger mount. [Docker volume backup and restore](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes).

## Consistent export sequence

1. Capture a read-only baseline of all original metadata, custody records, transaction IDs, encrypted-object hashes, installed/approved/committed chaincode definitions, channel membership and peer/orderer block heights. Check that application submissions are committed before the export boundary.
2. Stop the frontend, backend and gateway cleanly so no new application operations can enter. Stop both peers, the orderer and MinIO cleanly before copying their file volumes. Keep the source containers and volumes intact.
3. Take a PostgreSQL custom-format logical dump while PostgreSQL is running and application writers are stopped. Include the schema, append-only guards, constraints and all data; capture required ownership/roles or restore under the existing `vault` role. A logical dump supports transfer between machines more cleanly than copying an architecture-specific PostgreSQL data directory. [PostgreSQL SQL dump guidance](https://www.postgresql.org/docs/17/backup-dump.html).
4. Copy every identified MinIO/Fabric volume through a temporary Linux helper with source mounts read-only. Copy identities, gateway certificates/key, peer configuration, original package, relevant channel artifacts and the original root `.env` into the private bundle. No private key or secret should be printed into a public report.
5. Write a manifest recording source versions, architecture, source mount-to-archive mapping, hashes of every archive, export counts and expected channel/package IDs. Restart the original services in a `finally`/recovery path. A failed export must never leave a purported complete bundle.
6. Retain the source system and the complete export until a separate restore passes preservation checks. Avoid source cleanup, pruning, channel reset or event replay as part of transfer.

The export directory contains decryption keys and Fabric administrator credentials. It must be treated as a private recovery artifact, separate from the source distribution.

## Standalone Windows restore deployment

Use Docker Desktop's Linux-container backend; Fabric and the current application images are Linux workloads. The Docker Desktop Windows requirements and WSL 2 setup are described in [Docker's Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).

The portable Compose file should be complete and independent of the Mac-specific override files:

- Use a separate project name and new named volumes. Refuse to overwrite nonempty volumes unless a deliberate recovery procedure explicitly requests it. Avoid fixed container names, which would collide during a side-by-side restore rehearsal.
- Preserve service DNS aliases `peer0.org1.example.com`, `peer0.org2.example.com` and `orderer.example.com` inside its own network. Existing TLS certificates, gossip endpoints and channel configuration refer to these names.
- Restore into Linux named volumes before starting the application. Use relative identity/configuration paths or an identity/configuration named volume. Preserve readable permissions for the gateway's `node` user and preserve private parent directory protection where supported.
- Pass `--env-file` and `-f` explicitly. The source `.env` selects three Mac Compose files using a colon-delimited `COMPOSE_FILE`; relying on that value in Windows or in the portable clone can select the wrong deployment. Keep the AES key and gateway secret exactly the same.
- Use matching internal gateway routing and Fabric TLS name override. Keep application, MinIO console and node ports on loopback for the local demonstration. Build the frontend with its target API URL; that URL is compiled into the frontend image.
- Restore PostgreSQL before backend startup. Avoid running fresh-demo seed/import commands on a restoration path. Start existing infrastructure and query it before permitting new evidence actions.
- Run all Fabric CLI tools inside target-compatible Linux containers. Existing `fabric-samples/bin` binaries are for the Mac host and must not be used on Windows.
- If traditional Node chaincode is retained, its peer Docker socket and `CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE` must refer to the portable Docker engine/network. The original `fabric_test` network must not be shared with an active source/clone network.

Images exported from the Mac may be ARM64; a Windows x64 Docker Desktop machine generally needs Linux AMD64 images. Rebuild application/MinIO/gateway images from the retained Dockerfiles and lockfiles for the target architecture, or bundle independently built target images. Loading an ARM64 image archive is not sufficient evidence of native Windows x64 support. Retain Fabric `2.5.16`, PostgreSQL 17 and the MinIO source commit used here for the first restore. A Linux AMD64 rehearsal under Mac emulation is useful but is not a completed Windows-host test.

## Original chaincode versus CCAAS

The existing package is `blockchain/runtime/fabric-samples/test-network/nyayavault.tar.gz`. Read-only inspection found metadata type `node`, label `nyayavault_1.0`, and archive SHA-256 `2b0568ad43674b54cc59a2dc768dcd2c50d25c103c60c760e4245b3062c29eb4`. Its code archive contains `index.js`, `package.json`, `package-lock.json` and `test.js`; there are no vendored `node_modules` or native binaries. The metadata's source path is a Mac absolute path, but the code is packaged in the archive; verify the installed package ID against both peers rather than repackaging merely to change that path.

The least intrusive first restore keeps version `1.0`, sequence `1`, the original package ID and the same chaincode name, allowing the traditional Docker launcher to rebuild the image on the target architecture. The checked-in peer configuration uses `hyperledger/fabric-nodeenv:2.5` and an external CCAAS builder. A target-specific traditional image build must be tested; do not assume an exported peer-created ARM image will launch on x64.

CCAAS is a practical portable alternative: the application operator builds the contract image, starts one internal contract service per peer, and installs a package containing its connection information. Peer configuration already includes `/opt/hyperledger/ccaas_builder`. Connection-address templates can map a common package to separate peer services. The contract services must present the actual installed package ID and run the existing contract logic; they do not require published host ports. [Fabric CCAAS configuration](https://hyperledger-fabric.readthedocs.io/en/release-2.5/cc_basic.html).

Changing from the original Node package to a CCAAS package changes package identity. Do this only on the restored copy, retaining the old package and its ledger. Record any organization reapproval or chaincode definition upgrade as new administration transactions. If an upgraded definition is used, agree the new version/sequence through both organizations while keeping the same chaincode name and endorsement policy. Existing namespace state survives a compatible upgrade; the committed definition and organization package associations are distinct lifecycle concepts. [Fabric chaincode lifecycle](https://hyperledger-fabric.readthedocs.io/en/release-2.5/chaincode_lifecycle.html).

These additional administration transactions do not replace the original evidence commits. The restore must query original history and retain original `txId` values; reuploading files or replaying custody events into a new channel is not an exact transfer. Preserve the restored pre-upgrade snapshot so recovery remains possible if a CCAAS conversion fails.

## Acceptance checks before calling the transfer complete

Verify these independently on the isolated restored deployment, then report which host/architecture was actually tested:

1. Users, password hashes, memberships, every case (including archives), complete evidence metadata, custody/audit/verification records, encryption-key identity and original submission records match the export baseline.
2. Every MinIO object has the same ciphertext digest, decrypts under the original AES key and evidence UUID, and matches the original SHA-256 and byte length.
3. Every application custody chain is valid. Fresh Fabric queries match every original event ID, actor/action, original hash, linked hashes and original committed transaction ID, for active and archived evidence.
4. Both peers retain the channel and compatible block history; both organizations approve the intended deployed contract; channel membership and majority endorsement remain correct. Any added restore administration transactions are reported separately.
5. Login, assigned/unassigned case access and allowed/denied role operations work. New upload, original verification, custody transfer and modified-candidate detection produce genuinely new commits on the restored shared ledger. Use a clearly identified new restore-validation case and archive it after the checks.
6. Stopping/restarting the restored Compose group preserves data. No source volume, original identity or source transaction was reset or overwritten during the rehearsal.

At review time, the migration implementation, target image set, full exported bundle and actual Windows restore remained work to complete. This document is design evidence, not a passed backup/restore report.
