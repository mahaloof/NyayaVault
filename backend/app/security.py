from datetime import datetime,timedelta,timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
ph=PasswordHasher()
bearer=HTTPBearer(auto_error=False)
def check_password(raw,hashed):
    try: return ph.verify(hashed,raw)
    except VerificationError: return False
def token(user):
    return jwt.encode({"sub":user.id,"ver":user.token_version,"exp":datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expiry_minutes)},settings.jwt_secret,algorithm="HS256")
def current_user(auth: HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    try:
        if not auth: raise ValueError()
        data=jwt.decode(auth.credentials,settings.jwt_secret,algorithms=["HS256"],options={"require":["exp","sub","ver"]})
        user=db.get(User,data["sub"])
        if not user or user.token_version!=data["ver"]: raise ValueError()
        return user
    except (jwt.InvalidTokenError,ValueError,KeyError): raise HTTPException(401,"Please sign in again")
def roles(user,*allowed):
    if user.role not in allowed: raise HTTPException(403,"Your role cannot perform this action")
