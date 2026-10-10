"""Read ciphertext and exercise database guards with rolled-back transactions."""
import json,sys,hashlib
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from app.database import SessionLocal,engine
from app.models import Evidence
from app.storage import storage,decrypt
from app.config import settings

def check(evidence_label):
    with SessionLocal() as db:
        e=db.scalar(select(Evidence).where(Evidence.evidence_id==evidence_label))
        if not e: raise RuntimeError('Test evidence missing')
        raw=storage().get(e.stored_filename);plain=decrypt(raw,e.id)
        result={'database':engine.dialect.name,'storage':settings.storage_provider,'ciphertext_bytes':len(raw),'plaintext_bytes':len(plain),'encrypted_object':raw!=plain and plain not in raw,'decrypted_hash_matches':hashlib.sha256(plain).hexdigest()==e.sha256_hash}
        identifier=e.id
    for label,query in [('immutable_fingerprint',"UPDATE evidence SET sha256_hash=:value WHERE id=:id"),('append_only_custody',"UPDATE custody_events SET description=:value WHERE evidence_id=:id")]:
        blocked=False
        with engine.connect() as conn:
            transaction=conn.begin()
            try: conn.execute(text(query),{'value':'0'*64,'id':identifier})
            except DBAPIError: blocked=True
            finally: transaction.rollback()
        result[label]=blocked
    if not all(result[k] for k in ['encrypted_object','decrypted_hash_matches','immutable_fingerprint','append_only_custody']): raise RuntimeError('Deployment check failed: '+json.dumps(result))
    return result
if __name__=='__main__': print(json.dumps(check(sys.argv[1]),indent=2))
