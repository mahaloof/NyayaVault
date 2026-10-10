from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from collections import defaultdict,deque
import time
from app.database import get_db
from app.models import User,AuditLog
from app.schemas import Login,UserCreate,UserUpdate
from app.security import current_user,roles,ph,check_password,token
from app.services import user_record
router=APIRouter(prefix="/api")
attempts=defaultdict(deque)
@router.post("/auth/login")
def login(data:Login,request:Request,db:Session=Depends(get_db)):
    ip=request.client.host if request.client else "unknown"
    queue=attempts[ip]; now=time.monotonic()
    while queue and queue[0]<now-60: queue.popleft()
    if len(queue)>=20: raise HTTPException(429,"Too many sign-in attempts; wait one minute")
    queue.append(now)
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not check_password(data.password,user.password_hash): raise HTTPException(401,"Invalid email or password")
    db.add(AuditLog(actor_user_id=user.id,action="LOGIN",metadata_json={"ip":ip}));db.commit()
    return {"access_token":token(user),"token_type":"bearer","user":user_record(user)}
@router.get("/auth/me")
def me(user=Depends(current_user)): return user_record(user)
@router.post("/auth/logout")
def logout(user=Depends(current_user),db:Session=Depends(get_db)):
    user.token_version+=1;db.add(AuditLog(actor_user_id=user.id,action="LOGOUT"));db.commit();return {"message":"Signed out; all existing tokens revoked"}
@router.get("/users")
def users(user=Depends(current_user),db:Session=Depends(get_db)):
    roles(user,"ADMIN")
    return [user_record(u) for u in db.scalars(select(User))]
@router.get("/users/{id}")
def get_user(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    roles(user,"ADMIN");u=db.get(User,id)
    if not u: raise HTTPException(404,"User not found")
    return user_record(u)
@router.post("/users",status_code=201)
def create_user(data:UserCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    roles(user,"ADMIN")
    u=User(email=data.email.lower(),name=data.name,role=data.role,password_hash=ph.hash(data.password));db.add(u)
    db.add(AuditLog(actor_user_id=user.id,action="USER_CREATED",metadata_json={"email":u.email,"role":u.role}));db.commit();return user_record(u)
@router.put("/users/{id}")
def update_user(id:str,data:UserUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    roles(user,"ADMIN")
    if id==user.id: raise HTTPException(409,"Cannot change your own administrator role")
    u=db.get(User,id)
    if not u: raise HTTPException(404,"User not found")
    u.role=data.role;u.token_version+=1;db.add(AuditLog(actor_user_id=user.id,action="USER_ROLE_UPDATED",metadata_json={"user_id":id,"role":data.role}));db.commit();return user_record(u)
