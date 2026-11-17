"""Pipeline analysis for the Recruitment Analytics agent. Read-only, aggregate counts only.

No candidate names, no per-person judgement: it describes where the hiring process slows down.
"""
STAGE_ORDER = ['applied', 'screening', 'shortlisted', 'trade_test', 'interview', 'offer', 'hired', 'rejected', 'withdrawn']
CLOSED_STAGES = {'hired', 'rejected', 'withdrawn'}
STUCK_DAYS = 7


def stage_label(stage: str) -> str:
    return stage.replace('_', ' ').capitalize()


def _change(current: int, previous: int) -> str:
    if previous == 0:
        return 'new activity' if current else 'no change'
    pct = round((current - previous) * 100 / previous)
    return f'{pct:+d}%'


def findings(snapshot: dict) -> list[dict]:
    """Bottlenecks and changes worth a recruiter's attention, most important first."""
    out: list[dict] = []
    days = snapshot['days']
    cur, prev = snapshot['applications_current'], snapshot['applications_previous']
    if cur != prev:
        movers = sorted(snapshot['jobs'], key=lambda j: abs(j['current'] - j['previous']), reverse=True)
        movers = [j for j in movers if j['current'] != j['previous']][:3]
        detail = '; '.join(f"{j['title']} {j['previous']} to {j['current']}" for j in movers)
        out.append({'kind': 'volume', 'priority': 2,
                    'text': f'Applications in the last {days} days: {cur}, against {prev} in the {days} days before ({_change(cur, prev)}).'
                            + (f' Biggest changes by job: {detail}.' if detail else '')})
    stuck = snapshot['stuck_by_stage']
    for stage in STAGE_ORDER:
        count = stuck.get(stage, 0)
        if count:
            out.append({'kind': 'stuck', 'priority': 1,
                        'text': f'{count} application(s) have waited more than {STUCK_DAYS} days in {stage_label(stage)} with no stage change.'})
    if snapshot['interviews_overdue']:
        out.append({'kind': 'interviews', 'priority': 1,
                    'text': f"{snapshot['interviews_overdue']} interview(s) are past their scheduled time but not completed or cancelled."})
    if snapshot['interviews_declined']:
        out.append({'kind': 'interviews', 'priority': 3,
                    'text': f"{snapshot['interviews_declined']} interview invitation(s) were declined by candidates in this period."})
    for job in snapshot['jobs']:
        if job['status'] == 'published' and job['current'] == 0:
            out.append({'kind': 'no_applicants', 'priority': 2,
                        'text': f"Published job \"{job['title']}\" had no applications in the last {days} days. Check where it is advertised and its description."})
    funnel = snapshot['open_by_stage']
    early = funnel.get('applied', 0) + funnel.get('screening', 0)
    later = sum(funnel.get(s, 0) for s in ('shortlisted', 'trade_test', 'interview', 'offer'))
    if early >= 10 and later == 0:
        out.append({'kind': 'funnel', 'priority': 1,
                    'text': f'{early} open applications are in Applied or Screening and none have moved further. Screening may be the bottleneck.'})
    if not out:
        out.append({'kind': 'none', 'priority': 3, 'text': 'No bottlenecks found for this period.'})
    return sorted(out, key=lambda f: f['priority'])


def report(snapshot: dict, items: list[dict]) -> str:
    funnel = snapshot['open_by_stage']
    stages = ', '.join(f'{stage_label(s)} {funnel[s]}' for s in STAGE_ORDER if funnel.get(s))
    lines = [f"Recruitment report for the last {snapshot['days']} days.",
             f"{snapshot['applications_current']} new applications across {len(snapshot['jobs'])} jobs.",
             f'Open applications by stage: {stages}.' if stages else 'There are no open applications.']
    lines += [item['text'] for item in items]
    lines.append('Counts only; no individual candidate is assessed.')
    return ' '.join(lines)
