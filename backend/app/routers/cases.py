from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,delete,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Case,CaseMember,User,AuditLog,Evidence
from app.schemas import CaseCreate
from app.security import current_user,roles
from app.services import authorized_case,visible_cases,record,user_record,evidence_record
router=APIRouter(prefix="/api/cases")
def members(db,case,data,user):
    ids=set(data.member_ids)|{case.created_by,user.id}
    for id in ids:
        if not db.get(User,id): raise HTTPException(422,"Assigned user does not exist")
    existing=set(db.scalars(select(CaseMember.user_id).where(CaseMember.case_id==case.id)))
    custodians=set(db.scalars(select(Evidence.current_custodian_id).where(Evidence.case_id==case.id)))
    if custodians-ids: raise HTTPException(409,"Cannot remove a current evidence custodian")
    for id in existing-ids: db.delete(db.get(CaseMember,(case.id,id)))
    for id in ids-existing: db.add(CaseMember(case_id=case.id,user_id=id))
def case_record(db,c):
    d=record(c);d["evidence_count"]=db.scalar(select(func.count()).select_from(Evidence).where(Evidence.case_id==c.id));return d
@router.get("")
def listing(include_archived:bool=False,user=Depends(current_user),db:Session=Depends(get_db)): return [case_record(db,c) for c in visible_cases(db,user,include_archived)]
@router.post("",status_code=201)
def create(data:CaseCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    roles(user,"ADMIN","INVESTIGATOR")
    c=Case(**data.model_dump(exclude={"member_ids"}),created_by=user.id);db.add(c);db.flush();members(db,c,data,user)
    db.add(AuditLog(actor_user_id=user.id,case_id=c.id,action="CASE_CREATED"));db.commit();return record(c)
@router.get("/{id}")
def detail(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    c=authorized_case(db,user,id);d=case_record(db,c)
    d["members"]=[user_record(u) for u in db.scalars(select(User).join(CaseMember).where(CaseMember.case_id==id))]
    d["evidence"]=[evidence_record(db,e) for e in db.scalars(select(Evidence).where(Evidence.case_id==id))]
    return d
@router.get("/{id}/evidence")
def evidence(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    authorized_case(db,user,id);return [evidence_record(db,e) for e in db.scalars(select(Evidence).where(Evidence.case_id==id))]
@router.get("/{id}/members")
def case_members(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    authorized_case(db,user,id)
    return [user_record(u) for u in db.scalars(select(User).join(CaseMember).where(CaseMember.case_id==id))]
@router.put("/{id}")
def update_case(id:str,data:CaseCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    c=authorized_case(db,user,id);roles(user,"ADMIN","INVESTIGATOR")
    if user.role!="ADMIN" and c.created_by!=user.id: raise HTTPException(403,"Only the case owner can update assignments")
    before=record(c)
    for k,v in data.model_dump(exclude={"member_ids"}).items(): setattr(c,k,v)
    members(db,c,data,user);db.add(AuditLog(actor_user_id=user.id,case_id=id,action="CASE_UPDATED",metadata_json={"before":before,"after":data.model_dump()}));db.commit();return record(c)
