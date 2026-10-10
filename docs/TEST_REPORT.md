# Phase-II executed test report

Generated from actual pytest JUnit results; statuses are not hardcoded.

The backend tests use a fresh SQLite database, the actual Alembic migration, real Argon2 passwords, AES-GCM encryption and encrypted filesystem bytes. Synthetic TXT evidence is used. Results do not establish PostgreSQL, MinIO or live Fabric compatibility.

| Test case | Input / scenario | Expected | Actual | Execution time |
|---|---|---|---|---|
| test_valid_login | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 235.000 ms |
| test_invalid_login | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 3.000 ms |
| test_unauthorized_endpoint | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 8.000 ms |
| test_create_case | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 78.000 ms |
| test_upload_hash_encryption_and_download | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 56.000 ms |
| test_duplicate_evidence_id | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 45.000 ms |
| test_full_acceptance_workflow | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 112.000 ms |
| test_unauthorized_transfer | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 81.000 ms |
| test_viewer_cannot_upload_or_download | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 106.000 ms |
| test_invalid_format_and_size | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 42.000 ms |
| test_stored_verification_and_corruption | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 50.000 ms |
| test_immutable_fingerprint_and_append_only_events | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 45.000 ms |
| test_ledger_detects_historical_mutation | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 51.000 ms |
| test_logout_revokes_token | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 48.000 ms |
| test_blockchain_adapters | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 42.000 ms |
| test_assigned_non_custodian_cannot_transfer | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 100.000 ms |
| test_user_management_and_case_assignments | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 111.000 ms |
| test_expired_token_rejected | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 2.000 ms |
| test_missing_file_and_bad_case | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 40.000 ms |
| test_storage_failure_is_visible | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 40.000 ms |
| test_failed_fabric_submission_is_persisted | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 56.000 ms |
| test_archived_cases_leave_workspace_but_preserve_proofs | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | PASS | 176.000 ms |

## Measured acceptance timings

One automated acceptance execution with a 287-byte synthetic report. Warm local process; these measurements are not a load benchmark. Upload time includes backend processing, not browser transfer.

- hash_ms: 0.003250 ms
- encryption_ms: 0.023750 ms
- database_ms: 1.751375 ms
- upload_ms: 2.555458 ms
- Original candidate verification: 0.307167 ms
- Modified candidate verification: 0.254542 ms

## Scope and current deployment

These 22 tests cover a fresh SQLite/local-storage environment and simulated Fabric failure paths. They are separate from the real Docker integration checks. For the current two-organization Fabric, PostgreSQL, MinIO, browser, permission, cleanup, and limitation results, read [FULL_PROJECT_REPORT.md](FULL_PROJECT_REPORT.md). The older standalone Playwright launch failure is historical and is not counted as a pass.
