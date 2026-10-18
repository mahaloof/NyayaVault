# Current NyayaVault project

> **Backup status — 17 October 2026:** The old `NyayaVault-Windows-Exact.zip` and pre-reset recovery folder have been deleted at the user’s request. References below to that package and its record counts are historical. For a fresh installation, follow [RUN_PROJECT.md](../RUN_PROJECT.md). To move current data, export a new private snapshot first.

Open **http://127.0.0.1:3001**. There is one running NyayaVault deployment, with two Fabric organizations sharing the same blockchain.

From the `nyayavault` folder, resume it after starting Docker Desktop:

```sh
bash scripts/start-fabric.sh
```

To stop the application while retaining its data:

```sh
bash scripts/docker.sh stop
```

The deployment needs ten containers: frontend, backend, database, encrypted file storage, gateway, two peers, one orderer and two Fabric-managed contract containers. Fabric names its contract containers `dev-peer...`; they are required parts of this application.

Cleanup on 8 October 2026 removed the stopped portable test deployment, its 18 unused volumes, unused portable images, build cache, downloaded host dependencies, unrelated Fabric samples, temporary work files and duplicate source ZIPs. Application source, tests, reports, Docker configuration and Windows transfer scripts remain useful project files.

The single private recovery/Windows transfer archive is `../NyayaVault-Windows-Exact.zip`. It preserves the original database, encrypted originals, Fabric ledgers and keys. It also contains the retired local SQLite data and older recovery material under `cleanup-recovery/`. Keep the archive private. The current app uses PostgreSQL and MinIO; it does not use those retired files.

Before and after cleanup, all **19 preservation checks passed**: 5 users, 9 cases, 17 encrypted originals and 70 original custody/Fabric events. Four cases and twelve exhibits are active; older test history remains archived. See [preservation results](cleanup-after-preservation.json) and [cleanup inventory](cleanup-20261008.json).

The root `.env`, live identity/configuration paths under `blockchain/runtime`, and nine active Docker data volumes must be retained. Generated dependencies and build cache can be recreated by Docker. To transfer to Windows, extract the private ZIP and follow [the Windows guide](../WINDOWS_START_HERE.md).
