import os,tempfile,base64
from pathlib import Path
import pytest
ROOT=Path(tempfile.mkdtemp(prefix="nyayavault-tests-"))
os.environ["DATABASE_URL"]="sqlite:///"+str(ROOT/"test.db")
os.environ["JWT_SECRET"]="test-only-secret-"*4
os.environ["EVIDENCE_MASTER_KEY"]=base64.b64encode(os.urandom(32)).decode()
os.environ["STORAGE_PATH"]=str(ROOT/"evidence")
os.environ["BLOCKCHAIN_PROVIDER"]="development"
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed
from app.routers.auth import attempts
@pytest.fixture(scope="session",autouse=True)
def setup():
    command.upgrade(Config("alembic.ini"),"head");seed()
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import User,Case,CaseMember
    with SessionLocal() as db:
        users=list(db.scalars(select(User)))
        lead=next(u for u in users if u.email=="investigatora@nyayavault.local")
        case=Case(case_number="CASE-TEST-FIXTURE",title="Isolated workflow test",created_by=lead.id)
        db.add(case);db.flush()
        for user in users: db.add(CaseMember(case_id=case.id,user_id=user.id))
        db.commit()
@pytest.fixture
def client():
    attempts.clear()
    with TestClient(app) as c: yield c
@pytest.fixture
def login(client):
    def go(name="investigatorA"):
        r=client.post("/api/auth/login",json={"email":name+"@nyayavault.local","password":"DemoOnly!2026"})
        assert r.status_code==200,r.text
        return {"Authorization":"Bearer "+r.json()["access_token"]}
    return go
