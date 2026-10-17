# Fresh local demonstration — 17 October 2026

The user requested a complete reset of cases, evidence and blockchain history. The active Mac Docker deployment is now empty and ready for new cases.

- All 9 cases (including archived cases), 17 evidence records and encrypted objects, 70 custody events and corresponding application transaction records were removed. Verification, audit, case membership, tag and OCR records were also cleared.
- All five user accounts, passwords, application configuration, encryption keys, Gemini settings, Fabric identities and application code were preserved.
- Both Fabric peers and the orderer were reset. The original channel genesis configuration was reused, and both organizations approved a fresh chaincode definition with a two-organization endorsement policy. No evidence events were replayed.
- Both peers have four setup-only blocks: genesis, two organization approvals and chaincode-definition commit. These are necessary network setup transactions, not old evidence history.
- Read-only verification confirmed zero application records and objects, empty history for all 17 former evidence IDs on both peers, connected Fabric, and available AI/OCR. No test case or evidence was created after reset. See [results](fresh-start-results.json).

## Start and use

Open http://127.0.0.1:3001 and refresh any previously open page. Existing accounts still work. Create a new case through Investigation cases, assign its users, then upload evidence.

Resume this existing deployment with `bash scripts/start-fabric.sh`. Normal backend startup seeds only missing user accounts, not cases. Do not run `scripts/populate-demo.py` unless you want demonstration records added again. The separate portable startup can populate demo records by default; use its `--no-demo` option (Windows: `-NoDemo`) to start it without examples.

## Private recovery backup

The verified pre-reset snapshot is in `cleanup-recovery/before-fresh-start-20261016/`, excluded from Git. It contains the PostgreSQL dump, encrypted objects, original peer/orderer ledgers, identities, original environment configuration and checksums. The old data remains only as recovery material; it is not visible in the running app. Protect this directory because it includes credentials and encryption keys.

Restore the snapshot as a consistent whole using the documented transfer workflow into an empty target deployment. Do not restore just the old database onto the fresh blockchain. Historical demonstration/test reports describe the prior deployment and do not represent current record counts.
