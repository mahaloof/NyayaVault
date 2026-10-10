#!/usr/bin/env python3
"""Read-only storage, custody, Fabric and original-record preservation checks.

No application login or evidence endpoint is called. Database transactions are
read-only; storage requests only fetch existing objects; Fabric calls only query.
Only the local verification report and temporary decoded channel files are written.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "demo-preservation-results.json"
BACKUPS = ROOT / "blockchain" / "runtime" / "demo-refresh-backups"
DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker" if Path("/Applications/Docker.app/Contents/Resources/bin/docker").exists() else "docker"

# Run inside the backend so existing settings and the same decryption implementation
# are used. Do not instantiate storage(): its constructor can create a missing bucket.
BACKEND = r'''
import hashlib,json,sys
from pathlib import Path
from sqlalchemy import select,func,text
from app.database import SessionLocal,engine
from app.models import Evidence,CustodyEvent,BlockchainTransaction,User,Case
from app.config import settings
from app.storage import decrypt
from app.ledger import verify_chain
from app.blockchain import blockchain
from app.services import evidence_record,record

baseline=json.load(sys.stdin)
originals={item['id']:item for item in baseline['evidence']}
rows=[]
preserved=[]

if settings.storage_provider=='minio':
 from minio import Minio
 client=Minio(settings.minio_endpoint,access_key=settings.minio_access_key,secret_key=settings.minio_secret_key,secure=settings.minio_secure)
 def ciphertext(key):
  response=client.get_object(settings.minio_bucket,key)
  try:return response.read()
  finally:response.close();response.release_conn()
elif settings.storage_provider=='local':
 def ciphertext(key):return (Path(settings.storage_path)/key).read_bytes()
else:
 raise RuntimeError('Unknown storage provider')

def normalized_metadata(item):
 item=dict(item)
 item['tags']=sorted(item.get('tags',[]))
 item['blockchain_transactions']=sorted(item.get('blockchain_transactions',[]),key=lambda tx:tx['event_id'])
 return item

with SessionLocal() as db:
 if engine.dialect.name=='postgresql':
  db.execute(text('SET TRANSACTION READ ONLY'))
 elif engine.dialect.name=='sqlite':
  db.execute(text('PRAGMA query_only=ON'))
 users={user.id:user for user in db.scalars(select(User))}
 cases=list(db.scalars(select(Case)))
 for e in db.scalars(select(Evidence).order_by(Evidence.evidence_id)):
  events=list(db.scalars(select(CustodyEvent).where(CustodyEvent.evidence_id==e.id).order_by(CustodyEvent.sequence)))
  custody=[]
  for event in events:
   item=record(event)
   item['actor']=users[event.actor_user_id].name
   item['from_custodian']=users[event.from_custodian_id].name if event.from_custodian_id else None
   item['to_custodian']=users[event.to_custodian_id].name if event.to_custodian_id else None
   tx=db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id==event.id))
   item['blockchain']=record(tx) if tx else None
   custody.append(item)
  chain=verify_chain(db,e)
  row={'evidence_id':e.evidence_id,'events':len(events),'chain_valid':chain['valid'],'peer_matches':False,'ciphertext':False,'stored_original_valid':False}
  try:
   raw=ciphertext(e.stored_filename)
   plain=decrypt(raw,e.id)
   row['ciphertext']=len(raw)==len(plain)+28 and raw!=plain and plain not in raw
   row['stored_original_valid']=len(plain)==e.file_size and hashlib.sha256(plain).hexdigest()==e.sha256_hash
  except Exception as exc:
   row['storage_error']=type(exc).__name__
  try:
   history=blockchain().get_history(e.evidence_id)
   by_id={item['eventId']:item for item in history}
   all_match=bool(events) and len(history)==len(events)==len(by_id)
   for item in custody:
    p=by_id.get(item['id'],{})
    tx=item['blockchain']
    expected={'eventId':item['id'],'evidenceId':e.evidence_id,'caseId':item['case_id'],'sha256Hash':e.sha256_hash,'action':item['event_type'],'actor':item['actor_user_id'],'timestamp':item['timestamp'],'fromCustodian':item['from_custodian_id'],'toCustodian':item['to_custodian_id'],'verificationResult':item['metadata_json'].get('result'),'applicationEventHash':item['event_hash'],'previousEventHash':item['previous_event_hash']}
    all_match=all_match and tx is not None and tx['status']=='COMMITTED' and bool(tx['tx_id']) and tx['tx_id']==p.get('txId') and all(key in p and p[key]==value for key,value in expected.items())
   row['peer_matches']=bool(all_match)
  except Exception as exc:
   row['peer_error']=type(exc).__name__
  rows.append(row)
  if e.id in originals:
   before=originals[e.id]
   current=evidence_record(db,e)
   complete_before=normalized_metadata(before)
   complete_after=normalized_metadata(current)
   before_custody=baseline['custody'][e.id]
   tx_ids=[event['blockchain']['tx_id'] for event in before_custody['events']]
   preserved.append({'evidence_id':e.evidence_id,'id':e.id,'metadata_unchanged':complete_before==complete_after,'changed_metadata_fields':[key for key in sorted(set(complete_before)|set(complete_after)) if complete_before.get(key)!=complete_after.get(key)],'custody_unchanged':{'events':custody,'ledger':chain}==before_custody,'original_events':len(before_custody['events']),'original_transaction_ids':tx_ids,'transaction_ids_unchanged':tx_ids==[event['blockchain']['tx_id'] if event['blockchain'] else None for event in custody]})
 print(json.dumps({'evidence':rows,'preservation':preserved,'users':len(users),'cases':len(cases),'active_cases':sum(case.status!='ARCHIVED' for case in cases),'archived_cases':sum(case.status=='ARCHIVED' for case in cases),'total_events':sum(row['events'] for row in rows)}))
'''


def command(args: list[str], **kwargs) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, help="Private baseline path; defaults to the latest importer snapshot.")
    args = parser.parse_args()
    checks: list[dict] = []
    result = {"status": "failed", "read_only": True, "checks": checks, "completed_at": datetime.now(timezone.utc).isoformat()}

    def check(name: str, condition: bool) -> None:
        checks.append({"test": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    try:
        candidates = list(BACKUPS.glob("*/baseline.json"))
        baseline_path = args.baseline.resolve() if args.baseline else max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None
        check("A private pre-refresh baseline exists", baseline_path is not None and baseline_path.is_file())
        baseline = json.loads(baseline_path.read_text())
        manifest = json.loads((ROOT / "sample-data" / "demo-cases" / "manifest.json").read_text())
        labels = set(manifest["retire_evidence_ids"])
        originals = [item for item in baseline["evidence"] if item["evidence_id"] in labels]
        check("Baseline contains the original five evidence records", len(originals) == 5 and len(labels) == 5 and {item["evidence_id"] for item in originals} == labels)
        selected = {"evidence": originals, "custody": {item["id"]: baseline["custody"][item["id"]] for item in originals}}
        result["private_baseline"] = str(baseline_path.relative_to(ROOT)) if baseline_path.is_relative_to(ROOT) else baseline_path.name
        result["baseline_captured_at"] = baseline["captured_at"]
        inventory = json.loads(command([DOCKER, "exec", "-i", os.environ.get("NYAYAVAULT_BACKEND_CONTAINER", "nyayavault-backend-1"), "python", "-c", BACKEND], input=json.dumps(selected)))
        result["inventory"] = inventory
        check("Every stored original decrypts, hashes correctly and is AES-GCM ciphertext", bool(inventory["evidence"]) and all(item["stored_original_valid"] and item["ciphertext"] for item in inventory["evidence"]))
        check("Every local custody chain is valid", all(item["chain_valid"] for item in inventory["evidence"]))
        check("Every event and original transaction ID matches real Fabric history", all(item["peer_matches"] for item in inventory["evidence"]))
        check("All five original evidence records remain present", len(inventory["preservation"]) == 5 and {item["evidence_id"] for item in inventory["preservation"]} == labels)
        check("All original evidence metadata and transaction submission records are unchanged", all(item["metadata_unchanged"] for item in inventory["preservation"]))
        check("Complete original custody records and chain anchors are unchanged", all(item["custody_unchanged"] for item in inventory["preservation"]))
        check("All original committed transaction references are unchanged", all(item["transaction_ids_unchanged"] for item in inventory["preservation"]))

        net = ROOT / "blockchain" / "runtime" / "fabric-samples" / "test-network"
        binary = net.parent / "bin"
        env = os.environ.copy()
        env.update(FABRIC_CFG_PATH=str(net.parent / "config"), CORE_PEER_TLS_ENABLED="true")
        peers = {}
        for org, port in (("1", "7051"), ("2", "9051")):
            organization = net / f"organizations/peerOrganizations/org{org}.example.com"
            env.update(CORE_PEER_LOCALMSPID=f"Org{org}MSP", CORE_PEER_ADDRESS="localhost:" + port, CORE_PEER_MSPCONFIGPATH=str(organization / f"users/Admin@org{org}.example.com/msp"), CORE_PEER_TLS_ROOTCERT_FILE=str(organization / f"peers/peer0.org{org}.example.com/tls/ca.crt"))
            peers["Org" + org] = json.loads(command([str(binary / "peer"), "lifecycle", "chaincode", "querycommitted", "-C", "nyayachannel", "-n", "nyayavault", "--output", "json"], env=env))
            check("Org" + org + " confirms both organization approvals", peers["Org" + org]["approvals"] == {"Org1MSP": True, "Org2MSP": True})
        result["peer_definitions"] = peers
        with tempfile.TemporaryDirectory(prefix="nyayavault-demo-query-") as folder:
            block = str(Path(folder) / "config.block")
            decoded = str(Path(folder) / "config.json")
            command([str(binary / "peer"), "channel", "fetch", "config", block, "-c", "nyayachannel", "-o", "localhost:7050", "--ordererTLSHostnameOverride", "orderer.example.com", "--tls", "--cafile", str(net / "organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt")], env=env, stderr=subprocess.DEVNULL)
            command([str(binary / "configtxlator"), "proto_decode", "--input", block, "--type", "common.Block", "--output", decoded])
            application = json.loads(Path(decoded).read_text())["data"]["data"][0]["payload"]["data"]["config"]["channel_group"]["groups"]["Application"]
            check("Channel retains Org1MSP and Org2MSP", sorted(application["groups"]) == ["Org1MSP", "Org2MSP"])
            endorsement = application["policies"]["Endorsement"]["policy"]["value"]
            check("Endorsement requires majority of the two organizations", endorsement == {"rule": "MAJORITY", "sub_policy": "Endorsement"})
            result["channel"] = {"organizations": sorted(application["groups"]), "endorsement": endorsement}
        result["status"] = "passed"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        REPORT.write_text(json.dumps(result, indent=2) + "\n")
        old_events = sum(item["original_events"] for item in inventory["preservation"])
        print(f"{len(checks)} read-only checks passed: {len(inventory['evidence'])} stored originals and {inventory['total_events']} Fabric events verified; all five original evidence records and {old_events} original transaction references preserved. Report: docs/{REPORT.name}")
    except Exception as exc:
        result.update(error=str(exc), completed_at=datetime.now(timezone.utc).isoformat())
        REPORT.write_text(json.dumps(result, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
