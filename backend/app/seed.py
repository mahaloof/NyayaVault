from sqlalchemy import select
from app.database import SessionLocal
from app.models import User
from app.security import ph
ACCOUNTS=[("admin","Vault Administrator","ADMIN"),("investigatorA","Investigator A","INVESTIGATOR"),("investigatorB","Investigator B","INVESTIGATOR"),("forensic","Forensic Officer","FORENSIC_OFFICER"),("legal","Legal Reviewer","VIEWER")]
def seed():
    with SessionLocal() as db:
        for email,name,role in ACCOUNTS:
            email=email.lower()+"@nyayavault.local"
            u=db.scalar(select(User).where(User.email==email))
            if not u:
                u=User(email=email,name=name,role=role,password_hash=ph.hash("DemoOnly!2026"));db.add(u);db.flush()
        db.commit()
if __name__=="__main__": seed();print("Demo accounts seeded. Load practical fictional cases with scripts/populate-demo.py.")
