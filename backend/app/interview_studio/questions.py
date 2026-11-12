"""Draft interview questions for a recruiter to edit and approve.

Drafts come from a local AI model (Ollama on this PC) when OLLAMA_URL is set, and
from simple rules otherwise or whenever the model is unreachable. Nothing produced
here is saved or shown to a candidate until a recruiter approves it.
"""
import json
import logging
import re
import urllib.error
import urllib.request

from app.core.config import settings

log = logging.getLogger(__name__)
MAX_QUESTIONS = 12
MAX_LENGTH = 400
LLM_TIMEOUT_SECONDS = 120

# Topics an interviewer must not ask about. Drafts touching them are dropped.
BLOCKED_TOPICS = re.compile(
    r"\b(age|how old|date of birth|married|marital|husband|wife|pregnan|children|kids|family plan|religio|caste|"
    r"gender|sexual|disab|health condition|medical|nationalit|ethnic|race|political|native place|mother tongue)\b",
    re.I,
)


def clean_questions(items, limit: int = MAX_QUESTIONS) -> list[str]:
    """Normalise, drop unusable or off-limits drafts, and remove duplicates."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, str):
            continue
        text = re.sub(r"\s+", " ", item).strip().lstrip("-*0123456789.) ").strip()
        if len(text) < 15 or len(text) > MAX_LENGTH or BLOCKED_TOPICS.search(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def rule_questions(job_title: str, requirements: list[str], count: int) -> list[str]:
    title = job_title.strip() or "this role"
    drafts = [
        f"Tell us about a recent piece of work that is relevant to the {title} role. What exactly was your part in it?",
        "Describe a difficult problem you solved at work. How did you check that your solution really worked?",
    ]
    for label in requirements:
        label = label.strip().rstrip(".")
        if label:
            drafts.append(f"This role needs: {label}. Give a specific example of when you have done this, and what the result was.")
    drafts += [
        "Tell us about a time you made a mistake at work. What did you do next, and what did you change afterwards?",
        "How do you organise your work when several urgent tasks arrive at the same time?",
        f"What would you want to learn or improve in your first three months in the {title} role?",
        "Describe a time you had to explain something technical or complicated to someone without that background.",
    ]
    return clean_questions(drafts, count)


def build_prompt(job_title: str, job_description: str, requirements: list[str], count: int) -> str:
    needs = "\n".join(f"- {label}" for label in requirements) or "- (no specific requirements were listed)"
    return (
        "You are helping a recruiter prepare a structured, fair job interview.\n"
        f"Write exactly {count} interview questions for the role below.\n\n"
        f"Role: {job_title}\n"
        f"About the role: {(job_description or 'Not provided')[:1500]}\n"
        f"Requirements:\n{needs}\n\n"
        "Rules:\n"
        "- Plain, simple English that a candidate reading in a second language understands.\n"
        "- Each question asks for a real past example or a concrete way of working, and is answerable in writing.\n"
        "- Cover the listed requirements; one question per requirement where possible.\n"
        "- One question only per item. No multi-part lists, no trick questions, no yes/no questions.\n"
        "- Never ask about age, marriage, family, religion, caste, gender, health, disability, nationality or politics.\n\n"
        'Reply with JSON only, in this exact shape: {"questions": ["...", "..."]}'
    )


def llm_questions(job_title: str, job_description: str, requirements: list[str], count: int) -> list[str]:
    """Ask the local Ollama model. Returns [] on any problem so the caller can fall back."""
    base = settings.ollama_url.strip().rstrip("/")
    if not base:
        return []
    payload = json.dumps({
        "model": settings.ollama_model,
        "prompt": build_prompt(job_title, job_description, requirements, count),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4},
    }).encode()
    request = urllib.request.Request(f"{base}/api/generate", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8", "replace"))
        parsed = json.loads(body.get("response") or "{}")
        items = parsed.get("questions") if isinstance(parsed, dict) else parsed
        return clean_questions(items if isinstance(items, list) else [], count)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("Local AI question draft unavailable: %s", type(exc).__name__)
        return []


def draft_questions(job_title: str, job_description: str, requirements: list[str], count: int) -> dict:
    """Return {'source': 'local_ai' | 'rules', 'questions': [...]}; AI drafts are topped up with rule drafts."""
    count = max(3, min(count, MAX_QUESTIONS))
    from_model = llm_questions(job_title, job_description, requirements, count)
    if len(from_model) >= 3:
        return {"source": "local_ai", "questions": from_model}
    return {"source": "rules", "questions": rule_questions(job_title, requirements, count)}
