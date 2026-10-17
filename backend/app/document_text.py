"""Local page extraction. Temporary plaintext is confined to Linux shared memory."""
import csv
import io
import re
import subprocess
import tempfile
import time
import warnings
from pathlib import Path
from fastapi import HTTPException
from PIL import Image, ImageOps

FORMATS = ('text/plain', 'application/pdf', 'image/png', 'image/jpeg')
MAX_PAGES = 20
Image.MAX_IMAGE_PIXELS = 16_000_000


def run(args, data=None, deadline=None):
    timeout = min(20, (deadline or time.monotonic()+20)-time.monotonic())
    if timeout <= 0:
        raise HTTPException(422, 'Document reading timed out. Select a smaller document.')
    try:
        return subprocess.run(args, input=data, capture_output=True, check=True, timeout=timeout).stdout
    except FileNotFoundError:
        raise HTTPException(503, 'Document reader unavailable. Rebuild the backend image.')
    except (subprocess.SubprocessError, OSError):
        raise HTTPException(422, 'Document could not be read. It may be damaged, password-protected or too complex.')


def recognize(path, deadline):
    raw = run(['tesseract', str(path), 'stdout', '-l', 'eng', 'tsv'], deadline=deadline)
    lines = {}; scores = []
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8')), delimiter='\t', quoting=csv.QUOTE_NONE):
        word = row.get('text', '').strip()
        if not word or row.get('level') != '5':
            continue
        key = tuple(row[k] for k in ('block_num', 'par_num', 'line_num'))
        lines.setdefault(key, []).append(word)
        scores.append(float(row['conf']))
    text = '\n'.join(' '.join(words) for words in lines.values())
    uncertain = not scores or any(score < 60 for score in scores)
    return text, uncertain


def read_pages(data, mime, force_ocr=False):
    if mime == 'text/plain':
        try:
            return [{'page':None, 'text':data.decode('utf-8'), 'method':'text', 'uncertain':False}], []
        except UnicodeDecodeError:
            raise HTTPException(422, 'Evidence text is not valid UTF-8')
    if mime not in FORMATS:
        raise HTTPException(422, 'Choose text, PDF, PNG or JPEG evidence.')
    if not Path('/dev/shm').is_dir():
        raise HTTPException(503, 'Run document reading in the Docker backend; memory-only temporary storage is required.')
    deadline = time.monotonic()+90
    notes = []; pages = []
    with tempfile.TemporaryDirectory(prefix='nyayavault-ocr-', dir='/dev/shm') as directory:
        root = Path(directory)
        if mime == 'application/pdf':
            info = run(['pdfinfo', '-'], data, deadline).decode('utf-8', errors='replace')
            match = re.search(r'^Pages:\s+(\d+)', info, re.M)
            if not match:
                raise HTTPException(422, 'Could not determine PDF page count.')
            count = int(match.group(1))
            if count > MAX_PAGES:
                notes.append(f'Only the first {MAX_PAGES} of {count} pages were read.')
            for number in range(1, min(count, MAX_PAGES)+1):
                text = '' if force_ocr else run(['pdftotext', '-f', str(number), '-l', str(number), '-enc', 'UTF-8', '-', '-'], data, deadline).decode('utf-8')
                method = 'text'; uncertain = False
                if len(text.strip()) < 10:
                    run(['pdftoppm', '-f', str(number), '-l', str(number), '-singlefile', '-scale-to', '2000', '-png', '-', str(root/'page')], data, deadline)
                    text, uncertain = recognize(root/'page.png', deadline)
                    (root/'page.png').unlink(missing_ok=True)
                    method = 'ocr'
                pages.append({'page':number, 'text':text, 'method':method, 'uncertain':uncertain})
            if not force_ocr:
                notes.append('Pages with selectable text use that text. Enable “Scan every PDF page” if a page also contains scanned notes.')
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(data)) as image:
                        if image.format not in ('PNG', 'JPEG'):
                            raise ValueError('Unsupported image encoding')
                        image.load()
                        image = ImageOps.exif_transpose(image).convert('RGB')
                        image.thumbnail((2400, 2400))
                        image.save(root/'page.png')
            except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise HTTPException(422, 'Image is damaged or too large (maximum 16 megapixels).')
            text, uncertain = recognize(root/'page.png', deadline)
            pages.append({'page':1, 'text':text, 'method':'ocr', 'uncertain':uncertain})
    if any(p['method'] == 'ocr' for p in pages):
        notes.append('OCR reads printed English. Handwriting and other languages are not reliably supported. Compare every OCR quotation with the original page; confidence is not a guarantee.')
    for page in pages:
        if len(page['text'].strip()) < 10:
            notes.append(f"Page {page['page']}: no usable text; not analyzed.")
        elif page['uncertain']:
            notes.append(f"Page {page['page']}: uncertain OCR words; check the original.")
    return pages, notes
