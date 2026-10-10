#!/usr/bin/env python3
"""Capture a private transfer baseline or verify a restored deployment read-only.

Without --baseline, the output contains _private_inventory and must remain private.
With --baseline, the output is a summary: original rows, encrypted objects and
Fabric proofs must match; additional restore-test records are permitted. User token
versions are deliberately excluded because login/logout validation can revoke them.
No application API endpoint is called and no evidence or custody event is written.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


# Kept as an importable constant so the transfer helper can execute the identical
# inventory operation inside the backend without requiring host Python packages.
SNAPSHOT = r'''
import base64,hashlib,json,re
from pathlib import Path
from sqlalchemy import select,text
from app.database import SessionLocal,engine
from app.models import User,Case,CaseMember,Evidence,CustodyEvent,BlockchainTransaction,VerificationLog,AuditLog,Tag,EvidenceTag,OCRDocument
from app.config import settings
from app.storage import decrypt
from app.ledger import verify_chain
from app.blockchain import blockchain
from app.services import record

models=(User,Case,CaseMember,Evidence,CustodyEvent,BlockchainTransaction,VerificationLog,AuditLog,Tag,EvidenceTag,OCRDocument)
tables={}
objects=[]
proofs=[]

# Construct a read-only object client directly: storage() would create a missing
# MinIO bucket or local directory, which is not appropriate for a verifier.
if settings.storage_provider=='minio':
 from minio import Minio
 object_client=Minio(settings.minio_endpoint,access_key=settings.minio_access_key,secret_key=settings.minio_secret_key,secure=settings.minio_secure)
 def get_ciphertext(key):
  response=object_client.get_object(settings.minio_bucket,key)
  try:return response.read()
  finally:response.close();response.release_conn()
elif settings.storage_provider=='local':
 def get_ciphertext(key):return (Path(settings.storage_path)/key).read_bytes()
else:
 raise RuntimeError('Unsupported evidence storage provider')

with SessionLocal() as db:
 if engine.dialect.name=='postgresql':
  db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
 elif engine.dialect.name=='sqlite':
  db.execute(text('PRAGMA query_only=ON'))
 for model in models:
  columns=list(model.__table__.primary_key.columns)
  rows=[]
  for value in db.scalars(select(model).order_by(*columns)):
   if model is User:
    item={field:getattr(value,field) for field in ('id','email','name','role')}
    item['password_hash_sha256']=hashlib.sha256(value.password_hash.encode()).hexdigest()
   else:item=record(value)
   rows.append(item)
  tables[model.__tablename__]=rows
 transactions={tx['event_id']:tx for tx in tables['blockchain_transactions']}
 by_evidence={}
 for event in tables['custody_events']:
  by_evidence.setdefault(event['evidence_id'],[]).append(event)
 for e in db.scalars(select(Evidence).order_by(Evidence.id)):
  chain=verify_chain(db,e)
  obj={'id':e.id,'evidence_id':e.evidence_id,'stored_filename':e.stored_filename,'ciphertext_sha256':None,'plaintext_sha256':None,'ciphertext_valid':False,'original_valid':False}
  try:
   raw=get_ciphertext(e.stored_filename)
   obj['ciphertext_sha256']=hashlib.sha256(raw).hexdigest()
   plain=decrypt(raw,e.id)
   obj['plaintext_sha256']=hashlib.sha256(plain).hexdigest()
   obj['ciphertext_valid']=len(raw)==len(plain)+28 and raw!=plain
   obj['original_valid']=obj['plaintext_sha256']==e.sha256_hash and len(plain)==e.file_size
  except Exception as exc:obj['storage_error']=type(exc).__name__
  objects.append(obj)
  events=sorted(by_evidence.get(e.id,[]),key=lambda event:event['sequence'])
  proof={'id':e.id,'evidence_id':e.evidence_id,'chain':chain,'events':len(events),'peer_matches':False,'history':[]}
  try:
   history=blockchain().get_history(e.evidence_id)
   proof['history']=history
   history_by_id={item['eventId']:item for item in history}
   matched=bool(events) and len(history)==len(events)==len(history_by_id)
   for event in events:
    actual=history_by_id.get(event['id'],{})
    tx=transactions.get(event['id'])
    expected={'eventId':event['id'],'evidenceId':e.evidence_id,'caseId':event['case_id'],'sha256Hash':e.sha256_hash,'action':event['event_type'],'actor':event['actor_user_id'],'timestamp':event['timestamp'],'fromCustodian':event['from_custodian_id'],'toCustodian':event['to_custodian_id'],'verificationResult':event['metadata_json'].get('result'),'applicationEventHash':event['event_hash'],'previousEventHash':event['previous_event_hash']}
    matched=matched and tx is not None and tx['status']=='COMMITTED' and bool(re.fullmatch(r'[a-f0-9]{64}',tx['tx_id'] or '')) and tx['tx_id']==actual.get('txId') and all(key in actual and actual[key]==value for key,value in expected.items())
   proof['peer_matches']=bool(matched)
  except Exception as exc:proof['peer_error']=type(exc).__name__
  proofs.append(proof)
 counts={table:len(rows) for table,rows in tables.items()}
 counts.update(active_cases=sum(case['status']!='ARCHIVED' for case in tables['cases']),archived_cases=sum(case['status']=='ARCHIVED' for case in tables['cases']),encrypted_objects=len(objects),fabric_events=sum(item['events'] for item in proofs))
 passed=bool(tables['evidence']) and settings.blockchain_provider=='fabric' and all(item['ciphertext_valid'] and item['original_valid'] for item in objects) and all(item['chain']['valid'] and item['peer_matches'] for item in proofs)
 print(json.dumps({'passed':passed,'tables':tables,'objects':objects,'proofs':proofs,'counts':counts,'settings':{'storage_provider':settings.storage_provider,'blockchain_provider':settings.blockchain_provider,'encryption_key_sha256':hashlib.sha256(base64.b64decode(settings.evidence_master_key)).hexdigest()},'excluded_user_fields':['token_version']}))
'''


PRIMARY_KEYS = {
    "users": ("id",), "cases": ("id",), "case_members": ("case_id", "user_id"),
    "evidence": ("id",), "custody_events": ("id",),
    "blockchain_transactions": ("id",), "verification_logs": ("id",),
    "audit_logs": ("id",), "tags": ("id",),
    "evidence_tags": ("evidence_id", "tag_id"), "ocr_documents": ("id",),
}


def snapshot(container: str) -> dict:
    docker = shutil.which("docker")
    mac_docker = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if not docker and mac_docker.exists():
        docker = str(mac_docker)
    if not docker:
        raise RuntimeError("Docker CLI was not found. Start Docker Desktop and make docker available on PATH.")
    result = subprocess.run([docker, "exec", "-i", container, "python", "-c", SNAPSHOT], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Backend read-only inventory failed (exit {result.returncode}): {result.stderr.strip()[:1500]}")
    return json.loads(result.stdout)


def write_report(path: Path, report: dict, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Baseline files contain identifying metadata, password-hash digests and
    # signer identity references. Keep them private even on the source host.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    if os.name != "nt":
        path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True, help="Running backend container to inspect.")
    parser.add_argument("--outputfile", "--output-file", "--output", dest="outputfile", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="Previously captured private baseline; omission captures a new baseline.")
    args = parser.parse_args()
    checks: list[dict] = []
    report = {"status": "failed", "mode": "verify" if args.baseline else "baseline", "read_only": True, "container": args.container, "completed_at": datetime.now(timezone.utc).isoformat(), "checks": checks, "excluded_user_fields": ["token_version"]}

    def check(name: str, condition: bool) -> None:
        checks.append({"test": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    try:
        baseline = None
        if args.baseline:
            if args.baseline.resolve() == args.outputfile.resolve():
                raise RuntimeError("Verification output must not overwrite its private baseline.")
            payload = json.loads(args.baseline.read_text(encoding="utf-8"))
            # transfer.py writes the raw SNAPSHOT result; standalone baseline
            # mode wraps the same inventory in its private report field.
            baseline = payload.get("_private_inventory", payload)
            successful = payload.get("status") == "passed" if "_private_inventory" in payload else payload.get("passed") is True
            check("Private source baseline is a successful snapshot", successful and isinstance(baseline.get("tables"), dict) and baseline.get("passed") is True)
        elif args.outputfile.exists():
            raise RuntimeError("Baseline output already exists. Choose a new private path to preserve the previous snapshot.")
        inventory = snapshot(args.container)
        report["counts"] = inventory["counts"]
        if baseline is None:
            report["_private_inventory"] = inventory
        check("Evidence inventory is nonempty", bool(inventory["tables"]["evidence"]))
        check("Every encrypted original authenticates and matches its trusted SHA-256", all(item["ciphertext_valid"] and item["original_valid"] for item in inventory["objects"]))
        check("Every application custody chain is valid", all(item["chain"]["valid"] for item in inventory["proofs"]))
        check("Every custody event and committed transaction ID matches real Fabric history", inventory["settings"]["blockchain_provider"] == "fabric" and all(item["peer_matches"] for item in inventory["proofs"]))

        if baseline is not None:
            preservation = {}
            report["preservation"] = preservation
            check("Original evidence encryption key and providers are unchanged", inventory["settings"] == baseline["settings"])
            for table, fields in PRIMARY_KEYS.items():
                previous = baseline["tables"][table]
                current = {tuple(row[field] for field in fields): row for row in inventory["tables"][table]}
                missing = []
                changed = []
                for row in previous:
                    identity = tuple(row[field] for field in fields)
                    if identity not in current:
                        missing.append(identity)
                    elif current[identity] != row:
                        changed.append(identity)
                preservation[table] = {"original_rows": len(previous), "current_rows": len(current), "missing_rows": len(missing), "changed_rows": len(changed), "unchanged": not missing and not changed}
                check(f"All original {table} rows are unchanged", not missing and not changed)
            current_objects = {item["id"]: item for item in inventory["objects"]}
            check("Every original ciphertext object and decrypted fingerprint is identical", all(current_objects.get(item["id"]) == item for item in baseline["objects"]))
            current_proofs = {item["id"]: item for item in inventory["proofs"]}
            check("Complete original Fabric histories, proof fields and transaction references are unchanged", all(current_proofs.get(item["id"]) == item for item in baseline["proofs"]))
            report["preserved_original_counts"] = baseline["counts"]
            report["additional_records_allowed"] = True

        report.update(status="passed", completed_at=datetime.now(timezone.utc).isoformat())
        write_report(args.outputfile, report, exclusive=args.baseline is None)
        counts = inventory["counts"]
        print(f"{len(checks)} read-only {report['mode']} checks passed: {counts['users']} users, {counts['cases']} cases, {counts['evidence']} encrypted originals, {counts['custody_events']} custody events. Output: {args.outputfile}")
        return 0
    except Exception as exc:
        report.update(error=str(exc), completed_at=datetime.now(timezone.utc).isoformat())
        # Refuse to destroy an earlier baseline even when validation fails.
        if args.baseline is None and args.outputfile.exists():
            print(f"Verification failed: {exc}", file=sys.stderr)
            return 1
        if args.baseline and args.baseline.resolve() == args.outputfile.resolve():
            print(f"Verification failed: {exc}", file=sys.stderr)
            return 1
        write_report(args.outputfile, report, exclusive=args.baseline is None)
        print(f"Verification failed: {exc}. Report: {args.outputfile}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
