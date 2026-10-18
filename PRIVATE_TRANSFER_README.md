# Restore this private NyayaVault package on Windows

This package contains application source and a consistent snapshot under `transfer/current`. It includes private keys, credentials, the database, encrypted evidence and original Fabric ledgers. Keep the ZIP private; it is not password-encrypted. Do not upload it to GitHub.

1. Install and start Docker Desktop with WSL 2 and Linux containers enabled.
2. Extract the entire ZIP to a local folder, such as `C:\NyayaVault-Transfer`.
3. Open PowerShell inside the extracted `nyayavault` folder (containing this file).
4. On a fresh destination, run Import before Start:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Import.ps1 -TransferPath 'transfer/current'
```

5. Wait for the import verification to finish, then open http://localhost:3001. Use the same user accounts and passwords as on the source computer. Gemini configuration is preserved by the included transfer script.

Import refuses to overwrite an existing deployment. Do not delete existing destination data to bypass that check. The import builds Linux images for the destination and preserves original transaction references rather than replaying evidence events. Internet access is required for image downloads and builds.

For later restarts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start.ps1 -NoDemo
```

For macOS/Linux, use `bash scripts/transfer.sh import transfer/current` for the first import.

The snapshot reflects the export time in `transfer/current/manifest.json`; later source changes are not included. Archive and snapshot integrity are checked at export. A successful Windows restore still needs to be confirmed on the destination device.
