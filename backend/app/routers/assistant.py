import hashlib
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from cryptography.exceptions import InvalidTag
from app import assistant, document_text
from app.config import settings
from app.database import get_db
from app.models import Evidence, AuditLog
from app.security import current_user, roles
from app.services import authorized_case
from app.storage import storage, decrypt

router = APIRouter(prefix="/api/assistant", tags=["Case assistant"])

class Ask(BaseModel):
    case_id: str = Field(min_length=1, max_length=36)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)
    question: str = Field(default="", max_length=2000)
    mode: Literal["question", "summary"] = "question"
    confirm_demo_external_processing: bool = False
    force_ocr: bool = False

@router.get("/status")
def status(user=Depends(current_user)):
    roles(user, "ADMIN", "INVESTIGATOR", "FORENSIC_OFFICER")
    enabled = settings.ai_provider == "gemini" and bool(settings.gemini_api_key.get_secret_value())
    return {"enabled": enabled, "provider": "Google Gemini", "model": settings.ai_model,
            "message": "Ready for fictional demo evidence" if enabled else "Configure AI_PROVIDER=gemini and GEMINI_API_KEY on the backend",
            "formats": list(document_text.FORMATS), "max_files": 4,
            "max_file_bytes": assistant.MAX_BYTES, "max_excerpt_characters": assistant.MAX_CHARS}

@router.post("/ask")
def ask(data: Ask, user=Depends(current_user), db: Session=Depends(get_db)):
    roles(user, "ADMIN", "INVESTIGATOR", "FORENSIC_OFFICER")
    authorized_case(db, user, data.case_id)
    ids = list(dict.fromkeys(data.evidence_ids))
    evidence = list(db.scalars(select(Evidence).where(Evidence.id.in_(ids), Evidence.case_id == data.case_id).order_by(Evidence.evidence_id)))
    if len(evidence) != len(ids):
        raise HTTPException(404, "Selected evidence not found in this authorized case")
    if not data.confirm_demo_external_processing:
        raise HTTPException(422, "Confirm that selected evidence is fictional demo data and may be sent to Google")
    if not status(user)["enabled"]:
        raise HTTPException(503, "Gemini is not configured; core evidence features remain available")
    question = "Summarize the supplied evidence excerpts and distinguish allegations from facts." if data.mode == "summary" else data.question.strip()
    if not question:
        raise HTTPException(422, "Enter a question")
    if not assistant.slots.acquire(blocking=False):
        raise HTTPException(429, "The assistant is busy. Try again shortly")
    try:
        since = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        count = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.actor_user_id==user.id, AuditLog.action=="AI_REQUESTED", AuditLog.timestamp>=since))
        if count >= 5:
            raise HTTPException(429, "Limit of five assistant requests per minute reached")
        request_log = AuditLog(actor_user_id=user.id, action="AI_REQUESTED", case_id=data.case_id,
            metadata_json={"actor_role": user.role, "provider": "gemini", "model": settings.ai_model,
                           "evidence_ids": ids, "mode": data.mode, "result": "PREPARING", "demo_consent": True})
        db.add(request_log); db.commit()
        try:
            sources = []
            warnings = []
            for e in evidence:
                if e.file_size > assistant.MAX_BYTES:
                    raise HTTPException(413, "Assistant supports evidence up to 10 MiB per file")
                if e.mime_type not in document_text.FORMATS:
                    raise HTTPException(422, "Selected evidence includes an unsupported format; choose text, PDF, PNG or JPEG")
                try:
                    content = decrypt(storage().get(e.stored_filename), e.id)
                except InvalidTag:
                    raise HTTPException(409, "Evidence authentication failed; assistant access blocked. Run integrity verification")
                except Exception:
                    raise HTTPException(503, "Encrypted evidence storage unavailable")
                if len(content) > assistant.MAX_BYTES:
                    raise HTTPException(413, "Evidence exceeds assistant size limit")
                if hashlib.sha256(content).hexdigest() != e.sha256_hash:
                    raise HTTPException(409, "Evidence fingerprint mismatch; assistant access blocked. Run integrity verification")
                pages, notes = document_text.read_pages(content, e.mime_type, data.force_ocr)
                warnings.extend(f"{e.evidence_id}: {note}" for note in notes)
                readable = [p for p in pages if len(p['text'].strip()) >= 10]
                if not readable:
                    raise HTTPException(422, f"{e.evidence_id}: no readable text. Use a clearer printed scan; handwriting is not reliably supported.")
                # Share the existing per-file disclosure budget across all readable pages.
                budget = assistant.MAX_CHARS // len(readable)
                for page in readable:
                    selected, limited = assistant.excerpt(page['text'], question, data.mode == "summary", limit=budget)
                    limited = limited or len(selected) > budget
                    selected = selected[:budget]
                    sources.append({"source_id": f"S{len(sources)+1}", "evidence_id": e.id,
                        "label": e.evidence_id, "filename": e.original_filename, "sha256": e.sha256_hash,
                        "excerpt": selected, "limited": limited, "page": page['page'],
                        "method": page['method'], "uncertain": page['uncertain']})
            # Commit disclosure audit before the external request; errors cannot erase it.
            db.add(AuditLog(actor_user_id=user.id, action="AI_DISCLOSURE", case_id=data.case_id,
                metadata_json={**request_log.metadata_json, "result": "SENDING", "request_id": request_log.id,
                "source_hashes": [s["sha256"] for s in sources]}))
            db.commit()
            answer = assistant.generate(question, sources)
            assistant.validate_citations(answer, sources)
            db.add(AuditLog(actor_user_id=user.id, action="AI_COMPLETED", case_id=data.case_id,
                metadata_json={"actor_role": user.role, "request_id": request_log.id, "result": "COMPLETED"}))
            db.commit()
            return {"claims": [c.model_dump() for c in answer.claims], "sources": sources,
                "model": settings.ai_model, "answered": bool(answer.claims), "warnings": warnings,
                "notice": "AI-derived assistance, not evidence or a legal finding. Quotes are checked against extracted text (OCR can contain errors); human review is still required. Only selected excerpts were analyzed. PDFs are limited to the first 20 pages."}
        except HTTPException as exc:
            db.add(AuditLog(actor_user_id=user.id, action="AI_FAILED", case_id=data.case_id,
                metadata_json={"actor_role": user.role, "request_id": request_log.id, "result": "FAILED", "error_status": exc.status_code}))
            db.commit()
            raise
    finally:
        assistant.slots.release()
