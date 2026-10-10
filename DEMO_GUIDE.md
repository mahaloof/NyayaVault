> Current Docker demonstration and executed results: [full report](docs/FULL_PROJECT_REPORT.md). Local SQLite mode is separate.

# NyayaVault live demonstration

## Preparation

1. Start Docker Desktop, then run `bash scripts/start-fabric.sh` from the project folder. It resumes the existing services without resetting evidence.
2. Open http://127.0.0.1:3001. Keep `sample-data/demo-cases/` available in the file picker.
3. The demo password for all accounts is `DemoOnly!2026` (development only).
4. Explain that actual evidence is encrypted off-chain. The Docker demonstration uses PostgreSQL, MinIO, and the live **two-organization Hyperledger Fabric network**.
5. The practical dataset is documented in [DEMO_CASES.md](docs/DEMO_CASES.md). On a fresh Fabric deployment, run its importer first; ordinary startup only seeds accounts. Duplicate case and evidence identifiers are intentionally rejected.

## Exact presentation sequence

1. Sign in as `investigatorA@nyayavault.local`.
2. Open **Investigation cases**. Show supplier invoice diversion, a night-time collision, missing warehouse stock, and a ransomware incident. Each has three case-specific text records; all people and events are invented.
3. Open **NV-2026-0142 — Supplier invoice diversion**. Both investigators and the forensic/legal demo accounts are assigned. Inspect **NV-0142-EMAIL** in the evidence vault and show the SHA-256 fingerprint, encryption label and chain of custody: Investigator A handed it to the forensic officer.
4. Open **NV-2026-0217 — Night-time collision**. **NV-0217-CAMERA** has an integrity alert because a candidate transcript changed one timestamp. Its original remains encrypted and unchanged. **NV-0217-WITNESS** is honestly unverified.
5. Open the closed **NV-2026-0308** stock case and the open **NV-2026-0419** ransomware incident to show different investigation stages. The camera record is a transcript; no actual video or malware is supplied.
6. Return to **Overview**. Immediately after import it shows four cases, twelve evidence items, ten verified, one alert, one unverified, seven transfers and twelve verification attempts. Subsequent actions update the real counts and history.
7. Open **System status** and a custody record. Show live Fabric connectivity and actual committed transaction IDs. The two Fabric organizations share one channel; user roles and case assignments are enforced by the backend.
8. To demonstrate a new upload, choose **NV-2026-0142**, an unused evidence ID such as **NV-0142-DEMO-01**, type **Forensic Report**, and a description that identifies it as an additional fictional training exhibit. Select `sample-data/demo-cases/mailbox_triage_findings.txt` and register it.
9. The result lists completed steps. Open **Verify integrity** and leave the candidate blank to compare the decrypted stored original. Show the matching hashes and the measured time.
10. As its current custodian, open **Transfer custody**, select **Forensic Officer**, provide an examination reason, confirm and submit. Show the new custody event and real Fabric commit.
11. Sign in as `forensic@nyayavault.local` to inspect the handoff and optionally download that new exhibit. Downloading and opening evidence details record new access events.
12. Sign in as `legal@nyayavault.local` to show assigned read access and restricted upload, transfer and download actions. Case membership also remains necessary for non-administrators.
13. On the cases or evidence page, enable **Include archived cases and evidence** to inspect the old test records, then turn it off. Their original ciphertext, custody history and transaction references remain preserved; new uploads require restoring the archived case.
14. Open **Audit trail** to show recorded actions. Optional OCR/RAG/MFA remain visibly unimplemented.

## Review questions

- **Why not store the file on-chain?** Sensitive file bytes stay encrypted off-chain; the permissioned ledger stores hashes and event proofs only.
- **Can a database administrator rewrite everything?** The local development chain cannot prevent an administrator rebuilding all hashes and anchors. The true Fabric deployment provides an independent permissioned trust boundary, and is connected in the Docker demonstration. Both peers run on this one machine, so this is not operational separation from the host administrator.
- **What is actually tested?** Read `docs/FULL_PROJECT_REPORT.md` for the current tests, actual Fabric commits, browser results and remaining limits.
- **Is the modified file stored?** No. Candidate bytes are hashed for comparison and do not replace or update the original fingerprint or stored ciphertext.

## Presentation cautions

Preserve root `.env`, Fabric runtime identities and Docker data volumes together in a tested backup. The optional SQLite demo separately needs `backend/.env`, its database and `backend/data/`. Never regenerate an encryption key casually. This demo has predictable accounts and uses local HTTP; present with synthetic files. Missing AI functionality does not affect the evidence workflow.
