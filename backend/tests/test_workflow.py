import hashlib,uuid,json,time
from pathlib import Path
from sqlalchemy import select,text
from app.database import SessionLocal,engine
from app.models import Evidence,User,CustodyEvent
from app.config import settings
from app.storage import storage,decrypt
from app.blockchain import HyperledgerFabricBlockchainService,DevelopmentLedgerService
ORIGINAL=Path("../sample-data/forensic_report_original.txt").read_bytes()
MODIFIED=Path("../sample-data/forensic_report_modified.txt").read_bytes()
def upload(client,headers):
    case=client.get("/api/cases",headers=headers).json()[0]
    r=client.post("/api/evidence",headers=headers,data={"case_id":case["id"],"evidence_id":"EVD-"+uuid.uuid4().hex[:10],"tags":"device-a, demo"},files={"file":("report.txt",ORIGINAL,"text/plain")})
    assert r.status_code==201,r.text
    return r.json()
def test_valid_login(client,login): assert client.get("/api/auth/me",headers=login()).json()["role"]=="INVESTIGATOR"
def test_invalid_login(client): assert client.post("/api/auth/login",json={"email":"nobody","password":"wrong"}).status_code==401
def test_unauthorized_endpoint(client): assert client.get("/api/evidence").status_code==401
def test_create_case(client,login):
    r=client.post("/api/cases",headers=login(),json={"case_number":"CASE-"+uuid.uuid4().hex[:10],"title":"Test investigation"});assert r.status_code==201
    assert client.get("/api/cases/"+r.json()["id"],headers=login("investigatorB")).status_code==404
def test_upload_hash_encryption_and_download(client,login):
    h=login();e=upload(client,h)
    assert e["sha256_hash"]==hashlib.sha256(ORIGINAL).hexdigest()
    with SessionLocal() as db:
        row=db.get(Evidence,e["id"]);cipher=storage().get(row.stored_filename)
        assert ORIGINAL not in cipher and cipher!=ORIGINAL
        assert decrypt(cipher,row.id)==ORIGINAL
    r=client.get(f"/api/evidence/{e['id']}/download",headers=h);assert r.status_code==200 and r.content==ORIGINAL
    actions=[x["event_type"] for x in client.get(f"/api/evidence/{e['id']}/custody",headers=h).json()["events"]]
    assert actions==["EVIDENCE_UPLOADED","EVIDENCE_DOWNLOADED"]
def test_duplicate_evidence_id(client,login):
    h=login();e=upload(client,h)
    r=client.post("/api/evidence",headers=h,data={"case_id":e["case_id"],"evidence_id":e["evidence_id"]},files={"file":("report.txt",ORIGINAL)})
    assert r.status_code==409

def test_full_acceptance_workflow(client,login):
    a=login();b=login("investigatorB");e=upload(client,a);url=f"/api/evidence/{e['id']}"
    original=client.post(url+"/verify",headers=a,files={"file":("original.txt",ORIGINAL)}).json();assert original["matched"] is True
    with SessionLocal() as db: receiver=db.scalar(select(User).where(User.email=="investigatorb@nyayavault.local")).id
    # Upload helper may pick another test-created case: explicitly assign B as case owner.
    case=client.get("/api/cases/"+e["case_id"],headers=a).json()
    payload={k:case[k] for k in ("case_number","title","description","department","status","priority")};payload["member_ids"]=[u["id"] for u in case["members"]]+[receiver]
    assert client.put("/api/cases/"+e["case_id"],headers=a,json=payload).status_code==200
    transferred=client.post(url+"/transfer",headers=a,json={"to_custodian_id":receiver,"reason":"Forensic examination"});assert transferred.status_code==200,transferred.text
    assert transferred.json()["current_custodian_id"]==receiver
    failed=client.post(url+"/verify",headers=b,files={"file":("modified.txt",MODIFIED)}).json();assert failed["matched"] is False
    assert failed["trusted_hash"]==e["sha256_hash"] and failed["calculated_hash"]!=e["sha256_hash"]
    history=client.get(url+"/custody",headers=b).json();assert history["ledger"]["valid"]
    assert [v["event_type"] for v in history["events"]]==["EVIDENCE_UPLOADED","INTEGRITY_VERIFIED","CUSTODY_TRANSFERRED","INTEGRITY_FAILED"]
    assert len(client.get("/api/audit?evidence_id="+e["id"],headers=b).json())==4
    Path("../docs/acceptance-results.json").write_text(json.dumps({"original":original,"modified":failed,"custody_ledger":history["ledger"],"upload_timings":e["timings"],"dashboard":client.get("/api/dashboard",headers=a).json()},indent=2))
def test_unauthorized_transfer(client,login):
    a=login();e=upload(client,a)
    r=client.post(f"/api/evidence/{e['id']}/transfer",headers=login("legal"),json={"to_custodian_id":e["uploaded_by"],"reason":"Should be forbidden"});assert r.status_code in (403,404)
def test_viewer_cannot_upload_or_download(client,login):
    a=login();e=upload(client,a);h=login("legal")
    assert client.get(f"/api/evidence/{e['id']}/download",headers=h).status_code in (403,404)
    assert client.post("/api/evidence",headers=h,data={"case_id":e["case_id"],"evidence_id":"DENIED"},files={"file":("x.txt",ORIGINAL)}).status_code==403
def test_invalid_format_and_size(client,login):
    h=login();case=client.get("/api/cases",headers=h).json()[0]["id"]
    r=client.post("/api/evidence",headers=h,data={"case_id":case,"evidence_id":"INVALID"},files={"file":("fake.pdf",b"not a PDF")});assert r.status_code==415
    before=settings.max_file_mb;settings.max_file_mb=1
    try:
        r=client.post("/api/evidence",headers=h,data={"case_id":case,"evidence_id":"TOOLARGE"},files={"file":("big.txt",b"x"*(1024*1024+1))});assert r.status_code==413
    finally: settings.max_file_mb=before

def test_stored_verification_and_corruption(client,login):
    h=login();e=upload(client,h);url=f"/api/evidence/{e['id']}"
    assert client.post(url+"/verify",headers=h).json()["matched"]
    with SessionLocal() as db:
        row=db.get(Evidence,e["id"]);p=Path(settings.storage_path)/row.stored_filename;data=bytearray(p.read_bytes());data[-1]^=1;p.write_bytes(data)
    assert client.post(url+"/verify",headers=h).status_code==409
    assert client.get(url,headers=h).json()["integrity_status"]=="INTEGRITY_ALERT"
def test_immutable_fingerprint_and_append_only_events(client,login):
    e=upload(client,login())
    import pytest
    with engine.begin() as conn:
        with pytest.raises(Exception): conn.execute(text("UPDATE evidence SET sha256_hash=:hash WHERE id=:id"),{"hash":"0"*64,"id":e["id"]})
        with pytest.raises(Exception): conn.execute(text("UPDATE custody_events SET description='tampered' WHERE evidence_id=:id"),{"id":e["id"]})
def test_ledger_detects_historical_mutation(client,login):
    from app.ledger import verify_chain
    e=upload(client,login())
    with SessionLocal() as db:
        row=db.get(Evidence,e["id"]);event=db.scalar(select(CustodyEvent).where(CustodyEvent.evidence_id==e["id"]))
        event.description="tampered"
        with db.no_autoflush: assert verify_chain(db,row)["valid"] is False
        db.rollback()
def test_logout_revokes_token(client,login):
    h=login();assert client.post("/api/auth/logout",headers=h).status_code==200
    assert client.get("/api/auth/me",headers=h).status_code==401
def test_blockchain_adapters():
    assert DevelopmentLedgerService().record_event({})["tx_id"] is None
    result=HyperledgerFabricBlockchainService().record_event({"evidenceId":"test"})
    assert result["status"]=="FAILED" and result["tx_id"] is None

def test_assigned_non_custodian_cannot_transfer(client,login):
    a=login();case=next(c for c in client.get('/api/cases',headers=a).json() if c['case_number']=='CASE-TEST-FIXTURE')
    response=client.post('/api/evidence',headers=a,data={'case_id':case['id'],'evidence_id':'EVD-'+uuid.uuid4().hex[:10]},files={'file':('sample.txt',ORIGINAL)})
    assert response.status_code==201
    evidence=response.json()
    r=client.post('/api/evidence/'+evidence['id']+'/transfer',headers=login('investigatorB'),json={'to_custodian_id':evidence['uploaded_by'],'reason':'Unauthorized custody transfer'})
    assert r.status_code==403

def test_user_management_and_case_assignments(client,login):
    h=login('admin');email='test-'+uuid.uuid4().hex[:8]+'@nyayavault.local'
    r=client.post('/api/users',headers=h,json={'email':email,'name':'Test Reviewer','role':'VIEWER','password':'TestPassword!2026'})
    assert r.status_code==201
    assert client.get('/api/users',headers=login()).status_code==403
    r=client.put('/api/users/'+r.json()['id'],headers=h,json={'role':'FORENSIC_OFFICER'})
    assert r.status_code==200 and r.json()['role']=='FORENSIC_OFFICER'

def test_expired_token_rejected(client):
    import jwt
    from datetime import datetime,timedelta,timezone
    token=jwt.encode({'sub':'expired','ver':0,'exp':datetime.now(timezone.utc)-timedelta(seconds=1)},settings.jwt_secret,algorithm='HS256')
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401

def test_missing_file_and_bad_case(client,login):
    h=login();assert client.post('/api/evidence',headers=h,data={'case_id':'missing','evidence_id':'EVD-X'}).status_code==422
    assert client.post('/api/evidence',headers=h,data={'case_id':'missing','evidence_id':'EVD-X'},files={'file':('x.txt',ORIGINAL)}).status_code==404

def test_storage_failure_is_visible(client,login,monkeypatch):
    from app.routers import evidence as routes
    class BrokenStorage:
        def put(self,*args): raise OSError('unavailable')
    monkeypatch.setattr(routes,'storage',lambda:BrokenStorage())
    h=login();case=client.get('/api/cases',headers=h).json()[0]['id']
    r=client.post('/api/evidence',headers=h,data={'case_id':case,'evidence_id':'EVD-'+uuid.uuid4().hex[:10]},files={'file':('x.txt',ORIGINAL)})
    assert r.status_code==503 and r.json()['detail']=='Encrypted storage unavailable'

def test_failed_fabric_submission_is_persisted(client,login,monkeypatch):
    monkeypatch.setattr(settings,'blockchain_provider','fabric')
    h=login();e=upload(client,h)
    assert e['blockchain_transactions'][0]['status']=='FAILED'
    assert e['blockchain_transactions'][0]['tx_id'] is None
    assert client.get('/api/evidence/'+e['id']+'/custody',headers=h).json()['ledger']['valid']

def test_archived_cases_leave_workspace_but_preserve_proofs(client,login):
    a=login();admin=login('admin');other=login('investigatorB')
    c=client.post('/api/cases',headers=a,json={'case_number':'ARCHIVE-'+uuid.uuid4().hex[:8],'title':'Archive visibility regression'}).json()
    e=client.post('/api/evidence',headers=a,data={'case_id':c['id'],'evidence_id':'ARCHIVE-'+uuid.uuid4().hex[:8]},files={'file':('archive.txt',ORIGINAL)}).json()
    before=client.get('/api/evidence/'+e['id']+'/custody',headers=a).json()
    c['status']='ARCHIVED';c['member_ids']=[]
    assert client.put('/api/cases/'+c['id'],headers=a,json=c).status_code==200
    blocked=client.post('/api/evidence',headers=a,data={'case_id':c['id'],'evidence_id':'ARCHIVE-BLOCKED-'+uuid.uuid4().hex[:8]},files={'file':('new.txt',ORIGINAL)})
    assert blocked.status_code==409
    for who in [a,admin]:
        assert c['id'] not in [x['id'] for x in client.get('/api/cases',headers=who).json()]
        assert e['id'] not in [x['id'] for x in client.get('/api/evidence',headers=who).json()]
        assert c['id'] in [x['id'] for x in client.get('/api/cases?include_archived=true',headers=who).json()]
        assert e['id'] in [x['id'] for x in client.get('/api/evidence?include_archived=true',headers=who).json()]
        assert not client.get('/api/audit?evidence_id='+e['id'],headers=who).json()
        assert client.get('/api/audit?include_archived=true&evidence_id='+e['id'],headers=who).json()
        assert e['id'] not in [x['id'] for x in client.get('/api/dashboard',headers=who).json()['recent_evidence']]
    assert c['id'] not in [x['id'] for x in client.get('/api/cases?include_archived=true',headers=other).json()]
    assert client.get('/api/cases/'+c['id'],headers=other).status_code==404
    assert client.get('/api/evidence/'+e['id']+'/custody',headers=a).json()==before
    c['status']='OPEN';assert client.put('/api/cases/'+c['id'],headers=a,json=c).status_code==200
    assert e['id'] in [x['id'] for x in client.get('/api/evidence',headers=a).json()]
