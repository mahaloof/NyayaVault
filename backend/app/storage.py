from pathlib import Path
import io,os,base64,secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings
class LocalStorage:
    def __init__(self):
        self.root=Path(settings.storage_path); self.root.mkdir(parents=True,exist_ok=True)
    def put(self,key,data):
        with (self.root/key).open("xb") as f:
            os.chmod(self.root/key,0o600);f.write(data);f.flush();os.fsync(f.fileno())
    def get(self,key): return (self.root/key).read_bytes()
    def delete(self,key): (self.root/key).unlink(missing_ok=True)
class MinioStorage:
    def __init__(self):
        from minio import Minio
        self.client=Minio(settings.minio_endpoint,access_key=settings.minio_access_key,secret_key=settings.minio_secret_key,secure=settings.minio_secure)
        if not self.client.bucket_exists(settings.minio_bucket): self.client.make_bucket(settings.minio_bucket)
    def put(self,key,data): self.client.put_object(settings.minio_bucket,key,io.BytesIO(data),len(data),content_type="application/octet-stream")
    def get(self,key):
        response=self.client.get_object(settings.minio_bucket,key)
        try: return response.read()
        finally: response.close();response.release_conn()
    def delete(self,key): self.client.remove_object(settings.minio_bucket,key)
def storage():
    if settings.storage_provider=="local": return LocalStorage()
    if settings.storage_provider=="minio": return MinioStorage()
    raise RuntimeError("Unknown storage provider")
def encrypt(data,evidence_id):
    nonce=secrets.token_bytes(12)
    return nonce+AESGCM(base64.b64decode(settings.evidence_master_key)).encrypt(nonce,data,evidence_id.encode())
def decrypt(data,evidence_id):
    return AESGCM(base64.b64decode(settings.evidence_master_key)).decrypt(data[:12],data[12:],evidence_id.encode())
