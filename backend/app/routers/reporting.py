from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from collections import Counter
from app.database import get_db
from app.security import current_user
from app.models import Evidence,CustodyEvent,AuditLog,User,Case,VerificationLog,BlockchainTransaction
from app.services import visible_cases,evidence_record,record
from app.blockchain import blockchain
from app.config import settings
from app.database import engine
router=APIRouter(prefix="/api")
@router.get("/audit")
def audit(case_id:str="",evidence_id:str="",actor:str="",action:str="",date_from:str="",date_to:str="",include_archived:bool=False,user=Depends(current_user),db:Session=Depends(get_db)):
    ids=[c.id for c in visible_cases(db,user,include_archived)];query=select(AuditLog).order_by(AuditLog.timestamp.desc())
    if user.role!="ADMIN": query=query.where(AuditLog.case_id.in_(ids))
    elif not include_archived: query=query.where((AuditLog.case_id.in_(ids)) | (AuditLog.case_id.is_(None)))
    if case_id: query=query.where(AuditLog.case_id==case_id)
    if evidence_id: query=query.where(AuditLog.evidence_id==evidence_id)
    if actor: query=query.where(AuditLog.actor_user_id==actor)
    if action: query=query.where(AuditLog.action==action)
    if date_from: query=query.where(AuditLog.timestamp>=date_from)
    if date_to: query=query.where(AuditLog.timestamp<=date_to+"T23:59:59.999999+00:00")
    result=[]
    for log in db.scalars(query):
        d=record(log);u=db.get(User,log.actor_user_id);d["actor"]=u.name;d["role"]=log.metadata_json.get("actor_role",u.role)
        tx=db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id==log.metadata_json.get("event_id","")))
        d["blockchain_tx_id"]=tx.tx_id if tx else None
        d["evidence_label"]=db.get(Evidence,log.evidence_id).evidence_id if log.evidence_id else "—"
        d["case_number"]=db.get(Case,log.case_id).case_number if log.case_id else "—";result.append(d)
    return result
@router.get("/dashboard")
def dashboard(user=Depends(current_user),db:Session=Depends(get_db)):
    cases=visible_cases(db,user);ids=[c.id for c in cases];evidence=list(db.scalars(select(Evidence).where(Evidence.case_id.in_(ids)).order_by(Evidence.created_at.desc())))
    eids=[e.id for e in evidence];logs=list(db.scalars(select(VerificationLog).where(VerificationLog.evidence_id.in_(eids))))
    events=list(db.scalars(select(CustodyEvent).where(CustodyEvent.case_id.in_(ids)).order_by(CustodyEvent.timestamp.desc())))
    txs=list(db.scalars(select(BlockchainTransaction).join(CustodyEvent,BlockchainTransaction.event_id==CustodyEvent.id).where(CustodyEvent.case_id.in_(ids))))
    avg=lambda values: round(sum(values)/len(values),3) if values else None
    return {"total_cases":len(cases),"total_evidence":len(evidence),"verified":sum(e.integrity_status=="VERIFIED" for e in evidence),"alerts":sum(e.integrity_status=="INTEGRITY_ALERT" for e in evidence),"transfers":sum(e.event_type=="CUSTODY_TRANSFERRED" for e in events),"verification_attempts":len(logs),"successful_verifications":sum(l.result=="VERIFIED" for l in logs),"detected_mismatches":sum(l.result=="INTEGRITY_ALERT" for l in logs),"blockchain_transactions":sum(t.status=="COMMITTED" for t in txs),"failed_blockchain_transactions":sum(t.status=="FAILED" for t in txs),"metrics":{"average_hash_ms":avg([e.timings["hash_ms"] for e in evidence]),"average_encryption_ms":avg([e.timings["encryption_ms"] for e in evidence]),"average_upload_ms":avg([e.timings.get("upload_ms",0) for e in evidence]),"average_database_ms":avg([e.timings.get("database_ms",0) for e in evidence]),"average_verification_ms":avg([l.elapsed_ms for l in logs]),"average_decryption_ms":avg([e.metadata_json["decryption_ms"] for e in events if "decryption_ms" in e.metadata_json]),"average_blockchain_ms":avg([t.elapsed_ms for t in txs if t.status!="DEVELOPMENT"])},"evidence_types":dict(Counter(e.evidence_type for e in evidence)),"recent_evidence":[evidence_record(db,e) for e in evidence[:5]],"recent_activity":[{**record(e),"actor":db.get(User,e.actor_user_id).name,"evidence_label":db.get(Evidence,e.evidence_id).evidence_id} for e in events[:10]],"blockchain":blockchain().status()}
@router.get("/blockchain/status")
def status(user=Depends(current_user)):
    return {**blockchain().status(),"database":engine.dialect.name,"storage":settings.storage_provider,"features":{"Evidence upload":"IMPLEMENTED","SHA-256 integrity":"IMPLEMENTED","AES-256-GCM":"IMPLEMENTED","Custody transfer":"IMPLEMENTED","Application hash-linked ledger":"IMPLEMENTED","OCR":"Local printed-English OCR for PDFs, PNG and JPEG","Case assistant":("CONFIGURED — Google Gemini" if settings.ai_provider=="gemini" and settings.gemini_api_key.get_secret_value() else "DISABLED — configure Gemini"),"RAG search":"Selected evidence excerpts only; no vector index","MFA":"NOT IMPLEMENTED","Relationship graph":"NOT IMPLEMENTED"}}
