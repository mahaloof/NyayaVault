"""Run in the Docker backend to exercise real Poppler and Tesseract."""
import io
import shutil
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont
from app import document_text, assistant
from app.config import settings
from pydantic import SecretStr

pytestmark = pytest.mark.skipif(not shutil.which('tesseract') or not Path('/dev/shm').is_dir(), reason='Requires Docker OCR runtime')

def scan(text):
    image=Image.new('RGB',(1600,1000),'white')
    ImageDraw.Draw(image).text((80,100),text,fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',40))
    return image

def pdf():
    out=io.BytesIO()
    scan('FICTIONAL TRAINING RECORD\nInvoice total 45000.').save(out,format='PDF',save_all=True,append_images=[scan('FICTIONAL TRAINING RECORD\nRecovered stock 24 units.')])
    return out.getvalue()

def test_real_scanned_pdf_and_image():
    before=set(Path('/dev/shm').glob('nyayavault-ocr-*'))
    pages,notes=document_text.read_pages(pdf(),'application/pdf')
    assert [p['page'] for p in pages]==[1,2]
    assert all(p['method']=='ocr' for p in pages)
    assert '45000' in pages[0]['text'] and '24' in pages[1]['text']
    for fmt,mime in [('PNG','image/png'),('JPEG','image/jpeg')]:
        out=io.BytesIO();scan('FICTIONAL INVOICE\nAmount 45000').save(out,format=fmt)
        pages,_=document_text.read_pages(out.getvalue(),mime)
        assert '45000' in pages[0]['text']
    out=io.BytesIO();Image.new('RGB',(100,100),'white').save(out,format='PNG')
    pages,notes=document_text.read_pages(out.getvalue(),'image/png')
    assert not pages[0]['text'] and any('no usable text' in n for n in notes)
    assert set(Path('/dev/shm').glob('nyayavault-ocr-*'))==before


def test_real_ocr_through_authorized_api(client,login,monkeypatch):
    monkeypatch.setattr(settings,'ai_provider','gemini')
    monkeypatch.setattr(settings,'gemini_api_key',SecretStr('fake-test-only'))
    headers=login('admin')
    case=client.post('/api/cases',headers=headers,json={'case_number':'OCR-RUNTIME','title':'Fictional OCR test'}).json()
    e=client.post('/api/evidence',headers=headers,data={'case_id':case['id'],'evidence_id':'OCR-SCAN'},files={'file':('scan.pdf',pdf(),'application/pdf')})
    assert e.status_code==201,e.text
    def answer(question,sources):
        assert len(sources)==2 and sources[1]['page']==2 and sources[1]['method']=='ocr'
        assert '24' in sources[1]['excerpt']
        return assistant.Answer(claims=[assistant.Claim(text='The record states 24 units.',citations=[assistant.Citation(source_id=sources[1]['source_id'],quote=sources[1]['excerpt'])])])
    monkeypatch.setattr(assistant,'generate',answer)
    payload={'case_id':case['id'],'evidence_ids':[e.json()['id']],'question':'How many units were recovered?','confirm_demo_external_processing':True}
    response=client.post('/api/assistant/ask',headers=headers,json=payload)
    assert response.status_code==200,response.text
    body=response.json()
    cited=next(s for s in body['sources'] if s['source_id']==body['claims'][0]['citations'][0]['source_id'])
    assert cited['page']==2 and body['warnings']
    assert client.post('/api/assistant/ask',headers=login('legal'),json=payload).status_code==403

def test_real_selectable_pdf():
    content=b'BT /F1 20 Tf 50 700 Td (Fictional invoice amount 45000) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream']
    data=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    xref=len(data);data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for off in offsets[1:]: data.extend(f'{off:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    pages,_=document_text.read_pages(bytes(data),'application/pdf')
    assert pages[0]['method']=='text' and pages[0]['page']==1 and '45000' in pages[0]['text']
