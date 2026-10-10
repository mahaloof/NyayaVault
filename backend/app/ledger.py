import hashlib,json
from fastapi import HTTPException
from sqlalchemy import select,update
from app.models import CustodyEvent,AuditLog,BlockchainTransaction,Evidence,uid,now
from app.blockchain import blockchain
from app.config import settings
FIELDS=("id","evidence_id","case_id","sequence","event_type","actor_user_id","actor_role","timestamp","from_custodian_id","to_custodian_id","description","evidence_hash","previous_event_hash","metadata_json")
def digest(event):
    return hashlib.sha256(json.dumps({k:getattr(event,k) for k in FIELDS},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def append_event(db,evidence,user,action,description,metadata=None,from_id=None,to_id=None):
    previous=evidence.ledger_head;sequence=evidence.ledger_seq
    event=CustodyEvent(id=uid(),evidence_id=evidence.id,case_id=evidence.case_id,sequence=sequence+1,event_type=action,actor_user_id=user.id,actor_role=user.role,timestamp=now(),from_custodian_id=from_id,to_custodian_id=to_id,description=description,evidence_hash=evidence.sha256_hash,previous_event_hash=previous,metadata_json=metadata or {})
    event.event_hash=digest(event)
    # Compare-and-swap protects concurrent writers on both SQLite and PostgreSQL.
    result=db.execute(update(Evidence).where(Evidence.id==evidence.id,Evidence.ledger_seq==sequence).values(ledger_head=event.event_hash,ledger_seq=sequence+1).execution_options(synchronize_session=False))
    if result.rowcount!=1: raise HTTPException(409,"Evidence changed concurrently; reload and retry")
    evidence.ledger_head=event.event_hash;evidence.ledger_seq=sequence+1
    db.add(event);db.flush()
    db.add(AuditLog(actor_user_id=user.id,case_id=evidence.case_id,evidence_id=evidence.id,action=action,metadata_json={**event.metadata_json,"event_id":event.id,"actor_role":user.role}))
    db.add(BlockchainTransaction(event_id=event.id,status="PENDING" if settings.blockchain_provider=="fabric" else "DEVELOPMENT"))
    return event

def submit_pending(db,event):
    # Application commits before the external side effect. Failed submissions remain visible.
    tx=db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id==event.id))
    if tx.status!="PENDING": return
    e=db.get(Evidence,event.evidence_id)
    proof={"eventId":event.id,"evidenceId":e.evidence_id,"caseId":event.case_id,"sha256Hash":event.evidence_hash,"action":event.event_type,"actor":event.actor_user_id,"timestamp":event.timestamp,"fromCustodian":event.from_custodian_id,"toCustodian":event.to_custodian_id,"verificationResult":event.metadata_json.get("result"),"applicationEventHash":event.event_hash,"previousEventHash":event.previous_event_hash}
    for k,v in blockchain().record_event(proof).items(): setattr(tx,k,v)
    db.commit()

def verify_chain(db,evidence):
    events=db.scalars(select(CustodyEvent).where(CustodyEvent.evidence_id==evidence.id).order_by(CustodyEvent.sequence)).all()
    previous=""
    for sequence,event in enumerate(events,1):
        if event.sequence!=sequence or event.previous_event_hash!=previous or digest(event)!=event.event_hash or event.evidence_hash!=evidence.sha256_hash:
            return {"valid":False,"events":len(events),"broken_event":event.id}
        previous=event.event_hash
    return {"valid":bool(events) and previous==evidence.ledger_head and len(events)==evidence.ledger_seq,"events":len(events),"head":previous}
