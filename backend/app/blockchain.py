import httpx,time
from app.config import settings
class DevelopmentLedgerService:
    def record_event(self,proof): return {"status":"DEVELOPMENT","tx_id":None,"error":None,"elapsed_ms":0}
    register_evidence=record_event
    transfer_custody=record_event
    record_verification=record_event
    def get_history(self,evidence_id): return []
    def status(self): return {"provider":"development","connected":False,"label":"Development Tamper-Evident Ledger"}
class HyperledgerFabricBlockchainService:
    def record_event(self,proof):
        start=time.perf_counter()
        try:
            r=httpx.post(settings.fabric_gateway_url+"/events",json=proof,headers={"Authorization":"Bearer "+settings.fabric_gateway_secret},timeout=35)
            r.raise_for_status();tx=r.json()["tx_id"]
            if not tx: raise ValueError("Missing committed transaction ID")
            return {"status":"COMMITTED","tx_id":tx,"error":None,"elapsed_ms":(time.perf_counter()-start)*1000}
        except Exception:
            return {"status":"FAILED","tx_id":None,"error":"Fabric submission unavailable; inspect gateway logs","elapsed_ms":(time.perf_counter()-start)*1000}
    register_evidence=record_event
    transfer_custody=record_event
    record_verification=record_event
    def get_history(self,evidence_id):
        r=httpx.get(settings.fabric_gateway_url+"/history/"+evidence_id,headers={"Authorization":"Bearer "+settings.fabric_gateway_secret},timeout=35);r.raise_for_status();return r.json()
    def status(self):
        try:
            r=httpx.get(settings.fabric_gateway_url+"/health",headers={"Authorization":"Bearer "+settings.fabric_gateway_secret},timeout=7);r.raise_for_status()
            return {"provider":"fabric","connected":True,"label":"Hyperledger Fabric connected"}
        except Exception: return {"provider":"fabric","connected":False,"label":"Blockchain unavailable — Development Tamper-Evident Ledger active"}
def blockchain():
    return HyperledgerFabricBlockchainService() if settings.blockchain_provider=="fabric" else DevelopmentLedgerService()
