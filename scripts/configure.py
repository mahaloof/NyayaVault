from pathlib import Path
import secrets,base64
root=Path(__file__).resolve().parents[1]
p=root/"backend/.env"
if not p.exists():
    p.write_text("DATABASE_URL=sqlite:///./nyayavault.db\nJWT_SECRET="+secrets.token_urlsafe(48)+"\nEVIDENCE_MASTER_KEY="+base64.b64encode(secrets.token_bytes(32)).decode()+"\nBLOCKCHAIN_PROVIDER=development\n")
    p.chmod(0o600)
    print("Generated local secrets in backend/.env; preserve this file to decrypt stored evidence.")
else: print("Existing secrets preserved.")
