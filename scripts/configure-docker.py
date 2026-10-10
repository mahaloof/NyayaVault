from pathlib import Path
import secrets,base64
p=Path(__file__).resolve().parents[1]/".env"
if p.exists(): raise SystemExit("Existing .env preserved. Edit it explicitly if changes are needed.")
p.write_text("POSTGRES_PASSWORD="+secrets.token_urlsafe(32)+"\nJWT_SECRET="+secrets.token_urlsafe(48)+"\nEVIDENCE_MASTER_KEY="+base64.b64encode(secrets.token_bytes(32)).decode()+"\nMINIO_ACCESS_KEY=vault-development\nMINIO_SECRET_KEY="+secrets.token_urlsafe(32)+"\n")
p.chmod(0o600)
print("Generated Docker demo secrets. Preserve .env with your database and evidence backups.")
