from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings
class Base(DeclarativeBase): pass
engine=create_engine(settings.database_url,connect_args={"check_same_thread":False,"timeout":30} if settings.database_url.startswith("sqlite") else {},pool_pre_ping=True)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine,"connect")
    def pragmas(conn,record):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
SessionLocal=sessionmaker(engine,expire_on_commit=False)
def get_db():
    with SessionLocal() as db:
        try: yield db
        except Exception:
            db.rollback()
            raise
