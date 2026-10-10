from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form,Response,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from pathlib import Path
from time import perf_counter
import hashlib,re
from urllib.parse import quote
from cryptography.exceptions import InvalidTag
from app.database import get_db
from app.config import settings
from app.models import Evidence,Case,CaseMember,User,Tag,EvidenceTag,VerificationLog,CustodyEvent,BlockchainTransaction,uid,now
from app.security import current_user,roles
from app.schemas import Transfer
from app.services import authorized_case,authorized_evidence,visible_cases,evidence_record,record,validate_file
from app.storage import storage,encrypt,decrypt
from app.ledger import append_event,submit_pending,verify_chain
router=APIRouter(prefix="/api/evidence")
def read_limited(file):
    data=file.file.read(settings.max_file_mb*1024*1024+1)
    if len(data)>settings.max_file_mb*1024*1024: raise HTTPException(413,f"File exceeds {settings.max_file_mb} MB limit")
    return data
def finish(db,event): db.commit();submit_pending(db,event)
@router.post("",status_code=201)
def upload(request:Request,case_id:str=Form(...),evidence_id:str=Form(...),file:UploadFile=File(...),evidence_type:str=Form("Document"),description:str=Form(""),source:str=Form(""),collection_location:str=Form(""),collected_at:str=Form(""),tags:str=Form(""),user=Depends(current_user),db:Session=Depends(get_db)):
    started=perf_counter();roles(user,"ADMIN","INVESTIGATOR","FORENSIC_OFFICER");case=authorized_case(db,user,case_id)
    if case.status=="ARCHIVED": raise HTTPException(409,"Restore the archived case before registering new evidence")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}",evidence_id): raise HTTPException(422,"Evidence ID must be 3–80 letters, digits, underscores or hyphens")
    if any(len(v)>10000 for v in [description,source,collection_location,tags]) or len(evidence_type)>80: raise HTTPException(422,"Metadata is too long")
    if db.scalar(select(Evidence).where(Evidence.evidence_id==evidence_id)): raise HTTPException(409,"Evidence ID already exists")
    data=read_limited(file);mime=validate_file(file.filename,data);t=perf_counter();trusted=hashlib.sha256(data).hexdigest();hash_ms=(perf_counter()-t)*1000
    id=uid();t=perf_counter();encrypted=encrypt(data,id);enc_ms=(perf_counter()-t)*1000
    key=id+".aesgcm"
    try:
        adapter=storage();adapter.put(key,encrypted)
    except Exception: raise HTTPException(503,"Encrypted storage unavailable")
    try:
        t=perf_counter()
        e=Evidence(id=id,evidence_id=evidence_id,case_id=case_id,original_filename=Path(file.filename or "evidence").name[:255],stored_filename=key,mime_type=mime,file_size=len(data),evidence_type=evidence_type,description=description,source=source,collection_location=collection_location,collected_at=collected_at,sha256_hash=trusted,encryption_metadata={"algorithm":"AES-256-GCM","nonce":"first 12 bytes","aad":"evidence UUID","key_version":"1"},uploaded_by=user.id,current_custodian_id=user.id,timings={"hash_ms":hash_ms,"encryption_ms":enc_ms})
        db.add(e);db.flush()
        for name in sorted(set(s.strip()[:80] for s in tags.split(",") if s.strip()))[:20]:
            tag=db.scalar(select(Tag).where(Tag.name==name))
            if not tag: tag=Tag(name=name);db.add(tag);db.flush()
            db.add(EvidenceTag(evidence_id=id,tag_id=tag.id))
        event=append_event(db,e,user,"EVIDENCE_UPLOADED","Evidence registered and encrypted",{"ip":request.client.host,"bytes":len(data)},to_id=user.id)
        db.commit()
    except Exception:
        db.rollback();adapter.delete(key);raise
    db_ms=(perf_counter()-t)*1000
    submit_pending(db,event)
    e.timings={**e.timings,"database_ms":db_ms,"upload_ms":(perf_counter()-started)*1000};db.commit()
    return {**evidence_record(db,e),"completed_steps":["File received","SHA-256 fingerprint generated","AES-256-GCM encrypted","Encrypted evidence stored","Metadata recorded","Custody event created"]}
@router.get("")
def listing(q:str="",case_id:str="",status:str="",evidence_type:str="",custodian:str="",uploader:str="",date_from:str="",date_to:str="",include_archived:bool=False,user=Depends(current_user),db:Session=Depends(get_db)):
    ids=[c.id for c in visible_cases(db,user,include_archived)];query=select(Evidence).where(Evidence.case_id.in_(ids)).order_by(Evidence.created_at.desc())
    if case_id: query=query.where(Evidence.case_id==case_id)
    if status: query=query.where((Evidence.status==status)|(Evidence.integrity_status==status))
    if evidence_type: query=query.where(Evidence.evidence_type==evidence_type)
    if custodian: query=query.where(Evidence.current_custodian_id==custodian)
    if uploader: query=query.where(Evidence.uploaded_by==uploader)
    if date_from: query=query.where(Evidence.created_at>=date_from)
    if date_to: query=query.where(Evidence.created_at<=date_to+"T23:59:59.999999+00:00")
    items=[evidence_record(db,e) for e in db.scalars(query)]
    return [e for e in items if not q or q.lower() in " ".join(str(e[k]) for k in ("evidence_id","case_number","case_title","original_filename","description","tags","custodian","uploader")).lower()]
@router.get("/{id}")
def detail(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    e=authorized_evidence(db,user,id);event=append_event(db,e,user,"EVIDENCE_ACCESSED","Evidence metadata accessed");finish(db,event);return evidence_record(db,e)
@router.post("/{id}/verify")
def verify(id:str,file:UploadFile|None=File(default=None),user=Depends(current_user),db:Session=Depends(get_db)):
    start=perf_counter();e=authorized_evidence(db,user,id)
    if file: data=read_limited(file)
    else:
        try: data=decrypt(storage().get(e.stored_filename),e.id)
        except InvalidTag:
            db.add(VerificationLog(evidence_id=e.id,actor_user_id=user.id,trusted_hash=e.sha256_hash,calculated_hash="",result="AUTHENTICATION_FAILED",elapsed_ms=(perf_counter()-start)*1000))
            e.integrity_status="INTEGRITY_ALERT";event=append_event(db,e,user,"INTEGRITY_FAILED","Stored ciphertext authentication failed",{"result":"AUTHENTICATION_FAILED"});finish(db,event)
            raise HTTPException(409,"Stored evidence failed AES-GCM authentication; integrity alert recorded")
        except Exception: raise HTTPException(503,"Evidence storage unavailable")
    calculated=hashlib.sha256(data).hexdigest();matched=calculated==e.sha256_hash;result="VERIFIED" if matched else "INTEGRITY_ALERT"
    elapsed=(perf_counter()-start)*1000;e.integrity_status=result
    log=VerificationLog(evidence_id=e.id,actor_user_id=user.id,trusted_hash=e.sha256_hash,calculated_hash=calculated,result=result,elapsed_ms=elapsed);db.add(log)
    event=append_event(db,e,user,"INTEGRITY_VERIFIED" if matched else "INTEGRITY_FAILED","Original fingerprint compared with "+("candidate file" if file else "decrypted stored evidence"),{"result":result,"calculated_hash":calculated,"elapsed_ms":elapsed,"candidate":file.filename if file else "stored original"});finish(db,event)
    return {"matched":matched,"result":result,"message":"EVIDENCE INTEGRITY VERIFIED" if matched else "INTEGRITY VERIFICATION FAILED","trusted_hash":e.sha256_hash,"calculated_hash":calculated,"verified_by":user.name,"timestamp":log.timestamp,"elapsed_ms":elapsed}
@router.post("/{id}/transfer")
def transfer(id:str,data:Transfer,user=Depends(current_user),db:Session=Depends(get_db)):
    e=authorized_evidence(db,user,id);roles(user,"ADMIN","INVESTIGATOR","FORENSIC_OFFICER")
    if user.role!="ADMIN" and e.current_custodian_id!=user.id: raise HTTPException(403,"Only the current custodian or administrator may transfer")
    receiver=db.get(User,data.to_custodian_id)
    if not receiver or receiver.role not in ("ADMIN","INVESTIGATOR","FORENSIC_OFFICER") or not db.get(CaseMember,(e.case_id,receiver.id)): raise HTTPException(422,"Recipient must be an authorized case member with a custody role")
    if receiver.id==e.current_custodian_id: raise HTTPException(409,"Recipient already holds custody")
    sender=e.current_custodian_id;e.current_custodian_id=receiver.id;e.status="TRANSFERRED"
    event=append_event(db,e,user,"CUSTODY_TRANSFERRED",data.reason,from_id=sender,to_id=receiver.id);finish(db,event);return evidence_record(db,e)
@router.get("/{id}/custody")
def custody(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    e=authorized_evidence(db,user,id)
    items=[]
    for event in db.scalars(select(CustodyEvent).where(CustodyEvent.evidence_id==id).order_by(CustodyEvent.sequence)):
        d=record(event);d["actor"]=db.get(User,event.actor_user_id).name
        d["from_custodian"]=db.get(User,event.from_custodian_id).name if event.from_custodian_id else None
        d["to_custodian"]=db.get(User,event.to_custodian_id).name if event.to_custodian_id else None
        tx=db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id==event.id));d["blockchain"]=record(tx) if tx else None;items.append(d)
    return {"events":items,"ledger":verify_chain(db,e)}
@router.get("/{id}/blockchain")
def proof(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    return custody(id,user,db)
@router.get("/{id}/download")
def download(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    e=authorized_evidence(db,user,id);roles(user,"ADMIN","INVESTIGATOR","FORENSIC_OFFICER");start=perf_counter()
    try: data=decrypt(storage().get(e.stored_filename),e.id)
    except InvalidTag:
        e.integrity_status="INTEGRITY_ALERT";event=append_event(db,e,user,"INTEGRITY_FAILED","Download blocked: ciphertext authentication failed");finish(db,event);raise HTTPException(409,"Stored evidence failed authentication")
    except Exception: raise HTTPException(503,"Evidence storage unavailable")
    if hashlib.sha256(data).hexdigest()!=e.sha256_hash:
        e.integrity_status="INTEGRITY_ALERT";event=append_event(db,e,user,"INTEGRITY_FAILED","Download blocked: plaintext fingerprint mismatch");finish(db,event);raise HTTPException(409,"Stored evidence fingerprint mismatch")
    event=append_event(db,e,user,"EVIDENCE_DOWNLOADED","Authorized evidence retrieval prepared",{"decryption_ms":(perf_counter()-start)*1000});finish(db,event)
    return Response(data,media_type="application/octet-stream",headers={"Content-Disposition":"attachment; filename*=UTF-8''"+quote(e.original_filename),"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
