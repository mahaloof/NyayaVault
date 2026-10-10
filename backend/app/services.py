import hashlib,io,zipfile
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Case,CaseMember,Evidence,User,Tag,EvidenceTag,BlockchainTransaction,CustodyEvent

def record(obj): return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}
def user_record(u): return {k:getattr(u,k) for k in ("id","email","name","role")}
def authorized_case(db,user,case_id):
    case=db.get(Case,case_id)
    if not case or (user.role!="ADMIN" and not db.get(CaseMember,(case_id,user.id))): raise HTTPException(404,"Case not found or not authorized")
    return case

def authorized_evidence(db,user,evidence_id):
    evidence=db.scalar(select(Evidence).where(Evidence.id==evidence_id).with_for_update())
    if not evidence: raise HTTPException(404,"Evidence not found")
    authorized_case(db,user,evidence.case_id)
    return evidence

def visible_cases(db,user,include_archived=False):
    query=select(Case)
    if not include_archived: query=query.where(Case.status!="ARCHIVED")
    if user.role!="ADMIN": query=query.join(CaseMember).where(CaseMember.user_id==user.id)
    return list(db.scalars(query.order_by(Case.created_at.desc())).all())
def evidence_record(db,e):
    data=record(e);data.pop("stored_filename");data.pop("ledger_head");data.pop("ledger_seq")
    data["case_number"]=db.get(Case,e.case_id).case_number
    data["case_title"]=db.get(Case,e.case_id).title
    data["custodian"]=db.get(User,e.current_custodian_id).name
    data["uploader"]=db.get(User,e.uploaded_by).name
    data["tags"]=list(db.scalars(select(Tag.name).join(EvidenceTag).where(EvidenceTag.evidence_id==e.id)))
    txs=db.scalars(select(BlockchainTransaction).join(CustodyEvent,BlockchainTransaction.event_id==CustodyEvent.id).where(CustodyEvent.evidence_id==e.id)).all()
    data["blockchain_transactions"]=[record(t) for t in txs]
    return data

def validate_file(filename,data):
    if not data: raise HTTPException(422,"File is empty")
    suffix=Path(filename or "").suffix.lower()
    mime=None
    if suffix==".txt":
        try: data.decode("utf-8")
        except UnicodeDecodeError: raise HTTPException(415,"Text must be UTF-8")
        if b"\x00" in data: raise HTTPException(415,"Invalid text file")
        mime="text/plain"
    elif suffix==".pdf" and data.startswith(b"%PDF-"): mime="application/pdf"
    elif suffix==".png" and data.startswith(b"\x89PNG\r\n\x1a\n"): mime="image/png"
    elif suffix in (".jpg",".jpeg") and data.startswith(b"\xff\xd8\xff"): mime="image/jpeg"
    elif suffix==".mp4" and data[4:8]==b"ftyp": mime="video/mp4"
    elif suffix==".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist() and "[Content_Types].xml" in archive.namelist(): mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except zipfile.BadZipFile: pass
    if not mime: raise HTTPException(415,"Unsupported format or file content does not match extension")
    return mime
