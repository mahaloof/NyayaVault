# Run NyayaVault on Windows

**Start here for a new GitHub download:** [RUN_PROJECT.md](RUN_PROJECT.md) has the empty-workspace startup command, login accounts and AI/OCR setup. The snapshot counts below describe the historical October 8 transfer package, not the current running database. Private ZIPs and transfer snapshots are not included in GitHub.

Use Docker Desktop with **Linux containers**. This project keeps the same Next.js application, FastAPI backend, PostgreSQL database, encrypted MinIO storage and two-organization Hyperledger Fabric blockchain. No Python, Node.js, Git or Fabric binaries need to be installed on Windows.

**Downloaded from GitHub?** The repository contains source and fictional demo files, not private backups. For a new demonstration, open PowerShell in the project folder and run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start.ps1 -NoDemo`, then open http://127.0.0.1:3001. The import instructions below apply only when you also have the private transfer package.

## Keep the current data — recommended for this transfer

1. Install/start [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) and enable its WSL 2 Linux engine. Use a supported 64-bit Windows system with virtualization enabled. Docker's current minimum is 8 GB RAM; 16 GB is recommended for this multi-service demonstration. Internet is required for the first image downloads/builds.
2. Copy **NyayaVault-Windows-Exact.zip** to the Windows computer. This is a private package: it contains the existing database, encrypted evidence, encryption keys and Fabric identities. Keep it on storage you control.
3. Extract the complete ZIP to a local NTFS drive, for example `C:\NyayaVault`. Avoid network shares, cloud-synced folders and removable exFAT drives. Open the extracted `nyayavault` folder; it contains this guide, `docker-compose.portable.yml`, `scripts`, and `transfer\current`.
4. Open PowerShell in that folder and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Import.ps1
```

The import verifies snapshot checksums, refuses to overwrite existing populated Docker data, restores the original keys/database/ciphertext/ledgers, builds Linux images for the destination computer, starts the app, and compares the restored original records and transaction references with the source snapshot.

5. Open **http://127.0.0.1:3001**. Existing demo logins and passwords remain: `admin@nyayavault.local` / `DemoOnly!2026`. The ordinary workspace has the four fictional investigations and twelve exhibits; the five old test cases remain accessible through the archive toggle.

Do not run Start before Import on a new computer: Start creates a separate fresh network. If the target project already contains data, Import refuses to replace it. A failed partial restore must be diagnosed before reusing those volumes; the snapshot and source computer remain untouched.

## Subsequent starts and stops

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Status.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Stop.ps1
```

Start reuses the existing identities, encryption key and ledger. Stop leaves all data volumes intact. Do not use `docker compose down -v` or delete NyayaVault's Docker volumes. Keep `.env.portable` with your backups. Once an imported project has data, the demo helper skips reseeding it; user changes are preserved.

To validate the running copy, run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Test.ps1`. It creates one clearly labelled temporary test case, checks the real evidence workflow and permissions, then archives that case after successful checks. Existing investigations stay unchanged. Results are saved in `docs\portability-workflow-results.json`.

## Start a new independent demo instead

On an unused computer, extract **NyayaVault-Windows-Exact.zip** and run Start.ps1 directly instead of Import.ps1. Start ignores the saved transfer snapshot and creates new secrets, a new blockchain and the same four fictional scenarios through real uploads and Fabric commits. This option does **not** recreate this computer's original transactions. Import is the recommended option when keeping the existing data.

If ports are occupied on a fresh installation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start.ps1 -FrontendPort 3002 -BackendPort 8002 -MinioConsolePort 9002
```

Port options apply when creating `.env.portable`. Existing configuration is retained; changing an existing frontend/API port requires editing the port entries in that file and rerunning Start to rebuild the frontend. Preserve all secret/key entries.

## Moving an updated portable deployment later

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Export.ps1
```

Export briefly pauses the source application, makes a consistent copy, and restarts it. It prints the new folder under `transfer`. Copy that folder together with the current project source, then use Import.ps1 on an unused target, passing the folder if its name is not `transfer\current`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Import.ps1 -TransferPath 'transfer\export-YYYYMMDD-HHMMSS'
```

On macOS, Linux or WSL, the equivalents are `bash scripts/portable.sh start|stop|status` and `bash scripts/transfer.sh export|import transfer/folder`. The original Mac deployment can be exported using `bash scripts/transfer.sh export-legacy transfer/new-snapshot`.

## What happens to the blockchain

The exact package carries the original orderer and both peer ledgers and signing identities. Restoring never generates new identities for that ledger, resets a channel, backdates events or replays evidence as new original transactions.

The old network ran peer-managed chaincode containers. The portable copy runs the identical contract as two chaincode services, one for each organization, without giving the peers access to Docker's control socket. On the **restored copy only**, startup performs an explicit Fabric lifecycle upgrade from version `1.0` / sequence 1 to `1.0-portable` / sequence 2 with both organizations' endorsements. The original evidence history remains under the same `nyayavault` contract name and keeps its transaction IDs. Lifecycle approvals/commit are new administrative blockchain transactions, not evidence transactions. The original Mac network is not upgraded.

The Docker-control socket is used only by the explicitly run export/import/verification helper to copy and inspect local Docker data. It is not mounted into ordinary application, peer or chaincode services.

## Troubleshooting and test limits

- Docker unavailable: start Docker Desktop and wait for its Linux engine; reopen PowerShell if `docker` is not found.
- Script blocked: use the exact `powershell -NoProfile -ExecutionPolicy Bypass -File ...` invocation above. It changes the execution policy only for that process.
- Long first build: Fabric binaries, Node/Python packages and the pinned MinIO Go source are downloaded and built inside Docker. Keep internet access available; retries reuse cached images.
- Fabric failure: view `docker compose --env-file .env.portable -f docker-compose.portable.yml logs fabric-bootstrap peer-org1 peer-org2 orderer fabric-gateway`. Do not delete data to fix it. Start is safe to rerun after correcting a temporary failure.
- Different PC/CPU: Docker builds destination-native Linux images; macOS binaries and host dependency folders are not shipped. amd64 and arm64 bootstrap binaries are supported. This is not a claim that Docker works on unsupported Windows versions or 32-bit hardware.

The delivered configuration is tested through Docker Desktop on this Mac, including an isolated restored copy and real Fabric operations. Native Windows execution remains to be checked on the destination computer. See [portability test report](docs/PORTABILITY_REPORT.md) for the actual checks, preserved data and remaining limits.
