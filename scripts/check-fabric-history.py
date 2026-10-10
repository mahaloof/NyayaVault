"""Query the real peer through its internal gateway; compare with HTTP test records."""
import json, subprocess, uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
report=json.loads((root/'docs/fabric-test-results.json').read_text())
def request(method,path,body=None,authenticated=True):
    code='''const input=JSON.parse(process.argv[1]);const r=await fetch('http://127.0.0.1:4000'+input.path,{method:input.method,headers:{'Content-Type':'application/json',...(input.authenticated?{Authorization:'Bearer '+process.env.FABRIC_GATEWAY_SECRET}:{})},...(input.body?{body:JSON.stringify(input.body)}:{})});console.log(JSON.stringify({status:r.status,body:await r.json().catch(()=>null)}));'''
    args=['bash','scripts/docker.sh','-f','docker-compose.yml','-f','docker-compose.fabric.yml','exec','-T','fabric-gateway','node','--input-type=module','-e',code,json.dumps(dict(method=method,path=path,body=body,authenticated=authenticated))]
    return json.loads(subprocess.check_output(args,cwd=root,text=True))
path='/history/'+report['evidence']['evidence_id']
r=request('GET',path);assert r['status']==200
history=r['body'];events=report['custody']['events'];assert len(history)==len(events)
by_id={item['eventId']:item for item in history}
assert len(by_id)==len(events)
for event in events:
    actual=by_id[event['id']]
    assert actual['eventId']==event['id']
    assert actual['applicationEventHash']==event['event_hash']
    assert actual['sha256Hash']==report['evidence']['sha256_hash']
    assert actual['txId']==event['blockchain']['tx_id']
    assert actual['previousEventHash']==event['previous_event_hash']
proof={k:v for k,v in history[0].items() if k not in ('txId','fabricIdentity')}
replay=request('POST','/events',proof);assert replay['status']==200 and replay['body']['tx_id']==history[0]['txId']
invalid={**proof,'eventId':str(uuid.uuid4()),'action':'INTEGRITY_VERIFIED','sha256Hash':'0'*64,'previousEventHash':by_id[events[-1]['id']]['applicationEventHash']}
assert request('POST','/events',invalid)['status']==503
assert request('GET',path)['body']==history
assert request('GET','/health',authenticated=False)['status']==401
result={'checks':['Peer history matches every application event, original hash, linked hash, and committed transaction ID','Replay returns original transaction ID without adding evidence history','Chaincode rejects replacement of original fingerprint','Gateway rejects unauthenticated requests'],'events':len(history),'history':history}
(root/'docs/fabric-peer-results.json').write_text(json.dumps(result,indent=2))
print(f'4 peer/gateway checks passed; {len(history)} on-chain events match the app.')
