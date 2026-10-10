"""Read-only whole-ledger/storage verification plus role tests on a fresh synthetic case."""
import json,subprocess,os,tempfile,uuid
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
docker='/Applications/Docker.app/Contents/Resources/bin/docker' if Path('/Applications/Docker.app/Contents/Resources/bin/docker').exists() else 'docker'
checks=[]
def check(name,condition):
    checks.append({'test':name,'passed':bool(condition)})
    if not condition:raise AssertionError(name)
def cmd(args,**kw):return subprocess.check_output(args,cwd=root,text=True,**kw)
backend='''import json,hashlib
from sqlalchemy import select,func
from app.database import SessionLocal
from app.models import Evidence,CustodyEvent,BlockchainTransaction,User,Case
from app.storage import storage,decrypt
from app.ledger import verify_chain
from app.blockchain import blockchain
rows=[]
with SessionLocal() as db:
 for e in db.scalars(select(Evidence)):
  events=list(db.scalars(select(CustodyEvent).where(CustodyEvent.evidence_id==e.id)))
  history=blockchain().get_history(e.evidence_id);by_id={x['eventId']:x for x in history}
  all_match=len(history)==len(events)
  for event in events:
   tx=db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id==event.id));p=by_id.get(event.id,{})
   all_match=all_match and tx is not None and tx.status=='COMMITTED' and tx.tx_id==p.get('txId') and p.get('sha256Hash')==e.sha256_hash and p.get('applicationEventHash')==event.event_hash and p.get('previousEventHash')==event.previous_event_hash
  raw=storage().get(e.stored_filename);plain=decrypt(raw,e.id)
  rows.append({'evidence_id':e.evidence_id,'events':len(events),'chain_valid':verify_chain(db,e)['valid'],'peer_matches':all_match,'ciphertext':raw!=plain and plain not in raw,'stored_original_valid':hashlib.sha256(plain).hexdigest()==e.sha256_hash})
 print(json.dumps({'evidence':rows,'users':db.scalar(select(func.count()).select_from(User)),'cases':db.scalar(select(func.count()).select_from(Case))}))
'''

def main():
    with httpx.Client(base_url=os.environ.get('NYAYAVAULT_TEST_API','http://127.0.0.1:8001/api'),timeout=45) as c:
        def login(name):
            r=c.post('/auth/login',json={'email':name+'@nyayavault.local','password':'DemoOnly!2026'});check(name+' login',r.status_code==200);return {'Authorization':'Bearer '+r.json()['access_token']}
        admin=login('admin');a=login('investigatorA');f=login('forensic');v=login('legal')
        users=c.get('/users',headers=admin).json();uid=lambda email:next(u['id'] for u in users if u['email']==email+'@nyayavault.local')
        case=c.post('/cases',headers=admin,json={'case_number':'CASE-ROLE-'+uuid.uuid4().hex[:8],'title':'Synthetic department permission test','member_ids':[uid('investigatora'),uid('forensic'),uid('legal')]}).json()
        label='EVD-ROLE-'+uuid.uuid4().hex[:8];original=(root/'sample-data/forensic_report_original.txt').read_bytes()
        payload={'case_id':case['id'],'evidence_id':label,'description':'Synthetic forensic/viewer access test'}
        r=c.post('/evidence',headers=a,data=payload,files={'file':('original.txt',original)});check('Investigator uploads assigned evidence',r.status_code==201);e=r.json();url='/evidence/'+e['id']
        check('Forensic role cannot create cases',c.post('/cases',headers=f,json={'case_number':'DENIED-'+uuid.uuid4().hex[:8],'title':'Forbidden'}).status_code==403)
        check('Forensic role cannot manage users',c.get('/users',headers=f).status_code==403)
        check('Assigned viewer reads metadata',c.get(url,headers=v).status_code==200)
        check('Assigned viewer cannot download',c.get(url+'/download',headers=v).status_code==403)
        check('Assigned viewer cannot upload',c.post('/evidence',headers=v,data={**payload,'evidence_id':label+'-DENIED'},files={'file':('x.txt',original)}).status_code==403)
        check('Assigned viewer cannot transfer',c.post(url+'/transfer',headers=v,json={'to_custodian_id':uid('forensic'),'reason':'Forbidden viewer handoff'}).status_code==403)
        r=c.post(url+'/transfer',headers=a,json={'to_custodian_id':uid('forensic'),'reason':'Synthetic police to forensic handoff'});check('Investigator transfers to forensic case member',r.status_code==200 and r.json()['current_custodian_id']==uid('forensic'))
        r=c.post(url+'/verify',headers=f);check('Forensic officer verifies stored original',r.status_code==200 and r.json()['matched'])
        r=c.get(url+'/download',headers=f);check('Forensic officer downloads original',r.status_code==200 and r.content==original)
        check('Previous custodian cannot transfer again',c.post(url+'/transfer',headers=a,json={'to_custodian_id':uid('investigatora'),'reason':'Forbidden old custodian handoff'}).status_code==403)
        r=c.post(url+'/transfer',headers=f,json={'to_custodian_id':uid('investigatora'),'reason':'Synthetic forensic review complete'});check('Forensic custodian transfers back',r.status_code==200)
        history=c.get(url+'/custody',headers=a).json();check('Department workflow commits every event',all(x['blockchain']['status']=='COMMITTED' for x in history['events']))
    inventory=json.loads(cmd([docker,'exec','-i','nyayavault-backend-1','python','-c',backend]));check('Every stored original decrypts and hashes correctly',all(x['stored_original_valid'] and x['ciphertext'] for x in inventory['evidence']));check('Every application custody chain is valid',all(x['chain_valid'] for x in inventory['evidence']));check('Every event and transaction ID matches real Fabric history',all(x['peer_matches'] for x in inventory['evidence']))
    net=root/'blockchain/runtime/fabric-samples/test-network';binary=net.parent/'bin';env=os.environ.copy();env.update(FABRIC_CFG_PATH=str(net.parent/'config'),CORE_PEER_TLS_ENABLED='true')
    peers={}
    for org,port in [('1','7051'),('2','9051')]:
        o=net/f'organizations/peerOrganizations/org{org}.example.com';env.update(CORE_PEER_LOCALMSPID=f'Org{org}MSP',CORE_PEER_ADDRESS='localhost:'+port,CORE_PEER_MSPCONFIGPATH=str(o/f'users/Admin@org{org}.example.com/msp'),CORE_PEER_TLS_ROOTCERT_FILE=str(o/f'peers/peer0.org{org}.example.com/tls/ca.crt'))
        peers['Org'+org]=json.loads(cmd([str(binary/'peer'),'lifecycle','chaincode','querycommitted','-C','nyayachannel','-n','nyayavault','--output','json'],env=env));check('Org'+org+' confirms both organization approvals',peers['Org'+org]['approvals']=={'Org1MSP':True,'Org2MSP':True})
    with tempfile.TemporaryDirectory() as d:
        block=str(Path(d)/'config.block');decoded=str(Path(d)/'config.json')
        cmd([str(binary/'peer'),'channel','fetch','config',block,'-c','nyayachannel','-o','localhost:7050','--ordererTLSHostnameOverride','orderer.example.com','--tls','--cafile',str(net/'organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt')],env=env,stderr=subprocess.DEVNULL)
        cmd([str(binary/'configtxlator'),'proto_decode','--input',block,'--type','common.Block','--output',decoded]);config=json.loads(Path(decoded).read_text())['data']['data'][0]['payload']['data']['config']['channel_group']['groups']['Application']
        check('Channel retains Org1MSP and Org2MSP',sorted(config['groups'])==['Org1MSP','Org2MSP']);check('Endorsement requires majority of two organizations',config['policies']['Endorsement']['policy']['value']=={'rule':'MAJORITY','sub_policy':'Endorsement'})
    # Whole-ledger and network checks must succeed before archiving this run's own case.
    # Keep the report's inventory and custody snapshot from the completed workflow.
    with httpx.Client(base_url=os.environ.get('NYAYAVAULT_TEST_API','http://127.0.0.1:8001/api'),timeout=45) as c:
        current=c.get('/cases/'+case['id'],headers=admin)
        check('Read this run\'s role test case before archival',current.status_code==200)
        case_before_archive=current.json()
        assignments=[member['id'] for member in case_before_archive['members']]
        archive_payload={key:case_before_archive[key] for key in ('case_number','title','description','department','priority')}
        archive_payload.update(status='ARCHIVED',member_ids=assignments)
        archived=c.put('/cases/'+case['id'],headers=admin,json=archive_payload)
        check('Archive only this run\'s role test case',archived.status_code==200 and archived.json().get('id')==case['id'] and archived.json().get('status')=='ARCHIVED')
        after=c.get('/cases/'+case['id'],headers=admin)
        check('Role test archival preserves case assignments',after.status_code==200 and {member['id'] for member in after.json()['members']}==set(assignments))
    return {'checks':checks,'inventory':inventory,'peer_definitions':peers,'role_evidence':label,'role_case':case_before_archive,'custody':history,'case_archive':{'case_id':case['id'],'case_number':case['case_number'],'status':'ARCHIVED','member_ids':assignments}}
if __name__=='__main__':
    try:
        result=main();(root/'docs/live-system-results.json').write_text(json.dumps(result,indent=2));print(str(len(checks))+' live system checks passed.')
    except Exception as exc:
        (root/'docs/live-system-results.json').write_text(json.dumps({'checks':checks,'error':str(exc)},indent=2));raise
