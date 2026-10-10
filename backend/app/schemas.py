from pydantic import BaseModel, Field
from typing import Literal
Role=Literal["ADMIN","INVESTIGATOR","FORENSIC_OFFICER","VIEWER"]
class Login(BaseModel):
    email: str=Field(max_length=254)
    password: str=Field(max_length=200)
class UserCreate(Login):
    name: str=Field(min_length=2,max_length=120)
    role: Role
    password: str=Field(min_length=12,max_length=200)
class UserUpdate(BaseModel):
    role: Role
class CaseCreate(BaseModel):
    case_number: str=Field(min_length=3,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    title: str=Field(min_length=3,max_length=240)
    description: str=Field(default="",max_length=10000)
    department: str=Field(default="Cybercrime",max_length=160)
    priority: Literal["LOW","MEDIUM","HIGH","CRITICAL"]="MEDIUM"
    status: Literal["OPEN","UNDER_INVESTIGATION","CLOSED","ARCHIVED"]="OPEN"
    member_ids: list[str]=Field(default_factory=list,max_length=100)
class Transfer(BaseModel):
    to_custodian_id: str
    reason: str=Field(min_length=5,max_length=2000)
