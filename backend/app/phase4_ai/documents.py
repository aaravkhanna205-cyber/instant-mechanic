"""Bounded resume ingestion. Uploaded content is untrusted; never execute it."""
from io import BytesIO
from pathlib import Path
import re
import zipfile

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 25
MAX_CHARS = 80000
SKILLS = ("python", "sql", "excel", "power bi", "fastapi", "react", "javascript", "typescript", "docker", "aws", "postgresql", "redis", "machine learning", "data analysis", "customer support", "automotive", "recruitment", "communication")

class InvalidResume(ValueError):
    pass

def validate_file(filename: str, data: bytes) -> str:
    if not filename or filename != Path(filename).name or '\\' in filename or '/' in filename:
        raise InvalidResume("Invalid file name")
    if not data or len(data) > MAX_BYTES:
        raise InvalidResume("Resume must be 1 byte to 8 MB")
    name = filename.lower()
    if name.endswith('.pdf') and data.startswith(b'%PDF-'):
        return 'application/pdf'
    if name.endswith('.docx') and data[:4] == b'PK\x03\x04':
        try:
            with zipfile.ZipFile(BytesIO(data)) as z:
                infos = z.infolist()
                if len(infos) > 3000 or sum(i.file_size for i in infos) > 40 * 1024 * 1024:
                    raise InvalidResume('DOCX exceeds safe extraction limits')
                if 'word/document.xml' not in z.namelist():
                    raise InvalidResume('Invalid DOCX structure')
        except zipfile.BadZipFile as e:
            raise InvalidResume('Invalid DOCX') from e
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    raise InvalidResume('Only valid PDF and DOCX files are supported')

def extract_text(filename: str, data: bytes) -> str:
    kind = validate_file(filename, data)
    try:
        if kind == 'application/pdf':
            from pypdf import PdfReader
            pdf = PdfReader(BytesIO(data), strict=True)
            if pdf.is_encrypted or len(pdf.pages) > MAX_PAGES:
                raise InvalidResume('Encrypted or oversized PDF is not supported')
            content = '\n'.join(page.extract_text() or '' for page in pdf.pages)
        else:
            from docx import Document
            doc = Document(BytesIO(data))
            if len(doc.paragraphs) > 5000 or len(doc.tables) > 100:
                raise InvalidResume('DOCX contains too many elements')
            blocks = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows[:150]:
                    blocks.extend(c.text for c in row.cells[:30])
            content = '\n'.join(blocks)
    except InvalidResume:
        raise
    except Exception as exc:
        raise InvalidResume('Unable to extract document text') from exc
    text = re.sub(r'[ \t]+',' ',content).strip()
    if not text or len(text) > MAX_CHARS:
        raise InvalidResume('No selectable text or extracted text too long')
    return text

def reviewable_skills(text: str) -> list[dict]:
    found = []
    for skill in SKILLS:
        m = re.search(r'(?<!\w)' + re.escape(skill) + r'(?!\w)', text, re.I)
        if m:
            start, end = max(0,m.start()-50), min(len(text),m.end()+50)
            found.append({'skill':skill, 'evidence': text[start:end].replace('\n',' ')})
    return found

def chunks(text: str, size: int=900, overlap: int=120) -> list[str]:
    if size <= overlap or overlap < 0: raise ValueError('Invalid chunk size')
    return [text[i:i+size] for i in range(0,len(text),size-overlap)][:120]

def interview_prompts(job_title: str, requirements: list[str]) -> list[str]:
    # Structured prompts, not fabricated AI insights or hiring decisions.
    clean = [r.strip()[:120] for r in requirements if r.strip()][:8]
    questions = [f'Tell us about a project relevant to {job_title[:120]}. What was your contribution?',
                 'Describe a difficult problem you solved and how you verified the result.']
    questions.extend(f'How have you used {r} in a real task? Please explain the context and outcome.' for r in clean)
    return questions
