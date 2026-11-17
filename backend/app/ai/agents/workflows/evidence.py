"""Resume evidence matching for the Resume Review workflow.

Free and deterministic: no LLM, no embeddings, no paid key.
Resume text is untrusted data. It is searched for quotes; it is never followed as instructions.
The output is evidence per requirement, never a score, ranking or hiring decision.
"""
import re

SUPPORTED = 'supported'
UNCLEAR = 'unclear'
MISSING = 'missing_evidence'
STATUSES = (SUPPORTED, UNCLEAR, MISSING)

# Generic words that say nothing about a skill. Ignored when matching a requirement.
STOPWORDS = {
    'and', 'the', 'for', 'with', 'from', 'into', 'over', 'under', 'that', 'this', 'have', 'has', 'are',
    'was', 'were', 'will', 'can', 'able', 'ability', 'good', 'strong', 'excellent', 'basic', 'advanced',
    'knowledge', 'experience', 'experienced', 'skill', 'skills', 'year', 'years', 'yrs', 'least',
    'minimum', 'plus', 'preferred', 'required', 'must', 'should', 'working', 'work', 'understanding',
    'familiar', 'familiarity', 'proficient', 'proficiency', 'using', 'use', 'any', 'all', 'our', 'your',
}

# Text that tries to talk to an AI instead of describing the candidate.
INJECTION = re.compile(
    r'(ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)'
    r'|disregard\s+(all\s+|any\s+)?(previous|prior|above|earlier|the)'
    r'|system\s+prompt|developer\s+message|\bassistant\s*:|\bsystem\s*:'
    r'|you\s+are\s+now\b|act\s+as\s+(an?\s+)?(ai|assistant|recruiter|hr)'
    r'|(rank|rate|score|select|shortlist|hire|approve)\s+this\s+(candidate|applicant|resume)'
    r'|mark\s+(all|every)\s+requirements?\s+as'
    r'|<\s*script)',
    re.I,
)

MAX_EXCERPT = 300
MAX_SENTENCES = 4000


def terms_for(label: str) -> list[str]:
    """Meaningful words of a requirement, in order, without duplicates."""
    words = re.findall(r'[a-z0-9][a-z0-9+#.]*', label.lower())
    seen: list[str] = []
    for word in words:
        word = word.strip('.')
        if (len(word) >= 3 or word in ('c', 'r', 'go', 'ai', 'ml', 'bi', 'ui', 'ux', 'qa', 'hr')) and word not in STOPWORDS and word not in seen:
            seen.append(word)
    return seen


def split_sentences(chunks: list[dict]) -> list[dict]:
    """Break ordered resume parts into short sentences, keeping which part each came from.

    Chunks overlap by design (Phase 4), so repeated sentences are dropped.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for chunk in chunks:
        for raw in re.split(r'(?<=[.!?])\s+|\n+|\s*[•·▪●|]\s*', chunk.get('excerpt') or ''):
            sentence = ' '.join(raw.split())
            key = sentence.lower()
            if len(sentence) < 3 or key in seen:
                continue
            seen.add(key)
            out.append({'text': sentence, 'part': int(chunk.get('position', 0)) + 1})
            if len(out) >= MAX_SENTENCES:
                return out
    return out


def safety_scan(sentences: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (usable sentences, flagged sentences). Flagged text is never cited as evidence."""
    clean, flagged = [], []
    for sentence in sentences:
        (flagged if INJECTION.search(sentence['text']) else clean).append(sentence)
    return clean, [{'excerpt': f['text'][:MAX_EXCERPT], 'part': f['part']} for f in flagged[:20]]


def _hits(term: str, text: str) -> bool:
    return re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', text) is not None


def match_requirement(label: str, sentences: list[dict]) -> dict:
    """Find the single best quote for one requirement.

    supported: every key word appears in one sentence (numbers must match too).
    unclear:   some key words appear, or the requirement has nothing checkable.
    missing_evidence: no key word appears anywhere.
    """
    terms = terms_for(label)
    if not terms:
        return {'requirement': label, 'status': UNCLEAR, 'excerpt': None, 'part': None,
                'matched_terms': [], 'note': 'Requirement has no checkable words; review by hand.'}
    best, best_found = None, []
    for sentence in sentences:
        lower = sentence['text'].lower()
        found = [t for t in terms if _hits(t, lower)]
        if len(found) > len(best_found):
            best, best_found = sentence, found
            if len(found) == len(terms):
                break
    if not best_found:
        return {'requirement': label, 'status': MISSING, 'excerpt': None, 'part': None,
                'matched_terms': [], 'note': 'No matching text found in the resume.'}
    complete = len(best_found) == len(terms)
    note = None
    if complete and any(t.isdigit() for t in terms):
        note = 'Numbers matched in the text; confirm the actual duration or level by hand.'
    elif not complete:
        missing = [t for t in terms if t not in best_found]
        note = 'Partly matched. Not found: ' + ', '.join(missing[:6])
    return {'requirement': label, 'status': SUPPORTED if complete else UNCLEAR,
            'excerpt': best['text'][:MAX_EXCERPT], 'part': best['part'],
            'matched_terms': best_found, 'note': note}


def evidence_matrix(requirements: list[str], sentences: list[dict]) -> list[dict]:
    return [match_requirement(label, sentences) for label in requirements[:40]]


def summary(job_title: str, matrix: list[dict], flagged: list[dict]) -> str:
    """A plain description of the matrix. It states counts, not a verdict."""
    counts = {status: sum(1 for row in matrix if row['status'] == status) for status in STATUSES}
    names = lambda status: ', '.join(r['requirement'] for r in matrix if r['status'] == status)[:600]
    lines = [f'Resume evidence for {job_title[:180]}: {len(matrix)} requirements checked.']
    if counts[SUPPORTED]:
        lines.append(f'Text found for {counts[SUPPORTED]}: {names(SUPPORTED)}.')
    if counts[UNCLEAR]:
        lines.append(f'Partly found or needs checking for {counts[UNCLEAR]}: {names(UNCLEAR)}.')
    if counts[MISSING]:
        lines.append(f'No text found for {counts[MISSING]}: {names(MISSING)}.')
    if not matrix:
        lines.append('This job has no requirements listed, so nothing was checked.')
    if flagged:
        lines.append(f'{len(flagged)} line(s) in the resume look like instructions to an AI; they were ignored and are shown for review.')
    lines.append('These are unverified resume claims. This is not a score or a recommendation; a recruiter decides.')
    return ' '.join(lines)
