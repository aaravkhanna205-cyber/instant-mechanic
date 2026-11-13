"""Deterministic, free, auditable drafting policy. Never makes employment decisions."""
import re
from datetime import datetime, timezone

KINDS = {'interview_reminder', 'application_followup', 'document_request', 'interview_invitation', 'task_suggestion'}
SENSITIVE = re.compile(r'\b(?:reject|rejected|you are hired|you are fired|fired|disqualify|blacklist|withdraw)\b', re.I)
ALLOWED_STATES = {'pending','approved','rejected','queued','processing','delivered','outbox','failed','cancelled'}

def validate_draft(kind: str, message: str) -> str:
    if kind not in KINDS: raise ValueError('Unsupported agent action')
    message=message.strip()
    if not 8 <= len(message) <= 4000: raise ValueError('Draft must be 8-4000 characters')
    if SENSITIVE.search(message): raise ValueError('Hiring outcome changes are not allowed through automation')
    if any(ch in message for ch in ['\x00','\r']): raise ValueError('Invalid message')
    return message

def draft_message(kind: str, candidate_name: str, job_title: str, *, when: str='') -> str:
    name = (candidate_name or 'Candidate').strip()[:100].replace('\n',' ')
    job = (job_title or 'the role').strip()[:180].replace('\n',' ')
    templates = {
        'interview_reminder': f'Hello {name}, this is a reminder about your upcoming interview for {job}{" on " + when if when else ""}. Please check your interview details in the candidate portal. Regards, Instant Mechanic Hire.',
        'interview_invitation': f'Hello {name}, an interview for {job} is being arranged. Please check your candidate portal for the confirmed schedule. Regards, Instant Mechanic Hire.',
        'application_followup': f'Hello {name}, we are following up on your application for {job}. Please check the candidate portal for updates. Regards, Instant Mechanic Hire.',
        'document_request': f'Hello {name}, please review the document requests in your candidate portal for your application to {job}. Please do not email sensitive documents unless using an approved secure channel. Regards, Instant Mechanic Hire.',
        'task_suggestion': f'Review the open recruitment tasks for {job}. Verify candidate records and schedule appropriate follow-ups.'
    }
    return validate_draft(kind, templates[kind])

def keyword_evidence(query: str, sources: list[dict], limit: int=5) -> list[dict]:
    """Extractive retrieval only; never invent document citations."""
    terms=set(re.findall(r'[a-z0-9]{3,}',query.lower()))
    scored=[]
    for item in sources:
        body=item['body']
        score=len(terms.intersection(set(re.findall(r'[a-z0-9]{3,}',body.lower()+' '+item['title'].lower()))))
        if score: scored.append((score,item))
    scored.sort(key=lambda pair: (-pair[0],pair[1]['title']))
    return [{'id':str(it['id']),'title':it['title'],'excerpt':it['body'][:650],'matched_terms':score} for score,it in scored[:limit]]

def safe_recipient(email: str) -> bool:
    return bool(re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email or ''))
