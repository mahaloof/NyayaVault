#!/usr/bin/env python3
"""Consistent Docker-only transfer of NyayaVault data. Never resets a source ledger."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, tarfile, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

TAR_IMAGE='alpine:3.22'
SECRETS=('POSTGRES_PASSWORD','MINIO_ACCESS_KEY','MINIO_SECRET_KEY','JWT_SECRET','EVIDENCE_MASTER_KEY','FABRIC_GATEWAY_SECRET')
CORE_VOLUMES={'minio':'minio_data','peer-org1':'fabric_peer_org1','peer-org2':'fabric_peer_org2','orderer':'fabric_orderer'}

def command(*args, input=None, stdout=subprocess.PIPE):
    r=subprocess.run(['docker',*args],input=input,stdout=stdout,stderr=subprocess.PIPE,check=False)
    if r.returncode:
        # Docker error output may contain env values; don't echo arguments/secrets.
        raise RuntimeError(f'Docker operation {args[0]} failed: '+r.stderr.decode(errors='replace')[-800:])
    return r.stdout

def inspect(name): return json.loads(command('inspect',name))[0]
def backend_image_reference(container):
    # Classic Docker accepts the container's config digest as an image ID.
    # Desktop's containerd store may expose only the OCI index/manifest ID.
    if subprocess.run(['docker','image','inspect',container['Image']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        return container['Image']
    candidate=json.loads(command('image','inspect',container['Config']['Image']))[0]['Id']
    probe=command('create','--network','none','--entrypoint','python',candidate,'-c','pass').decode().strip()
    try:
        if inspect(probe)['Image']!=container['Image']:
            raise RuntimeError('The source backend image was replaced with different code since startup. Rerun the source start script while retaining data, then export again.')
    finally:
        command('rm',probe)
    return candidate
def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def volume_exists(name): return subprocess.run(['docker','volume','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
def volume_empty(name):
    if not volume_exists(name): return True
    return subprocess.run(['docker','run','--rm','--network','none','-v',name+':/data:ro',TAR_IMAGE,'sh','-c','test -z "$(ls -A /data)"'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def dump_volume(name,path):
    with path.open('wb') as out: command('run','--rm','--network','none','-v',name+':/data:ro',TAR_IMAGE,'tar','-czf','-','-C','/data','.',stdout=out)
    path.chmod(0o600)
def restore_volume(name,path):
    command('volume','create',name)
    with path.open('rb') as inp:
        r=subprocess.run(['docker','run','--rm','-i','--network','none','-v',name+':/data',TAR_IMAGE,'tar','-xzf','-','-C','/data'],stdin=inp,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    if r.returncode: raise RuntimeError('Volume extraction failed; target is incomplete and must not be started.')

def mount(container,destination):
    rows=[m for m in container['Mounts'] if m['Destination']==destination and m['Type']=='volume']
    if len(rows)!=1: raise RuntimeError('Expected exactly one data volume at '+destination)
    return rows[0]['Name']

def portable_env(source):
    values={}
    for line in source.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1); values[key.strip()]=value.strip().strip('"').strip("'")
    if any(not values.get(k) for k in SECRETS): raise RuntimeError('Source configuration is missing a required key; no new key will be generated.')
    selected={k:values[k] for k in SECRETS}
    # Keep the assistant configuration on both export and restore without
    # copying source-machine paths into the portable deployment.
    for key in ('AI_PROVIDER', 'GEMINI_API_KEY', 'AI_MODEL'):
        if key in values:
            selected[key] = values[key]
    selected.update(FRONTEND_PORT=values.get('FRONTEND_PORT','3001'),BACKEND_PORT=values.get('BACKEND_PORT','8001'),MINIO_CONSOLE_PORT=values.get('MINIO_CONSOLE_PORT','9001'))
    return selected

def snapshot(args):
    from portable_verify import SNAPSHOT
    root=args.project_root.resolve(); out=args.output.resolve()
    source='nyayavault' if args.source=='legacy' else args.project_name
    names={'postgres':source+'-postgres-1','minio':source+'-minio-1','backend':source+'-backend-1','frontend':source+'-frontend-1','fabric-gateway':source+'-fabric-gateway-1'}
    names.update({'peer-org1':'peer0.org1.example.com','peer-org2':'peer0.org2.example.com','orderer':'orderer.example.com'} if args.source=='legacy' else {s:source+'-'+s+'-1' for s in ('peer-org1','peer-org2','orderer')})
    containers={s:inspect(n) for s,n in names.items()}
    if not all(c['State']['Running'] for c in containers.values()): raise RuntimeError('Start all source services before exporting.')
    backend_image=backend_image_reference(containers['backend'])
    out.mkdir(parents=True,exist_ok=False); out.chmod(0o700)
    env=portable_env(root/('.env' if args.source=='legacy' else '.env.portable'))
    (out/'portable.env').write_text(''.join(k+'='+v+'\n' for k,v in env.items())); (out/'portable.env').chmod(0o600)
    # Keep the full original config privately, including legacy flags, for recovery.
    shutil.copy2(root/('.env' if args.source=='legacy' else '.env.portable'),out/'source.env'); (out/'source.env').chmod(0o600)
    running=[c['Id'] for c in containers.values() if c['State']['Running']]
    devs=[]
    if args.source=='legacy':
        for cid in command('ps','-q').decode().split():
            c=inspect(cid)
            if c['Name'].startswith(('/dev-peer0.org1.example.com-','/dev-peer0.org2.example.com-')): devs.append(c['Id'])
    manifest={'format':'nyayavault-transfer-v1','created_at':datetime.now(timezone.utc).isoformat(),'source':args.source,'channel':'nyayachannel','postgres_major':17,'fabric_version':'2.5.16','volumes':[],'files':{},'complete':False}
    try:
        print('Pausing the source application for a consistent copy...',flush=True)
        command('stop',names['frontend'],names['backend'])
        backend=containers['backend']
        network=next(n for n in backend['NetworkSettings']['Networks'] if n.endswith('_default'))
        run=['run','--rm','-i','--network',network]
        for entry in backend['Config']['Env']: run.extend(['-e',entry])
        # Use the exact running backend image, never a mutable tag which
        # could contain a different version after a build.
        run.extend([backend_image,'python','-c',SNAPSHOT])
        baseline=json.loads(command(*run))
        if not baseline['passed']: raise RuntimeError('Source proofs/storage did not pass verification. Export stopped.')
        (out/'baseline.json').write_text(json.dumps(baseline,indent=2)+'\n'); (out/'baseline.json').chmod(0o600)
        with (out/'postgres.dump').open('wb') as f: command('exec',names['postgres'],'pg_dump','-U','vault','-d','nyayavault','-Fc',stdout=f)
        (out/'postgres.dump').chmod(0o600)
        command('stop',*[names[s] for s in names if s not in ('frontend','backend')],*devs)
        for service,c in containers.items():
            if service not in ('minio','peer-org1','peer-org2','orderer'): continue
            for index,m in enumerate(c['Mounts']):
                if m['Type']!='volume': continue
                dest=m['Destination']
                portable=CORE_VOLUMES[service] if dest in ('/data','/var/hyperledger/production','/var/hyperledger/production/orderer') else None
                filename=f'{service}-{index}.tgz'
                dump_volume(m['Name'],out/filename)
                manifest['volumes'].append({'service':service,'source_volume':m['Name'],'destination':dest,'file':filename,'portable_volume':portable})
        if args.source=='legacy':
            organizations=root/'blockchain/runtime/fabric-samples/test-network/organizations'
            identity=root/'blockchain/runtime/gateway-identity'
            with tarfile.open(out/'fabric-crypto.tgz','w:gz') as tar:
                tar.add(organizations,arcname='organizations'); tar.add(identity,arcname='gateway-identity')
                marker=json.dumps({'channel':'nyayachannel','source':'legacy','original_chaincode_version':'1.0','note':'Preserve all old proofs; deploy unchanged contract as CCAAS on copied network.'}).encode()
                import io
                info=tarfile.TarInfo('artifacts/imported-ledger.json');info.size=len(marker);info.mode=0o600
                tar.addfile(info,io.BytesIO(marker))
        else:
            crypto=mount(containers['peer-org1'],'/runtime')
            dump_volume(crypto,out/'fabric-crypto.tgz')
        # Preserve host configs/package as recovery material; do not use Mac binaries on Windows.
        if args.source=='legacy':
            net=root/'blockchain/runtime/fabric-samples/test-network'
            with tarfile.open(out/'legacy-fabric-recovery.tgz','w:gz') as tar:
                for name in ('configtx','compose/docker/peercfg','channel-artifacts','nyayavault.tar.gz'):
                    if (net/name).exists(): tar.add(net/name,arcname=name)
        for path in out.iterdir():
            if path.is_file(): manifest['files'][path.name]=checksum(path)
        manifest.update(complete=True,counts=baseline['counts'],source_restarted=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n'); (out/'manifest.json').chmod(0o600)
        print('Snapshot complete. Encrypted evidence, keys, database and original Fabric ledgers are included.',flush=True)
    finally:
        # Restore precisely the services that were running; no source volume is changed/deleted.
        # Legacy peers remove/recreate their managed chaincode containers. Those
        # transient container IDs are not restartable and are not data stores.
        command('start',*[containers[s]['Id'] for s in names if s not in ('frontend','backend')])
        deadline=time.monotonic()+90
        while inspect(names['postgres'])['State'].get('Health',{}).get('Status')!='healthy':
            if time.monotonic()>deadline: raise RuntimeError('Source database restart timed out. Start the original deployment manually.')
            time.sleep(1)
        command('start',containers['backend']['Id'],containers['frontend']['Id'])
        if manifest['complete']:
            manifest['source_restarted']=True
            (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            (out/'manifest.json').chmod(0o600)


def restore(args):
    root=args.project_root.resolve(); source=args.input.resolve()
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest.get('format')!='nyayavault-transfer-v1' or manifest.get('complete') is not True: raise RuntimeError('Incomplete or unsupported snapshot.')
    for filename,expected in manifest['files'].items():
        if Path(filename).name!=filename or checksum(source/filename)!=expected: raise RuntimeError('Snapshot checksum mismatch: '+filename)
    project=args.project_name
    # Refuse restore into any existing target deployment or populated data volume.
    # Compose-built helper images may inherit project/service labels even when
    # launched with plain docker run. Ignore only this helper's own container.
    hostname=os.environ.get('HOSTNAME','')
    ids=[cid for cid in command('ps','-aq','--filter','label=com.docker.compose.project='+project).decode().split() if not (hostname and inspect(cid)['Id'].startswith(hostname))]
    if ids: raise RuntimeError('Target project already has containers. Restore to an unused project; no existing data will be overwritten.')
    volumes=['postgres_data','minio_data','fabric_crypto','fabric_orderer','fabric_peer_org1','fabric_peer_org2']
    for suffix in volumes:
        name=project+'_'+suffix
        if not volume_empty(name): raise RuntimeError('Target data volume is not empty: '+name)
    env=portable_env(source/'portable.env')
    for key,value in [('FRONTEND_PORT',args.frontend_port),('BACKEND_PORT',args.backend_port),('MINIO_CONSOLE_PORT',args.minio_port)]:
        if value is not None: env[key]=str(value)
    temp=root/'.env.portable.restoring'
    temp.write_text(''.join(k+'='+v+'\n' for k,v in env.items()));temp.chmod(0o600)
    # Every integrity/precondition check happens before target writes.
    for item in manifest['volumes']:
        if item['portable_volume']: restore_volume(project+'_'+item['portable_volume'],source/item['file'])
    restore_volume(project+'_fabric_crypto',source/'fabric-crypto.tgz')
    command('volume','create',project+'_postgres_data')
    pg=project+'-restore-postgres'
    command('run','-d','--name',pg,'--network','none','-e','POSTGRES_DB=nyayavault','-e','POSTGRES_USER=vault','-e','POSTGRES_PASSWORD='+env['POSTGRES_PASSWORD'],'-v',project+'_postgres_data:/var/lib/postgresql/data','postgres:17-alpine')
    try:
        deadline=time.monotonic()+90
        while True:
            ready=subprocess.run(['docker','exec',pg,'pg_isready','-U','vault','-d','nyayavault'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if ready.returncode==0: break
            if time.monotonic()>deadline: raise RuntimeError('Restore database did not become ready.')
            time.sleep(1)
        with (source/'postgres.dump').open('rb') as inp:
            result=subprocess.run(['docker','exec','-i',pg,'pg_restore','-U','vault','-d','nyayavault','--exit-on-error','--no-owner'],stdin=inp,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        if result.returncode: raise RuntimeError('PostgreSQL restore failed. Target is incomplete; do not start it.')
    finally:
        command('stop',pg);command('rm',pg)
    os.replace(temp,root/'.env.portable')
    marker_volume=project+'_portable_tools_data'
    command('volume','create',marker_volume)
    command('run','--rm','-i','--network','none','-v',marker_volume+':/data',TAR_IMAGE,'sh','-c','cat > /data/portable-demo-complete.json',input=json.dumps({'imported':True,'source_snapshot':manifest['created_at'],'demo_reseed':False}).encode())
    print('Restore complete. Start the portable project without reloading demo data, then verify against this snapshot.',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,default=Path('/project'))
    p.add_argument('--project-name',default='nyayavault-portable')
    sub=p.add_subparsers(dest='action',required=True)
    e=sub.add_parser('export');e.add_argument('--source',choices=('legacy','portable'),default='portable');e.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('restore');r.add_argument('--input',type=Path,required=True)
    for n in ('frontend','backend','minio'): r.add_argument('--'+n+'-port',type=int)
    args=p.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,62}',args.project_name): p.error('Use a lowercase Docker project name.')
    if args.action=='restore':
        for name in ('frontend_port','backend_port','minio_port'):
            value=getattr(args,name)
            if value is not None and not 1024<=value<=65535: p.error('Ports must be between 1024 and 65535.')
    if args.action=='export': snapshot(args)
    else: restore(args)
if __name__=='__main__':
    try:
        main()
    except RuntimeError as exc:
        raise SystemExit('NyayaVault transfer: '+str(exc)) from None
