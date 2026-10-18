import hashlib
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app import assistant
from app.models import Evidence, AuditLog, CustodyEvent
from app.database import SessionLocal
from app.config import settings
from pydantic import SecretStr
from app.storage import storage

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, 'ai_provider', 'gemini')
    monkeypatch.setattr(settings, 'gemini_api_key', SecretStr('fake-test-only'))


def prepare(client, login, content=b'The fictional invoice records a payment of INR 45000.'):
    headers=login()
    case=client.post('/api/cases',headers=headers,json={'case_number':'AI-'+uuid.uuid4().hex[:10],'title':'Fictional assistant test'}).json()
    response=client.post('/api/evidence',headers=headers,data={'case_id':case['id'],'evidence_id':'AI-'+uuid.uuid4().hex[:10]},files={'file':('record.txt',content)})
    assert response.status_code==201,response.text
    e=response.json()
    return headers,e,{'case_id':case['id'],'evidence_ids':[e['id']],'question':'What amount is recorded?','confirm_demo_external_processing':True}


def test_disabled_and_viewer_permissions(client,login,monkeypatch):
    monkeypatch.setattr(settings,'ai_provider','disabled')
    h,e,p=prepare(client,login)
    assert client.get('/api/assistant/status',headers=h).json()['enabled'] is False
    assert client.post('/api/assistant/ask',headers=h,json=p).status_code==503
    assert client.get('/api/assistant/status',headers=login('legal')).status_code==403
    assert client.post('/api/assistant/ask',headers=login('legal'),json=p).status_code==403
    assert client.post('/api/assistant/ask',json=p).status_code==401


def test_cross_case_and_consent_block_before_decryption(client,login,configured,monkeypatch):
    h,e,p=prepare(client,login)
    def never(*args): raise AssertionError('No external request allowed')
    monkeypatch.setattr(assistant,'generate',never)
    assert client.post('/api/assistant/ask',headers=login('investigatorB'),json=p).status_code==404
    assert client.post('/api/assistant/ask',headers=h,json={**p,'confirm_demo_external_processing':False}).status_code==422
    other=client.post('/api/cases',headers=h,json={'case_number':'AI-'+uuid.uuid4().hex[:10],'title':'Different case'}).json()
    assert client.post('/api/assistant/ask',headers=h,json={**p,'case_id':other['id']}).status_code==404


def test_cited_answer_preserves_original_and_ledger(client,login,configured,monkeypatch):
    h,e,p=prepare(client,login)
    with SessionLocal() as db:
        row=db.get(Evidence,e['id']);cipher=storage().get(row.stored_filename);head=row.ledger_head
    def fake(question,sources):
        assert len(sources)>1 and '45000' in sources[0]['excerpt']
        return assistant.Answer(claims=[assistant.Claim(text='The record states INR 45000.',citations=[assistant.Citation(source_id='S1',quote=sources[0]['excerpt'])])])
    monkeypatch.setattr(assistant,'generate',fake)
    result=client.post('/api/assistant/ask',headers=h,json=p)
    assert result.status_code==200,result.text
    assert result.json()['answered'] and result.json()['sources'][0]['sha256']==e['sha256_hash']
    with SessionLocal() as db:
        row=db.get(Evidence,e['id'])
        assert storage().get(row.stored_filename)==cipher and row.ledger_head==head
        logs=list(db.scalars(select(AuditLog).where(AuditLog.case_id==e['case_id'],AuditLog.action=='AI_COMPLETED')))
        assert logs[-1].metadata_json['result']=='COMPLETED'
        assert '45000' not in str(logs[-1].metadata_json) and 'question' not in logs[-1].metadata_json


def test_bad_citation_and_empty_answer(client,login,configured,monkeypatch):
    h,e,p=prepare(client,login)
    monkeypatch.setattr(assistant,'generate',lambda *a:assistant.Answer(claims=[assistant.Claim(text='Unsupported',citations=[assistant.Citation(source_id='S99',quote='This is fabricated text')])]))
    assert client.post('/api/assistant/ask',headers=h,json=p).status_code==502
    monkeypatch.setattr(assistant,'generate',lambda *a:assistant.Answer(claims=[]))
    r=client.post('/api/assistant/ask',headers=h,json=p)
    assert r.status_code==200 and not r.json()['answered']


def test_tampered_ciphertext_never_sent(client,login,configured,monkeypatch):
    h,e,p=prepare(client,login)
    with SessionLocal() as db:
        row=db.get(Evidence,e['id']);cipher=storage().get(row.stored_filename)
        (storage().root/row.stored_filename).write_bytes(cipher[:-1]+bytes([cipher[-1]^1]))
    monkeypatch.setattr(assistant,'generate',lambda *a:pytest.fail('Corrupt evidence sent'))
    assert client.post('/api/assistant/ask',headers=h,json=p).status_code==409


def test_excerpt_bounds_and_citation_validation():
    s,limited=assistant.excerpt('A'*10000+' relevant amount '*500,'relevant amount',False)
    assert limited and len(s)<=assistant.MAX_CHARS
    with pytest.raises(HTTPException):
        assistant.validate_citations(assistant.Answer(claims=[assistant.Claim(text='Claim',citations=[assistant.Citation(source_id='S1',quote='not actually present')])]),[{'source_id':'S1','excerpt':'real source'}])


def test_pdf_and_unsupported_formats(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(assistant.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=b''))
    with pytest.raises(HTTPException) as error: assistant.extract(b'%PDF-', 'application/pdf')
    assert error.value.status_code==422
    with pytest.raises(HTTPException): assistant.extract(b'image', 'image/png')
    monkeypatch.setattr(assistant.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=b'PDF selectable text'))
    assert assistant.extract(b'%PDF-', 'application/pdf')=='PDF selectable text'


def test_provider_transport_and_errors(configured,monkeypatch):
    real_client=assistant.httpx.Client
    def handler(request):
        assert request.url.host=='generativelanguage.googleapis.com'
        assert 'fake-test-only' not in str(request.url)
        assert request.headers['x-goog-api-key']=='fake-test-only'
        return assistant.httpx.Response(429,json={'error':'sensitive provider detail'})
    monkeypatch.setattr(assistant.httpx,'Client',lambda **kw:real_client(transport=assistant.httpx.MockTransport(handler),**kw))
    with pytest.raises(HTTPException) as error: assistant.generate('question',[])
    assert error.value.status_code==429 and 'sensitive' not in error.value.detail


def test_provider_valid_response_and_malformed_response(configured,monkeypatch):
    import json
    source={'source_id':'S1','excerpt':'A fictional invoice records INR 45000.'}
    real_client=assistant.httpx.Client
    content={'claims':[{'text':'The invoice records INR 45000.','citations':[{'passage_id':'S1:P1'}]}]}
    response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(content)}]}}]}
    monkeypatch.setattr(assistant.httpx,'Client',lambda **kw:real_client(transport=assistant.httpx.MockTransport(lambda req:assistant.httpx.Response(200,json=response)),**kw))
    assert assistant.generate('amount?',[source]).claims[0].citations[0].source_id=='S1'
    response['candidates'][0]['content']['parts'][0]['text']='not json'
    with pytest.raises(HTTPException) as error: assistant.generate('amount?',[source])
    assert error.value.status_code==502


def test_limit_and_busy_fail_without_provider(client,login,configured,monkeypatch):
    h,e,p=prepare(client,login)
    monkeypatch.setattr(assistant,'generate',lambda *a:pytest.fail('Provider called despite limit'))
    assert client.post('/api/assistant/ask',headers=h,json={**p,'evidence_ids':['x']*5}).status_code==422
    assistant.slots.acquire();assistant.slots.acquire()
    try: assert client.post('/api/assistant/ask',headers=h,json=p).status_code==429
    finally: assistant.slots.release();assistant.slots.release()


def test_summary_prompt_and_large_file(client,login,configured,monkeypatch):
    # A separate actor avoids coupling to the per-user quota in earlier tests.
    def admin_login(): return login('admin')
    h,e,p=prepare(client,admin_login)
    def fake(question,sources):
        assert question.startswith('Summarize the supplied evidence excerpts')
        return assistant.Answer(claims=[])
    monkeypatch.setattr(assistant,'generate',fake)
    assert client.post('/api/assistant/ask',headers=h,json={**p,'mode':'summary','question':''}).status_code==200
    h,e,p=prepare(client,admin_login,b'A'*(assistant.MAX_BYTES+1))
    assert client.post('/api/assistant/ask',headers=h,json=p).status_code==413


def test_per_user_quota(client,login,configured,monkeypatch):
    h,e,p=prepare(client,login)
    monkeypatch.setattr(assistant,'generate',lambda *a:assistant.Answer(claims=[]))
    responses=[client.post('/api/assistant/ask',headers=h,json=p).status_code for _ in range(6)]
    assert responses[-1]==429 and all(code in (200,429) for code in responses)


def test_request_schema_matches_validation_and_scopes_citations(configured,monkeypatch):
    import json
    source={"source_id":"S2","excerpt":"Fictional warehouse stock reconciliation."}
    real_client=assistant.httpx.Client
    def handler(request):
        payload=json.loads(request.content)
        schema=payload["generationConfig"]["responseJsonSchema"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["claims"]["maxItems"]==12
        citation=schema["$defs"]["PassageCitation"]
        assert citation["additionalProperties"] is False
        assert citation["properties"]["passage_id"]["enum"]==["S2:P1"]
        assert set(citation["required"])=={"passage_id"}
        assert "quote" not in citation["properties"]
        return assistant.httpx.Response(200,json={"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps({"claims":[{"text":"Recorded stock reconciliation.","citations":[{"passage_id":"S2:P1"}]}]})}]}}]})
    monkeypatch.setattr(assistant.httpx,"Client",lambda **kw:real_client(transport=assistant.httpx.MockTransport(handler),**kw))
    assert assistant.generate("Summarize",[source]).claims


def test_extra_source_field_still_rejected(configured,monkeypatch):
    # Regression: this is the exact extra field returned for the warehouse case.
    import json
    real_client=assistant.httpx.Client
    claim={"text":"Recorded stock reconciliation.","citations":[{"source_id":"S1","quote":"Fictional warehouse stock reconciliation.","source":"warehouse"}]}
    def handler(request):
        return assistant.httpx.Response(200,json={"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps({"claims":[claim]})}]}}]})
    monkeypatch.setattr(assistant.httpx,"Client",lambda **kw:real_client(transport=assistant.httpx.MockTransport(handler),**kw))
    with pytest.raises(HTTPException) as error:
        assistant.generate("Summarize",[{"source_id":"S1","excerpt":"Fictional warehouse stock reconciliation."}])
    assert error.value.status_code==502


@pytest.mark.parametrize("size", [10, 799, 800, 801, 809, 1601, 6000])
def test_passages_preserve_exact_text_and_bounds(size):
    text = ("warehouse\n" * 600)[:size]
    passages = assistant.evidence_passages([{"source_id":"S1","excerpt":text}])
    assert "".join(p.quote for p in passages.values()) == text
    assert all(10 <= len(p.quote) <= 800 and p.quote in text for p in passages.values())


@pytest.mark.parametrize("reference", ["S1:P99", "S2:P1"])
def test_unknown_passage_rejected(configured, monkeypatch, reference):
    import json
    real_client = assistant.httpx.Client
    content = {"claims":[{"text":"Unsupported", "citations":[{"passage_id":reference}]}]}
    body = {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(content)}]}}]}
    monkeypatch.setattr(assistant.httpx, "Client", lambda **kw:real_client(transport=assistant.httpx.MockTransport(lambda req:assistant.httpx.Response(200,json=body)), **kw))
    with pytest.raises(HTTPException) as error:
        assistant.generate("Summarize", [{"source_id":"S1", "excerpt":"Exact fictional evidence text."}])
    assert error.value.status_code == 502


def test_quotation_is_inserted_by_backend(configured, monkeypatch):
    import json
    source = {"source_id":"S2", "excerpt":"Exact whitespace:  two spaces.\nSecond line — unchanged."}
    real_client = assistant.httpx.Client
    def handler(request):
        payload = json.loads(request.content)
        passages = json.loads(payload["contents"][0]["parts"][0]["text"])["passages"]
        assert passages == [{"passage_id":"S2:P1", "text":source["excerpt"]}]
        content = {"claims":[{"text":"Recorded details.", "citations":[{"passage_id":"S2:P1"}]}]}
        return assistant.httpx.Response(200,json={"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(content)}]}}]})
    monkeypatch.setattr(assistant.httpx, "Client", lambda **kw:real_client(transport=assistant.httpx.MockTransport(handler), **kw))
    citation = assistant.generate("Summarize", [source]).claims[0].citations[0]
    assert citation.source_id == "S2" and citation.quote == source["excerpt"]


def test_case_only_context_and_permissions(client,login,configured,monkeypatch):
    h=login('admin')
    case=client.post('/api/cases',headers=h,json={'case_number':'CTX-'+uuid.uuid4().hex[:10],'title':'Public case study','description':'The case description records a court conviction; this is a source narrative.'}).json()
    captured=[]
    def fake(question,sources):
        captured.extend(sources)
        source=next(s for s in sources if s['label']=='Recorded evidence and custody coverage')
        return assistant.Answer(claims=[assistant.Claim(text='No evidence custody or transfers are recorded.',citations=[assistant.Citation(source_id=source['source_id'],quote=source['excerpt'])])])
    monkeypatch.setattr(assistant,'generate',fake)
    p={'case_id':case['id'],'question':'Who has custody?','confirm_external_processing':True}
    assert client.post('/api/assistant/ask',headers=login('investigatorB'),json=p).status_code==404
    assert client.post('/api/assistant/ask',headers=h,json={**p,'confirm_external_processing':False}).status_code==422
    r=client.post('/api/assistant/ask',headers=h,json=p)
    assert r.status_code==200,r.text
    text=' '.join(s['excerpt'] for s in captured)
    assert case['created_at'] in text and 'court conviction' in text
    assert 'No evidence custodian or evidence transfers' in text
    assert all(s['case_id']==case['id'] and s['kind']=='case_record' for s in captured)


def test_case_context_custodian_events_and_scope(client,login):
    from app.case_context import sources_for_case
    from app.models import Case
    h,e,p=prepare(client,login)
    with SessionLocal() as db:
        sources,warnings=sources_for_case(db,db.get(Case,e['case_id']),'custody',False)
    text=' '.join(s['excerpt'] for s in sources)
    assert e['evidence_id'] in text and 'Investigator A' in text
    assert 'Current recorded custodian' in text and 'Sequence: 1' in text
    assert all(s['case_id']==e['case_id'] for s in sources)
    assert 'Public case study' not in text


def test_transfers_report_sender_recipient_and_reason(client,login):
    from app.case_context import sources_for_case
    from app.models import Case, CaseMember, User
    h,e,p=prepare(client,login)
    with SessionLocal() as db:
        recipient=db.scalar(select(User).where(User.email=='forensic@nyayavault.local'))
        recipient_id=recipient.id
        db.add(CaseMember(case_id=e['case_id'],user_id=recipient_id));db.commit()
    r=client.post('/api/evidence/'+e['id']+'/transfer',headers=h,json={'to_custodian_id':recipient_id,'reason':'Laboratory examination requested'})
    assert r.status_code==200,r.text
    with SessionLocal() as db:
        sources,_=sources_for_case(db,db.get(Case,e['case_id']),'What transfers occurred?',False)
    transfer=next(s for s in sources if 'Event: CUSTODY_TRANSFERRED' in s['excerpt'])
    assert 'From custodian: Investigator A' in transfer['excerpt']
    assert 'Laboratory examination requested' in transfer['excerpt']
    assert 'To custodian: None recorded' not in transfer['excerpt']
    assert 'Recorded blockchain status:' in transfer['excerpt']
