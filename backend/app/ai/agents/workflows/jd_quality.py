"""Job description checks and a structured draft. Free and deterministic.

The draft only reorganises what the job already says. Anything missing becomes a [placeholder]
for the recruiter to fill in; nothing is invented. A recruiter must approve before the job changes.
"""
import re
from .evidence import terms_for

FIX = 'fix'          # wording that can exclude people or break the law; should change before publishing
IMPROVE = 'improve'  # makes the job clearer for candidates

# (pattern, why it matters, what to write instead)
EXCLUSIONARY = [
    (r'\b(young|youthful)\b', 'Age-related wording discourages older applicants.', 'Describe the work instead, for example "comfortable with fast-paced shifts".'),
    (r'\b(under|below|less than|max(imum)?)\s+\d{2}\s*(years|yrs)(\s+(of\s+age|old))?\b|\bage\s*(limit|below|under)\b', 'An age limit excludes applicants by age.', 'Remove the age limit unless a law requires it.'),
    (r'\brecent graduates? only\b|\bfreshers? only\b', 'Limits the job to one age group without a work reason.', 'Say the experience level needed, for example "0 to 2 years of experience".'),
    (r'\b(male|female|men|women)\s+(only|candidates? only|preferred)\b|\bonly\s+(male|female|men|women)\b', 'Restricting by gender is discriminatory.', 'Remove the gender requirement.'),
    (r'\b(boys|girls)\b', 'Gendered and informal.', 'Use "candidates" or "team members".'),
    (r'\b(salesman|salesmen|chairman|manpower|workman)\b', 'Gendered job word.', 'Use "salesperson", "chair", "staff", "worker".'),
    (r'\b(unmarried|married|single)\b', 'Marital status is not a job requirement.', 'Remove it.'),
    (r'\b(good[- ]looking|fair[- ]skinned|fair complexion|attractive|pleasing personality)\b', 'Appearance requirement is discriminatory.', 'Describe the job skill, for example "polite with customers".'),
    (r'\bnative (speaker|english|hindi)\b', 'Excludes fluent non-native speakers.', 'Say the level needed, for example "fluent spoken English".'),
]
PRONOUNS = [
    (r'\b(he|him|his|she|her)\b', 'Gendered pronoun. If it refers to the applicant, it suggests one gender.', 'Use "you" or "the candidate".'),
]
JARGON = [
    (r'\b(rock ?star|ninja|guru|wizard|superstar|jedi)\b', 'Vague hype word; candidates cannot tell what is needed.', 'Name the actual skill.'),
]
SECTIONS = {
    'responsibilities': (r'responsibilit|you will|duties|day[- ]to[- ]day|your role', 'What the person will do day to day is not described.', '[Add 3 to 5 main responsibilities]'),
    'hours': (r'\bshift|working hours|\bhours\b|timing|working days|\d\s*(am|pm)\b|weekend', 'Working hours or shifts are not mentioned.', '[Add shift or working hours]'),
    'pay': (r'salary|\bctc\b|\bpay\b|compensation|₹|\blpa\b|stipend|per month', 'No salary or pay range is given. Ranges usually get more applicants.', '[Add salary range]'),
}
# Words that describe character, not a checkable skill. A requirement made only of these is too vague.
SOFT_WORDS = {'attitude', 'personality', 'hardworking', 'hard-working', 'hard', 'dedicated', 'motivated', 'smart',
              'energetic', 'passionate', 'team', 'player', 'honest', 'punctual', 'positive', 'confident',
              'presentable', 'dynamic', 'sincere', 'disciplined', 'committed', 'self-starter', 'go-getter'}
EMPLOYMENT = {'full_time': 'Full time', 'part_time': 'Part time', 'contract': 'Contract', 'internship': 'Internship', 'temporary': 'Temporary'}


def _issue(kind: str, severity: str, where: str, text: str, why: str, suggestion: str) -> dict:
    return {'kind': kind, 'severity': severity, 'where': where, 'text': text[:200], 'why': why, 'suggestion': suggestion}


def _scan(text: str, where: str, rules: list, severity: str, kind: str) -> list[dict]:
    found, seen = [], set()
    for pattern, why, suggestion in rules:
        for match in re.finditer(pattern, text, re.I):
            key = (match.group(0).lower(), pattern)
            if key not in seen:
                seen.add(key)
                found.append(_issue(kind, severity, where, match.group(0), why, suggestion))
    return found


def check(job: dict) -> list[dict]:
    """Issues in a job, most serious first."""
    description = (job.get('description') or '').strip()
    labels = [r['label'] for r in job.get('requirements', [])]
    issues: list[dict] = []
    issues += _scan(job.get('title', ''), 'title', EXCLUSIONARY, FIX, 'exclusionary')
    issues += _scan(description, 'description', EXCLUSIONARY, FIX, 'exclusionary')
    for label in labels:
        issues += _scan(label, 'requirement', EXCLUSIONARY, FIX, 'exclusionary')
    issues += _scan(description, 'description', PRONOUNS, IMPROVE, 'gendered')
    issues += _scan(job.get('title', '') + '\n' + description, 'description', JARGON, IMPROVE, 'vague')
    if len(description) < 300:
        issues.append(_issue('short', IMPROVE, 'description', f'{len(description)} characters',
                             'Short descriptions leave candidates guessing what the job is.', 'Aim for at least 300 characters.'))
    for name, (pattern, why, placeholder) in SECTIONS.items():
        if not re.search(pattern, description, re.I):
            issues.append(_issue('missing_' + name, IMPROVE, 'description', name, why, f'Fill in {placeholder} in the draft.'))
    if not job.get('location') and not re.search(r'\blocation\b|\bremote\b|\bonsite\b|\bon-site\b', description, re.I):
        issues.append(_issue('missing_location', IMPROVE, 'job', 'location', 'Candidates need to know where the job is.', 'Set the job location.'))
    if not labels:
        issues.append(_issue('no_requirements', IMPROVE, 'requirements', '0 requirements',
                             'Without requirements, resume and interview evidence cannot be checked.', 'Add 3 to 8 specific requirements.'))
    if len(labels) > 12:
        issues.append(_issue('too_many', IMPROVE, 'requirements', f'{len(labels)} requirements',
                             'Long lists put off qualified applicants.', 'Keep the 8 that matter most; mark the rest as nice to have.'))
    seen: dict[str, str] = {}
    for label in labels:
        key = ' '.join(label.lower().split())
        if key in seen:
            issues.append(_issue('duplicate', IMPROVE, 'requirement', label, 'Listed twice.', 'Remove the duplicate.'))
        seen[key] = label
        if not [t for t in terms_for(label) if t not in SOFT_WORDS]:
            issues.append(_issue('vague_requirement', IMPROVE, 'requirement', label,
                                 'Too general to check against a resume or interview.', 'Name the skill, tool or certificate.'))
        if len(label) > 120:
            issues.append(_issue('long_requirement', IMPROVE, 'requirement', label, 'Very long requirement.', 'Split it into shorter ones.'))
    return sorted(issues, key=lambda i: i['severity'] != FIX)


def draft(job: dict, issues: list[dict]) -> str:
    """The job reorganised into clear sections. Placeholders mark what is missing."""
    missing = {i['kind'] for i in issues}
    location = job.get('location') or '[Add location]'
    kind = EMPLOYMENT.get(job.get('employment_type') or '', (job.get('employment_type') or '').replace('_', ' ').capitalize())
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', (job.get('description') or '').strip()) if p.strip()]
    required, nice = [], []
    seen: set[str] = set()
    for req in job.get('requirements', []):
        key = ' '.join(req['label'].lower().split())
        if key in seen:
            continue
        seen.add(key)
        (required if req.get('required', True) else nice).append(req['label'].strip())
    lines = [job.get('title', '').strip(), f'Location: {location} · {kind}', '', 'About the role']
    lines += paragraphs or ['[Describe the role in 2 or 3 sentences]']
    if 'missing_responsibilities' in missing:
        lines += ['', 'What you will do', SECTIONS['responsibilities'][2]]
    lines += ['', 'Requirements']
    lines += [f'- {r}' for r in required] or ['- [Add 3 to 8 specific requirements]']
    if nice:
        lines += ['', 'Nice to have'] + [f'- {r}' for r in nice]
    if 'missing_hours' in missing:
        lines += ['', f'Working hours: {SECTIONS["hours"][2]}']
    if 'missing_pay' in missing:
        lines += ['', f'Salary: {SECTIONS["pay"][2]}']
    lines += ['', 'We welcome applicants of every gender, age and background.']
    return '\n'.join(lines).strip()
