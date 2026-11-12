import pytest
from app.phase4_ai.documents import validate_file,InvalidResume,reviewable_skills,chunks,interview_prompts

def test_invalid_extension():
    with pytest.raises(InvalidResume): validate_file('resume.exe',b'example')
def test_no_path_traversal():
    with pytest.raises(InvalidResume): validate_file('../resume.pdf',b'%PDF-example')
def test_pdf_magic():
    assert validate_file('resume.pdf',b'%PDF-1.7\n')=='application/pdf'
def test_reject_fake_docx():
    with pytest.raises(InvalidResume):validate_file('resume.docx',b'PK\x03\x04broken')
def test_size_limit():
    with pytest.raises(InvalidResume):validate_file('resume.pdf',b'%PDF-'+b'x'*(8*1024*1024))
def test_skills_are_evidence_based():
    found=reviewable_skills('Built a Python API and wrote SQL queries.')
    assert {x['skill'] for x in found}=={'python','sql'}
def test_not_matching_partial_words():
    assert reviewable_skills('pythonic')==[]
def test_chunks_bounded():
    assert len(chunks('x'*200000))<=120
def test_prompts_require_human_review():
    assert len(interview_prompts('Software Engineer',['Python']))==3
