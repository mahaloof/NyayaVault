# Run NyayaVault

NyayaVault runs in Docker: web app, API, database, encrypted storage and a two-organization Hyperledger Fabric network. Start with an empty workspace using the instructions below.

## 1. Prepare Windows

- Install Docker Desktop for Windows from https://docs.docker.com/desktop/setup/install/windows-install/ and enable its WSL 2 / Linux containers engine.
- Start Docker Desktop and wait until it is ready. Internet access is required for the first build. A supported 64-bit machine with virtualization enabled is required; 16 GB RAM is recommended for this project.
- Download this repository using GitHub **Code → Download ZIP**, then extract it to a local folder such as `C:\NyayaVault`. Or, if Git is installed and you have access to this private repository:

```powershell
git clone https://github.com/mahaloof/NyayaVault.git
cd NyayaVault
```

Open PowerShell in the folder containing `docker-compose.portable.yml` and `scripts`. For a ZIP download this may be named `NyayaVault-main`.

## 2. Start an empty project

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start.ps1 -NoDemo
```

The first run builds the images, generates local secrets, initializes Fabric and creates demo login accounts. It can take several minutes. Keep Docker running and wait for the ready message. `-NoDemo` prevents sample cases and evidence from being added. Use this option on later starts as well.

Open **http://127.0.0.1:3001**.

| Account | Email | Initial demo password |
| --- | --- | --- |
| Administrator | admin@nyayavault.local | DemoOnly!2026 |
| Investigator A | investigatorA@nyayavault.local | DemoOnly!2026 |
| Investigator B | investigatorB@nyayavault.local | DemoOnly!2026 |
| Forensic officer | forensic@nyayavault.local | DemoOnly!2026 |
| Legal viewer | legal@nyayavault.local | DemoOnly!2026 |

These are local demonstration accounts. Keep this deployment private. Create a case, assign its members and upload evidence through the app. Investigator access depends on case membership; viewers cannot download originals or use the assistant.

To deliberately populate fictional example cases, run Start.ps1 without `-NoDemo`.

## 3. Enable the optional Gemini case assistant

Core evidence features work without an AI key. After the first successful start, open the generated **`.env.portable`** in a text editor. Preserve its existing keys and passwords. Add or update:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_KEY
AI_MODEL=gemini-3.5-flash-lite
```

Use a model available to your Google project; quotas and billing are controlled by Google. Save the file, then run the same Start command with `-NoDemo` again. Never put the real key in GitHub or a frontend setting.

The assistant supports TXT, selectable or scanned PDFs, and PNG/JPEG document photos. OCR runs locally and reads printed English; handwriting and other languages are unreliable. Limits: four files, 10 MiB per file, first 20 PDF pages and bounded text excerpts. Answers include source quotations and page numbers. For mixed text/image PDF pages, select **Scan every PDF page**.

The assistant also reads case details and recorded custody history without uploaded files. Explicit authorization and consent are required before sending case information and selected text to Google. See [AI setup and limitations](docs/AI_ASSISTANT.md).

## 4. Stop, restart and check status

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Stop.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start.ps1 -NoDemo
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Status.ps1
```

Stop keeps your Docker data. Do not delete volumes or use `docker compose down -v` unless you intentionally want to lose that deployment's data. Preserve `.env.portable`: its encryption key is required to read your evidence.

## GitHub code versus a private data backup

Cloning GitHub gives you the application code and optional fictional sample files. It does **not** copy another computer's accounts, case records (including the Jisha study), uploaded evidence, blockchain history, API key or private recovery backup. Each fresh installation creates its own database, identities, secrets and blockchain. Setup blocks are normal even with zero evidence.

To move existing records exactly, export a fresh private snapshot from the source computer and import it on an empty destination before running Start. See [Windows transfer instructions](WINDOWS_START_HERE.md). Old recovery snapshots restore the data as it existed when they were created, not newer cases.

## macOS / Linux / WSL

For a new portable installation with Docker running:

```bash
bash scripts/portable.sh start --no-demo
bash scripts/portable.sh status
bash scripts/portable.sh stop
```

For the original already-provisioned Mac network, resume it with `bash scripts/start-fabric.sh`. Do not start a second portable deployment on the same ports while the original one is running.

## Troubleshooting

- **Docker cannot connect:** open Docker Desktop and confirm Linux containers are running.
- **Port already used:** on a fresh installation, add `-FrontendPort 3002 -BackendPort 8002 -MinioConsolePort 9002` to Start.ps1, then open port 3002. Existing configuration is preserved; see the Windows guide before changing existing ports.
- **First build fails:** check the internet connection and Docker resources, then rerun Start with `-NoDemo`. Cached downloads are reused.
- **Fabric not connected:** inspect Status.ps1 and service logs; do not delete volumes as a troubleshooting shortcut.
- **AI unavailable:** confirm the key/model in `.env.portable`, rerun Start, and check Google's quota. Uploads and custody features still work without AI.

The portable architecture was tested with Linux containers on Docker Desktop for macOS. The AI/OCR tests and live Gemini checks passed there. Native Windows execution still needs validation on the destination machine. `scripts\windows\Test.ps1` exercises uploads and real Fabric commits, but creates and archives a test case; skip it if you want the workspace to stay empty.
