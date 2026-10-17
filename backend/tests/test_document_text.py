import subprocess
from pathlib import Path
import pytest
from fastapi import HTTPException
from app import document_text, assistant

def test_text_and_invalid_encoding():
    pages, notes = document_text.read_pages(b'Original fictional record.', 'text/plain')
    assert pages[0]['text'] == 'Original fictional record.' and pages[0]['page'] is None
    assert not notes
    with pytest.raises(HTTPException):
        document_text.read_pages(b'\xff', 'text/plain')

def test_ocr_lines_and_uncertainty(monkeypatch):
    tsv = b'level\tblock_num\tpar_num\tline_num\tconf\ttext\n5\t1\t1\t1\t98\tInvoice\n5\t1\t1\t1\t45\t45000\n5\t1\t1\t2\t92\tPaid\n'
    monkeypatch.setattr(document_text, 'run', lambda *a, **k:tsv)
    text, uncertain = document_text.recognize('unused', 1)
    assert text == 'Invoice 45000\nPaid' and uncertain

@pytest.fixture
def scratch(monkeypatch, tmp_path):
    import tempfile
    real_temp = tempfile.TemporaryDirectory
    monkeypatch.setattr(document_text.Path, 'is_dir', lambda _:True)
    monkeypatch.setattr(document_text.tempfile, 'TemporaryDirectory', lambda **kw:real_temp(prefix='ocr-', dir=tmp_path))
    return tmp_path

def test_mixed_pdf_pages_and_cleanup(monkeypatch, scratch):
    def run(args, *a, **kw):
        if args[0] == 'pdfinfo': return b'Pages: 2\n'
        if args[0] == 'pdftotext': return b'Typed first page.' if args[2] == '1' else b''
        if args[0] == 'pdftoppm':
            Path(args[-1]+'.png').write_bytes(b'fictional render')
            return b''
        raise AssertionError(args)
    monkeypatch.setattr(document_text, 'run', run)
    monkeypatch.setattr(document_text, 'recognize', lambda *a:('Scanned second page.', True))
    pages, notes = document_text.read_pages(b'pdf', 'application/pdf')
    assert [(p['page'], p['method']) for p in pages] == [(1,'text'),(2,'ocr')]
    assert any('Page 2' in n and 'uncertain' in n for n in notes)
    assert list(scratch.iterdir()) == []
    pages, notes = document_text.read_pages(b'pdf', 'application/pdf', True)
    assert all(p['method'] == 'ocr' for p in pages)
    assert list(scratch.iterdir()) == []

def test_page_limit_and_unreadable_notice(monkeypatch, scratch):
    monkeypatch.setattr(document_text, 'run', lambda args,*a,**k:b'Pages: 25\n' if args[0]=='pdfinfo' else b'')
    monkeypatch.setattr(document_text, 'recognize', lambda *a:('', True))
    pages, notes = document_text.read_pages(b'pdf', 'application/pdf')
    assert len(pages)==20 and any('20 of 25' in n for n in notes)
    assert any('no usable text' in n for n in notes)
    assert list(scratch.iterdir()) == []

def test_timeout_is_bounded(monkeypatch):
    def fail(*a,**k): raise subprocess.TimeoutExpired('reader',20)
    monkeypatch.setattr(document_text.subprocess,'run',fail)
    with pytest.raises(HTTPException) as e: document_text.run(['reader'])
    assert e.value.status_code==422

def test_page_excerpt_finds_relevant_late_text():
    text='Background material. '*300+'Unique invoice total 45000.'
    excerpt, limited=assistant.excerpt(text,'invoice total',False,limit=300)
    assert limited and len(excerpt)<=300 and '45000' in excerpt

def test_failed_ocr_cleans_temporary_files(monkeypatch, scratch):
    def run(args,*a,**k):
        if args[0]=='pdfinfo': return b'Pages: 1\n'
        if args[0]=='pdftotext': return b''
        Path(args[-1]+'.png').write_bytes(b'private page')
        return b''
    monkeypatch.setattr(document_text,'run',run)
    def fail(*a): raise HTTPException(422,'OCR failed')
    monkeypatch.setattr(document_text,'recognize',fail)
    with pytest.raises(HTTPException): document_text.read_pages(b'pdf','application/pdf')
    assert list(scratch.iterdir())==[]

def test_damaged_image_rejected_and_cleaned(scratch):
    with pytest.raises(HTTPException) as error:
        document_text.read_pages(b'not an image','image/png')
    assert error.value.status_code==422 and list(scratch.iterdir())==[]
