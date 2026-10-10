# Docker demonstration

From the NyayaVault project directory:

```sh
bash scripts/start-fabric.sh
bash scripts/docker.sh ps
bash scripts/docker.sh logs --tail=50 backend
```

This session uses `FRONTEND_PORT=3001` and `BACKEND_PORT=8001` in root `.env`, preserving the existing local SQLite demo on 3000/8000. Frontend: http://127.0.0.1:3001. API documentation: http://127.0.0.1:8001/docs. MinIO console: http://127.0.0.1:9001.

The helper finds Docker Desktop's bundled CLI on macOS if it is not already on PATH. Docker Desktop must be running. Fresh installations generate root `.env` once; an existing `.env` is preserved.

Docker stores cases and metadata in its PostgreSQL volume and encrypted evidence objects in its MinIO volume. These are separate from `backend/nyayavault.db` and `backend/data/`; existing local evidence is not migrated or overwritten. The Docker encryption key is in root `.env`; the local demo key is in `backend/.env`. Keep their backups distinct.

Login uses the same seeded demo accounts and `DemoOnly!2026` password. The first build downloads Python/Node/Go dependencies and compiles MinIO from a pinned official source revision because its previously configured registry image is unavailable. See `docker/minio/README.md` for provenance and licensing.

To stop while retaining data:

```sh
bash scripts/docker.sh stop
```

To resume existing containers:

```sh
bash scripts/docker.sh start
```

Do not use `down -v` unless you intend to destroy all Docker database and evidence volumes. Preserve root `.env` with the encrypted-storage backup; losing its key makes stored evidence unrecoverable.

## Integration verification

With the services running, use the same Python environment installed for the local project:

```sh
NYAYAVAULT_TEST_PROVIDER=fabric .venv/bin/python scripts/smoke-docker.py
```

This creates a clearly labeled synthetic investigation and evidence item, compares original/modified candidates, verifies encrypted retrieval and custody transfer, and writes actual results to `docs/docker-test-results.json`. It never replaces existing evidence. `NYAYAVAULT_TEST_API` can override the default `http://127.0.0.1:8001/api`.

Fabric is now connected on this host. Root `.env` selects both Compose files, so routine app updates preserve the Fabric configuration. Use `bash scripts/start-fabric.sh` after starting Docker Desktop to resume peers and the app without resetting data. See FABRIC.md. For a fresh source-only installation, provision Fabric first or use only the base Compose file for development mode.

## Executed status

The current deployment has eight main services and two Fabric-managed contract containers. The latest full review passed 80 automated tests/checks plus 10 browser observations; see FULL_PROJECT_REPORT.md. DOCKER_TEST_REPORT.md retains the initial four-service milestone. The Docker frontend build uses pnpm to import the npm lockfile, avoiding an npm installation stall encountered on this host.


## One Docker Desktop project

The eight main services now belong to the `nyayavault` Compose project: frontend, backend, PostgreSQL, MinIO, gateway, orderer, and two peers. Expand that project in Docker Desktop to see them together. Fabric creates and manages two additional `dev-peer...` contract containers automatically; they are intentionally outside Compose.

Root `.env` selects `docker-compose.yml`, `docker-compose.fabric.yml`, and `docker-compose.network.yml`. The network file references the existing external ledger volumes and preserves the current private identities. It is specific to this provisioned host; on a fresh machine, provision the network before adopting its volume names.

Use `bash scripts/start-fabric.sh` to start the stack, `bash scripts/docker.sh stop` to stop the main services, and `bash scripts/docker.sh ps` to list them. Fabric manages contract processes when peers restart. Images remain separate templates, not a runnable group: app images use the `nyayavault-` prefix and upstream images retain their official names. Keep Fabric-generated image names because peers resolve them by package ID.

Grouping verified: Fabric health returned connected, the app returned HTTP 200, and stored test proof history/transaction IDs matched the pre-migration report exactly. No data volume was deleted.
