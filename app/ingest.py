import os
import json
from pathlib import Path
from langdetect import detect, DetectorFactory

try:
    from PyPDF2 import PdfReader
except :
    PdfReader = None

try:
    import docx
except :
    docx = None

DetectorFactory.seed = 0

def read_txt(path) :
    with open(path, 'r', encoding='utf-8', errors='ignore') as f :
        return f.read()

def read_pdf(path) :
    if PdfReader is None :
        return ''
    text = []
    try :
        reader = PdfReader(path)
        for page in reader.pages :
            try :
                text.append(page.extract_text() or '')
            except :
                continue
    except :
        return ''
    return "\n".join(text)

def read_docx(path) :
    if docx is None :
        return ''
    try :
        doc = docx.Document(path)
        return "\n".join(par.text for par in doc.paragraphs)
    except :
        return ''


def chunk_text(text, chunk_size=800, overlap=200) :
    if not text :
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length :
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap if end < length else end
    return [chunk for chunk in chunks if chunk]


def detect_lang(text) :
    try :
        return detect(text)
    except :
        return 'unknown'


def ingest(data_path='corpus', store_path='corpus/chunks.jsonl') :
    data_path = Path(data_path)
    store_path = Path(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)

    with store_path.open('w', encoding='utf-8') as store_file :

        for root, _, files in os.walk(data_path) :
            for filename in files :
                filepath = Path(root) / filename
                ext = filepath.suffix.lower()

                if ext in ('.txt', '.md') :
                    text = read_txt(filepath)
                elif ext == '.pdf' :
                    text = read_pdf(filepath)
                elif ext in ('.docx',) :
                    text = read_docx(filepath)
                else :
                    continue

                if not text :
                    continue

                chunks = chunk_text(text)
                for i, chunk in enumerate(chunks) :
                    metadata = {
                        'text'     : chunk,
                        'source'   : str(filepath),
                        'type'     : ext.lstrip('.'),
                        'position' : i,
                        'language' : detect_lang(chunk)
                    }
                    store_file.write(json.dumps(metadata, ensure_ascii=False) + '\n')


if __name__ == '__main__' :
    ingest()
