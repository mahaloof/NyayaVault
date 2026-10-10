import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, JSON, Integer, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    email: Mapped[str]=mapped_column(String(254),unique=True,index=True)
    name: Mapped[str]=mapped_column(String(120))
    password_hash: Mapped[str]=mapped_column(Text)
    role: Mapped[str]=mapped_column(String(32))
    token_version: Mapped[int]=mapped_column(default=0)
class Case(Base):
    __tablename__="cases"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    case_number: Mapped[str]=mapped_column(String(80),unique=True,index=True)
    title: Mapped[str]=mapped_column(String(240))
    description: Mapped[str]=mapped_column(Text,default="")
    department: Mapped[str]=mapped_column(String(160),default="Cybercrime")
    status: Mapped[str]=mapped_column(String(32),default="OPEN")
    priority: Mapped[str]=mapped_column(String(20),default="MEDIUM")
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str]=mapped_column(String(40),default=now,index=True)
class CaseMember(Base):
    __tablename__="case_members"
    case_id: Mapped[str]=mapped_column(ForeignKey("cases.id"),primary_key=True)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),primary_key=True)
class Evidence(Base):
    __tablename__="evidence"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    evidence_id: Mapped[str]=mapped_column(String(80),unique=True,index=True)
    case_id: Mapped[str]=mapped_column(ForeignKey("cases.id"),index=True)
    original_filename: Mapped[str]=mapped_column(String(255))
    stored_filename: Mapped[str]=mapped_column(String(80),unique=True)
    mime_type: Mapped[str]=mapped_column(String(120))
    file_size: Mapped[int]=mapped_column(Integer)
    evidence_type: Mapped[str]=mapped_column(String(80))
    description: Mapped[str]=mapped_column(Text,default="")
    source: Mapped[str]=mapped_column(String(300),default="")
    collection_location: Mapped[str]=mapped_column(String(300),default="")
    collected_at: Mapped[str]=mapped_column(String(40),default="")
    sha256_hash: Mapped[str]=mapped_column(String(64),index=True)
    encryption_metadata: Mapped[dict]=mapped_column(JSON,default=dict)
    uploaded_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    current_custodian_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    status: Mapped[str]=mapped_column(String(32),default="REGISTERED")
    integrity_status: Mapped[str]=mapped_column(String(32),default="UNVERIFIED")
    ledger_head: Mapped[str]=mapped_column(String(64),default="")
    ledger_seq: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[str]=mapped_column(String(40),default=now,index=True)
    timings: Mapped[dict]=mapped_column(JSON,default=dict)
class Tag(Base):
    __tablename__="tags"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name: Mapped[str]=mapped_column(String(80),unique=True)
class EvidenceTag(Base):
    __tablename__="evidence_tags"
    evidence_id: Mapped[str]=mapped_column(ForeignKey("evidence.id"),primary_key=True)
    tag_id: Mapped[str]=mapped_column(ForeignKey("tags.id"),primary_key=True)
class CustodyEvent(Base):
    __tablename__="custody_events"
    __table_args__=(UniqueConstraint("evidence_id","sequence"),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    evidence_id: Mapped[str]=mapped_column(ForeignKey("evidence.id"),index=True)
    case_id: Mapped[str]=mapped_column(ForeignKey("cases.id"),index=True)
    sequence: Mapped[int]=mapped_column(Integer)
    event_type: Mapped[str]=mapped_column(String(60),index=True)
    actor_user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str]=mapped_column(String(32))
    timestamp: Mapped[str]=mapped_column(String(40),default=now,index=True)
    from_custodian_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    to_custodian_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    description: Mapped[str]=mapped_column(Text)
    evidence_hash: Mapped[str]=mapped_column(String(64))
    previous_event_hash: Mapped[str]=mapped_column(String(64))
    event_hash: Mapped[str]=mapped_column(String(64))
    metadata_json: Mapped[dict]=mapped_column(JSON,default=dict)
class VerificationLog(Base):
    __tablename__="verification_logs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    evidence_id: Mapped[str]=mapped_column(ForeignKey("evidence.id"),index=True)
    actor_user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    trusted_hash: Mapped[str]=mapped_column(String(64))
    calculated_hash: Mapped[str]=mapped_column(String(64))
    result: Mapped[str]=mapped_column(String(32))
    timestamp: Mapped[str]=mapped_column(String(40),default=now)
    elapsed_ms: Mapped[float]=mapped_column(Float)
class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    actor_user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    action: Mapped[str]=mapped_column(String(80))
    case_id: Mapped[str|None]=mapped_column(ForeignKey("cases.id"),nullable=True)
    evidence_id: Mapped[str|None]=mapped_column(ForeignKey("evidence.id"),nullable=True)
    timestamp: Mapped[str]=mapped_column(String(40),default=now,index=True)
    metadata_json: Mapped[dict]=mapped_column(JSON,default=dict)
class BlockchainTransaction(Base):
    __tablename__="blockchain_transactions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    event_id: Mapped[str]=mapped_column(ForeignKey("custody_events.id"),unique=True)
    status: Mapped[str]=mapped_column(String(32))
    tx_id: Mapped[str|None]=mapped_column(String(128),nullable=True)
    error: Mapped[str|None]=mapped_column(Text,nullable=True)
    elapsed_ms: Mapped[float]=mapped_column(Float,default=0)
class OCRDocument(Base):
    __tablename__="ocr_documents"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    evidence_id: Mapped[str]=mapped_column(ForeignKey("evidence.id"),unique=True)
    text: Mapped[str]=mapped_column(Text)
    created_at: Mapped[str]=mapped_column(String(40),default=now)
