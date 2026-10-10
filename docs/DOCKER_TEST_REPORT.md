# Docker deployment verification

The frontend, FastAPI, PostgreSQL and source-built MinIO containers are running. The original SQLite/filesystem demo is preserved separately.

| Integration assertion | Actual result |
|---|---|
| Unauthenticated access denied | PASS |
| Login admin | PASS |
| Login investigatorA | PASS |
| Login investigatorB | PASS |
| Login legal | PASS |
| Create PostgreSQL case with assignments | PASS |
| Upload to encrypted object storage | PASS |
| Correct original SHA-256 | PASS |
| Unassigned user cannot see evidence | PASS |
| Assigned non-custodian transfer denied | PASS |
| Original candidate verified | PASS |
| Stored MinIO ciphertext decrypts and verifies | PASS |
| Custody moves A to B | PASS |
| Modified candidate detected | PASS |
| Trusted fingerprint preserved | PASS |
| Authorized download equals original | PASS |
| Custody chain valid | PASS |
| All core events recorded | PASS |
| Audit records match custody events | PASS |
| Dashboard records actual alert | PASS |
| No fabricated Fabric connection | PASS |
| Logout | PASS |
| Logged-out token rejected | PASS |

## Independent storage/database checks

```json
{
  "database": "postgresql",
  "storage": "minio",
  "ciphertext_bytes": 315,
  "plaintext_bytes": 287,
  "encrypted_object": true,
  "decrypted_hash_matches": true,
  "immutable_fingerprint": true,
  "append_only_custody": true
}
```

## Measured timings

Synthetic original: 287 bytes. Timings are from actual backend processing, not a throughput benchmark.

```json
{
  "hash_ms": 0.005333000103746599,
  "encryption_ms": 0.9442919999855803,
  "database_ms": 10.026458000083949,
  "upload_ms": 97.55762500003584
}
```

## Browser check

The Docker frontend at http://127.0.0.1:3001 successfully signed in as Investigator A and displayed the real PostgreSQL/MinIO test record, transfer, integrity alert and metrics. System Status visibly reported `postgresql` and `minio`. Evidence also survived backend container recreation. Screenshot: docker-status-screenshot.png.

## Build fixes

The old MinIO binary images could not be pulled. MinIO was compiled from pinned official source; see docker/minio/README.md. The frontend npm installer stalled in the container; the successful build uses pinned pnpm 10.18.3 with an imported npm lockfile and the same PostCSS security override. Its Next.js production compilation and TypeScript validation passed in Docker.

## Remaining scope

This report records the initial Docker milestone. Hyperledger Fabric is now connected with two organizations; see FULL_PROJECT_REPORT.md for the current executed results. OCR/RAG/MFA remain outside this deployment milestone.
