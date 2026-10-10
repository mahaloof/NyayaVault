'use strict';
const {Contract}=require('fabric-contract-api');
class EvidenceContract extends Contract {
  async RecordCustodyEvent(ctx,payload){
    if(!['Org1MSP','Org2MSP'].includes(ctx.clientIdentity.getMSPID()))throw new Error('Organization not authorized');
    const proof=JSON.parse(payload);
    for(const field of ['eventId','evidenceId','caseId','sha256Hash','action','actor','timestamp','applicationEventHash']){
      if(typeof proof[field]!=='string'||!proof[field])throw new Error('Missing field: '+field);
    }
    if(!/^[a-f0-9]{64}$/.test(proof.sha256Hash)||!/^[a-f0-9]{64}$/.test(proof.applicationEventHash))throw new Error('Invalid fingerprint');
    const key=ctx.stub.createCompositeKey('evidence',[proof.evidenceId]);
    const eventKey=ctx.stub.createCompositeKey('event',[proof.evidenceId,proof.eventId]);
    if((await ctx.stub.getState(eventKey)).length) return (await ctx.stub.getState(eventKey)).toString();
    const existing=await ctx.stub.getState(key);
    if(existing.length){
      const original=JSON.parse(existing.toString());
      if(original.sha256Hash!==proof.sha256Hash||original.caseId!==proof.caseId)throw new Error('Original proof is immutable');
      if(original.applicationEventHash!==proof.previousEventHash)throw new Error('Broken custody chain: submit missing events first');
      if(proof.action==='EVIDENCE_UPLOADED')throw new Error('Evidence already registered');
    }else if(proof.action!=='EVIDENCE_UPLOADED'||proof.previousEventHash)throw new Error('Register evidence first');
    // Application actor is an attested reference; Fabric signer is recorded separately.
    const record={...proof,fabricIdentity:ctx.clientIdentity.getID(),txId:ctx.stub.getTxID()};
    const encoded=Buffer.from(JSON.stringify(record));
    await ctx.stub.putState(key,encoded);await ctx.stub.putState(eventKey,encoded);
    return JSON.stringify(record);
  }
  async RegisterEvidence(ctx,p){if(JSON.parse(p).action!=='EVIDENCE_UPLOADED')throw new Error('Incorrect action');return this.RecordCustodyEvent(ctx,p)}
  async TransferCustody(ctx,p){if(JSON.parse(p).action!=='CUSTODY_TRANSFERRED')throw new Error('Incorrect action');return this.RecordCustodyEvent(ctx,p)}
  async RecordVerification(ctx,p){if(!['INTEGRITY_VERIFIED','INTEGRITY_FAILED'].includes(JSON.parse(p).action))throw new Error('Incorrect action');return this.RecordCustodyEvent(ctx,p)}
  async GetEvidenceProof(ctx,id){const value=await ctx.stub.getState(ctx.stub.createCompositeKey('evidence',[id]));if(!value.length)throw new Error('Not found');return value.toString()}
  async GetEvidenceHistory(ctx,id){
    const iterator=await ctx.stub.getHistoryForKey(ctx.stub.createCompositeKey('evidence',[id]));const events=[];
    try{while(true){const item=await iterator.next();if(item.value?.value?.length)events.push(JSON.parse(item.value.value.toString()));if(item.done)break}}finally{await iterator.close()}
    return JSON.stringify(events);
  }
  async Health(){return 'nyayavault'}
}
module.exports.contracts=[EvidenceContract];
module.exports.EvidenceContract=EvidenceContract;
