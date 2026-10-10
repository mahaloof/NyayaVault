"""Operator recovery: replay incomplete proofs in evidence-chain order."""
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Evidence,CustodyEvent,BlockchainTransaction
from app.ledger import submit_pending
from app.config import settings
if __name__=='__main__':
    if settings.blockchain_provider!='fabric': raise SystemExit('Set BLOCKCHAIN_PROVIDER=fabric first')
    with SessionLocal() as db:
        for e in db.scalars(select(Evidence).order_by(Evidence.created_at)):
            for event in db.scalars(select(CustodyEvent).where(CustodyEvent.evidence_id==e.id).order_by(CustodyEvent.sequence)):
                tx=db.scalar(select(BlockchainTransaction).where(BlockchainTransaction.event_id==event.id))
                if tx.status=='COMMITTED': continue
                tx.status='PENDING';db.commit();submit_pending(db,event)
                print(e.evidence_id,event.sequence,tx.status,tx.tx_id or '')
                if tx.status!='COMMITTED': break
