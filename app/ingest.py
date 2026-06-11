import os
import json
from pathlib import Path

try :
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
except :
    detect = None

try :
    import pdfplumber
except :
    pdfplumber = None

try :
    import csv
except :
    csv = None


def read_txt(path) :
    with open(path, 'r', encoding='utf-8', errors='ignore') as f :
        return f.read()

def read_pdf(path) :
    if pdfplumber is None :
        return ''
    try :
        with pdfplumber.open(path) as pdf_file :
            text = []
            for page in pdf_file.pages :
                    text_prov = page.extract_text()
                    if text_prov != None :
                        text.append(text_prov)
            return "\n".join(text)
    except :
        return ''
    
def read_csv(path) :
    if csv is None :
        return ''
    try :
        with open(path, 'r', encoding='utf-8', errors='ignore') as csv_file :
            reader = csv.reader(csv_file)
            text = [', '.join(row) for row in reader]
            return '\n'.join(text)
    except :
        return ''

def chunk_text(text, chunk_size=800, overlap=120) :
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
    if detect == None :
        return 'unknown'
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
                elif ext == '.csv' :
                    text = read_csv(filepath)
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
