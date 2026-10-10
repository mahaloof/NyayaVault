# Implementation status

8 October portability: the standalone Docker configuration and Windows Import/Start/Stop/Status/Test/Export scripts are implemented. Exact-data restore, fresh demo creation, repeated starts, identity preservation and real Fabric workflows passed on Docker Desktop / Linux arm64. Native Windows remains untested. See [PORTABILITY_REPORT.md](PORTABILITY_REPORT.md) and [Windows guide](../WINDOWS_START_HERE.md).

| Capability | Implementation | Execution evidence |
|---|---|---|
| Authentication / JWT / logout revocation | Implemented | Backend automated tests |
| Case access and assignments | Implemented | Backend automated tests |
| Upload / SHA-256 / encrypted local storage | Implemented | Backend automated tests |
| Original and modified candidate verification | Implemented | Full acceptance test |
| Custody transfer and authorization | Implemented | Backend automated tests |
| Hash-linked event ledger / mutation detection | Implemented | Backend automated tests |
| Append-only guards and trusted hash immutability | Implemented | SQLite migration and tests |
| Download / audit logging | Implemented | Backend automated tests |
| Dashboard and measured metrics | Implemented | API acceptance artifact |
| Frontend routes and styling | Implemented | Production build and TypeScript check |
| Automated browser suite | Written | Launch blocked by macOS sandbox; not passed |
| PostgreSQL | Running in Docker | Migration, real API integration and immutability guards passed |
| MinIO | Running in Docker, built from official source | Encrypted object upload, decrypt, hash and download checks passed |
| Fabric chaincode | Implemented | Three contract unit tests passed |
| Fabric Gateway + backend adapter | Running | 24 HTTP checks and 4 direct peer/gateway checks passed |
| Live Fabric network | Connected | Fabric 2.5.16, two peers, channel and chaincode committed; eight prior events backfilled |
| OCR / classification / RAG / graph / MFA | Not implemented | Explicitly disabled/labeled |

See TEST_REPORT.md and browser-validation.md for final executed results. The project is a functional local academic prototype, not a certified forensic or production deployment.

Docker follow-up: all four containers built and started; browser login and dashboard verified on port 3001. See DOCKER_TEST_REPORT.md for executed PostgreSQL/MinIO results.

Fabric follow-up: see FABRIC_TEST_REPORT.md and FABRIC.md for the real network validation and restart instructions.

Latest complete validation: [FULL_PROJECT_REPORT.md](FULL_PROJECT_REPORT.md), 7 October 2026. Live role tests and all-evidence storage/peer consistency checks passed.

8 October practical demo refresh: [DEMO_CASES.md](DEMO_CASES.md) describes the four fictional investigations and twelve evidence originals. Archive filtering and upload protection passed all 22 backend tests. The executed refresh and read-only preservation checks are recorded separately in `demo-refresh-results.json` and `demo-preservation-results.json`; these retain the distinction between new real transactions and original test history.
