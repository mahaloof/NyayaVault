"""Bounded, case-scoped application records for the assistant; no file decryption."""
import hashlib
from sqlalchemy import select, func
from app.models import User, Evidence, CustodyEvent, BlockchainTransaction
from app import assistant


def sources_for_case(db, case, question, summary, start=1):
    sources, warnings = [], []
    def add(label, text, evidence_id=None, limited=False):
        sources.append(dict(source_id=f'S{start+len(sources)}', evidence_id=evidence_id,
            case_id=case.id, kind='case_record', label=label, filename='Application record',
            sha256=hashlib.sha256(text.encode()).hexdigest(), excerpt=text,
            limited=limited, page=None, method='database', uncertain=False))
    def name(uid):
        user = db.get(User, uid) if uid else None
        return user.name if user else ('Unknown user' if uid else 'None recorded')
    add('Case registration', f'Case: {case.case_number}\nTitle: {case.title}\nRegistered in NyayaVault: {case.created_at}\nCreated by: {name(case.created_by)}\nDepartment: {case.department}\nStatus: {case.status}\nPriority: {case.priority}\nThe app registration date is not the date of the incident. The case creator is not automatically an evidence custodian.')
    description, limited = assistant.excerpt(case.description or 'No case description recorded.', question, summary)
    add('Case description (entered narrative, not independently verified)', description, limited=limited)
    if limited: warnings.append('Only selected parts of the case description were included.')
    total = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.case_id == case.id))
    items = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id).order_by(Evidence.evidence_id).limit(100)))
    events_total = db.scalar(select(func.count()).select_from(CustodyEvent).where(CustodyEvent.case_id == case.id))
    events = list(db.scalars(select(CustodyEvent).where(CustodyEvent.case_id == case.id).order_by(CustodyEvent.timestamp.desc(), CustodyEvent.id).limit(200)))
    add('Recorded evidence and custody coverage', f'Total evidence files registered in this case: {total}. Total custody events recorded in this case: {events_total}. Included {len(items)} evidence records and {len(events)} most recent custody events. Custody refers to individual evidence items, not custody of a suspect. '+('No evidence custodian or evidence transfers are recorded because no evidence has been uploaded.' if not total and not events_total else 'Absence of an event here does not establish what occurred outside the app.'))
    if total > len(items) or events_total > len(events): warnings.append('Record coverage is limited to 100 evidence items and the 200 most recent custody events; this is not the complete history.')
    for e in items:
        add(f'{e.evidence_id} current custody', f'Evidence: {e.evidence_id}\nCurrent recorded custodian: {name(e.current_custodian_id)}\nRegistered in app: {e.created_at}\nStatus: {e.status}\nIntegrity status: {e.integrity_status}', e.id)
    for event in reversed(events):
        e = db.get(Evidence, event.evidence_id)
        if not e or e.case_id != case.id: continue
        tx = db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id == event.id))
        detail, detail_limited = assistant.excerpt(event.description or "No event description recorded.", question, summary, limit=1000)
        if detail_limited: warnings.append(f"{e.evidence_id} event {event.sequence}: event description shortened.")
        add(f'{e.evidence_id} custody event {event.sequence}', f'Evidence: {e.evidence_id}\nEvent: {event.event_type}\nSequence: {event.sequence}\nRecorded at: {event.timestamp}\nActor: {name(event.actor_user_id)}\nFrom custodian: {name(event.from_custodian_id)}\nTo custodian: {name(event.to_custodian_id)}\nEvent description: {detail}\nRecorded blockchain status: {tx.status if tx else "No transaction recorded"}\nTransaction reference: {tx.tx_id if tx else "None"}', e.id)
    return sources, warnings
