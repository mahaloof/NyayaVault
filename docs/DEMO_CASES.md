# Realistic fictional demo cases

The active demonstration contains four fictional scenarios, each with three UTF-8 text records. They contain invented organizations, incidents, observations and findings. These are training documents, and the camera record is a transcript rather than a video. No personal records, genuine crime evidence or executable malware is included.

| Case | Scenario | Evidence and workflow |
| --- | --- | --- |
| NV-2026-0142 | Supplier invoice diversion at Aster Office Supplies | Email headers, payment authorization and mailbox findings; two records pass to the forensic officer. |
| NV-2026-0217 | Night-time collision at Riverside Junction | Camera observations, witness interview and scene notes; a deliberately altered camera timestamp demonstrates an integrity alert. The witness note remains unverified. |
| NV-2026-0308 | Missing stock at Meridian Logistics | Loading-bay access, stock reconciliation and examination note; a closed case with retained evidence. |
| NV-2026-0419 | Ransomware incident at Community Skills Centre | Incident response log, endpoint timeline and triage note; an open incident with two forensic handoffs. |

All five existing demo users are assigned to every scenario. Their existing roles still control upload, transfer, download, account administration and read access. The two Fabric organizations continue to share the same channel.

The importer sends unchanged sample bytes through NyayaVault's upload API. The backend generates the original SHA-256 fingerprint, stores the AES-256-GCM ciphertext and commits each custody event through Fabric. Eleven originals are verified from decrypted stored bytes. Seven records are transferred to the forensic officer. One camera candidate changes `22:18:04` to `22:19:04`, which produces a real failed comparison while preserving the original. The resulting evidence states are ten verified, one integrity alert and one unverified.

Collection dates describe the fictional scenario. Upload, verification, transfer and Fabric transaction timestamps are actual execution times; the script never backdates them or invents transaction IDs.

## Refreshing an existing local demonstration

Before running, take the database and encrypted-object backup documented for this deployment. Keep the encryption keys and Fabric volumes. With the current application and Fabric services healthy, run from the project directory:

```sh
../../work/venv/bin/python scripts/populate-demo.py
```

The API defaults to `http://127.0.0.1:8001/api`; use `--api` or `NYAYAVAULT_DEMO_API` for another endpoint. `NYAYAVAULT_DEMO_PASSWORD` can override the existing demo-account password.

The script can be run again after an interruption. It reuses matching case numbers and evidence labels, checks their original hashes and case bindings, and skips workflow events already completed. An unexpected active record, mismatched reused label or custody event without a committed Fabric transaction stops the import. If Fabric failed after an application event was saved, restore the connection and use the documented blockchain retry process before rerunning.

Only case numbers and evidence labels explicitly listed in `sample-data/demo-cases/manifest.json` are eligible for retirement. Retirement sets the case status to `ARCHIVED`, removing its evidence from the ordinary case, evidence, dashboard and audit lists. It preserves the original files, encryption, case assignments, immutable custody history and original Fabric transaction references. Archived data remains retrievable with the existing case permissions and `include_archived=true`. The Fabric ledger is not erased.

No old case is archived until all twelve demo originals and their requested workflow events pass the commit checks. Before making changes, the importer saves a private JSON baseline beneath ignored `blockchain/runtime/demo-refresh-backups/`. This snapshot includes original case assignments, evidence metadata, custody events and transaction references; it is supplementary to the full database, ciphertext and key backup. It compares retired histories and memberships after archiving.

The execution result, actual dashboard totals and checks are written to `docs/demo-refresh-results.json`. Preserve private backups outside source archives.
