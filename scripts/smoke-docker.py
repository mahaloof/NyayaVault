"""Exercise real HTTP services. Uses fresh, labeled synthetic demo records."""
import json,hashlib,time,uuid,os
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
base=os.environ.get('NYAYAVAULT_TEST_API','http://127.0.0.1:8001/api')
checks=[]
expected_provider=os.environ.get('NYAYAVAULT_TEST_PROVIDER','development')
report_name='fabric-test-results.json' if expected_provider=='fabric' else 'docker-test-results.json'
report_name=os.environ.get('NYAYAVAULT_TEST_REPORT',report_name)
report_path=root/'docs'/report_name
def check(name,condition):
    checks.append({'test':name,'passed':bool(condition)})
    if not condition: raise AssertionError(name)
def login(client,email):
    response=client.post('/auth/login',json={'email':email+'@nyayavault.local','password':'DemoOnly!2026'})
    check('Login '+email,response.status_code==200)
    return {'Authorization':'Bearer '+response.json()['access_token']}
def main():
    started=time.perf_counter()
    with httpx.Client(base_url=base,timeout=60) as c:
        check('Unauthenticated access denied',c.get('/evidence').status_code==401)
        admin=login(c,'admin');a=login(c,'investigatorA');b=login(c,'investigatorB');legal=login(c,'legal')
        users=c.get('/users',headers=admin).json();aid=next(u['id'] for u in users if u['email']=='investigatora@nyayavault.local');bid=next(u['id'] for u in users if u['email']=='investigatorb@nyayavault.local')
        suffix=uuid.uuid4().hex[:8]
        response=c.post('/cases',headers=admin,json={'case_number':'CASE-DOCKER-'+suffix,'title':'Docker acceptance — synthetic investigation','description':'PostgreSQL and MinIO integration test. No real evidence.','member_ids':[aid,bid]})
        check('Create PostgreSQL case with assignments',response.status_code==201);case=response.json()
        original=(root/'sample-data/forensic_report_original.txt').read_bytes();modified=(root/'sample-data/forensic_report_modified.txt').read_bytes()
        response=c.post('/evidence',headers=a,data={'case_id':case['id'],'evidence_id':'EVD-DOCKER-'+suffix,'evidence_type':'Forensic Report','description':'Synthetic Docker integration test','tags':'docker-acceptance, synthetic'},files={'file':('forensic_report_original.txt',original,'text/plain')})
        check('Upload to encrypted object storage',response.status_code==201);e=response.json();url='/evidence/'+e['id']
        check('Correct original SHA-256',e['sha256_hash']==hashlib.sha256(original).hexdigest())
        check('Unassigned user cannot see evidence',c.get(url,headers=legal).status_code==404)
        check('Assigned non-custodian transfer denied',c.post(url+'/transfer',headers=b,json={'to_custodian_id':aid,'reason':'Forbidden transfer check'}).status_code==403)
        verified=c.post(url+'/verify',headers=a,files={'file':('original.txt',original)});check('Original candidate verified',verified.status_code==200 and verified.json()['matched'])
        stored=c.post(url+'/verify',headers=a);check('Stored MinIO ciphertext decrypts and verifies',stored.status_code==200 and stored.json()['matched'])
        transfer=c.post(url+'/transfer',headers=a,json={'to_custodian_id':bid,'reason':'Docker acceptance forensic handoff'});check('Custody moves A to B',transfer.status_code==200 and transfer.json()['current_custodian_id']==bid)
        tampered=c.post(url+'/verify',headers=b,files={'file':('modified.txt',modified)});check('Modified candidate detected',tampered.status_code==200 and not tampered.json()['matched'])
        check('Trusted fingerprint preserved',tampered.json()['trusted_hash']==e['sha256_hash'])
        downloaded=c.get(url+'/download',headers=b);check('Authorized download equals original',downloaded.status_code==200 and downloaded.content==original)
        history=c.get(url+'/custody',headers=b).json();check('Custody chain valid',history['ledger']['valid'])
        actions=[v['event_type'] for v in history['events']];check('All core events recorded',all(v in actions for v in ['EVIDENCE_UPLOADED','INTEGRITY_VERIFIED','CUSTODY_TRANSFERRED','INTEGRITY_FAILED','EVIDENCE_DOWNLOADED']))
        audit=c.get('/audit',headers=b,params={'evidence_id':e['id']});check('Audit records match custody events',audit.status_code==200 and len(audit.json())==len(history['events']))
        dashboard=c.get('/dashboard',headers=b).json();check('Dashboard records actual alert',dashboard['alerts']>=1 and dashboard['detected_mismatches']>=1)
        status=c.get('/blockchain/status',headers=b).json();check('Expected blockchain connection',status['provider']==expected_provider and status['connected']==(expected_provider=='fabric'))
        if expected_provider=='fabric':
            check('Every custody event committed to Fabric',all(ev.get('blockchain',{}).get('status')=='COMMITTED' and len(ev['blockchain'].get('tx_id') or '')==64 for ev in history['events']))
        check('Logout',c.post('/auth/logout',headers=a).status_code==200);check('Logged-out token rejected',c.get('/auth/me',headers=a).status_code==401)
        # Capture workflow results before moving this run's records out of the active workspace.
        result={'api':base,'elapsed_seconds':time.perf_counter()-started,'checks':checks,'evidence':e,'verification':verified.json(),'tampered':tampered.json(),'ledger':history['ledger'],'metrics':dashboard['metrics'],'custody':history,'blockchain':status}
        current=c.get('/cases/'+case['id'],headers=admin)
        check('Read this run\'s test case before archival',current.status_code==200)
        case_before_archive=current.json()
        assignments=[member['id'] for member in case_before_archive['members']]
        archive_payload={key:case_before_archive[key] for key in ('case_number','title','description','department','priority')}
        archive_payload.update(status='ARCHIVED',member_ids=assignments)
        archived=c.put('/cases/'+case['id'],headers=admin,json=archive_payload)
        check('Archive only this run\'s test case',archived.status_code==200 and archived.json().get('id')==case['id'] and archived.json().get('status')=='ARCHIVED')
        after=c.get('/cases/'+case['id'],headers=admin)
        check('Archival preserves case assignments',after.status_code==200 and {member['id'] for member in after.json()['members']}==set(assignments))
        result.update(case=case_before_archive,case_archive={'case_id':case['id'],'case_number':case['case_number'],'status':'ARCHIVED','member_ids':assignments})
        return result
if __name__=='__main__':
    try:
        result=main();report_path.write_text(json.dumps(result,indent=2));print(f"{len(checks)} integration checks passed; report: {report_path}")
    except Exception as exc:
        report_path.write_text(json.dumps({'checks':checks,'error':str(exc)},indent=2));raise
