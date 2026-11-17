"""Plain-language messages for candidates. Short, polite, no jargon."""
from datetime import datetime
from zoneinfo import ZoneInfo

STAGE_MESSAGES = {
    'screening': 'Your application for {job} is now being reviewed by our team.',
    'shortlisted': 'Good news: you have been shortlisted for {job}. We will contact you about the next step.',
    'trade_test': 'Next step for {job}: a short practical test. We will share the date and place with you.',
    'interview': 'Next step for {job}: an interview. You will see the time in your portal.',
    'offer': 'Good news: we would like to offer you the job of {job}. We will contact you with the details.',
    'hired': 'Welcome to Instant Mechanic! You have been selected for {job}.',
    'rejected': 'Thank you for applying for {job}. We will not be moving forward with your application this time. '
                'You are welcome to apply for other jobs.',
    'withdrawn': 'Your application for {job} has been withdrawn.',
}

# What each stage means, shown in the candidate portal.
STAGE_HELP = {
    'applied': 'We have received your application.',
    'screening': 'Our team is reading your application and resume.',
    'shortlisted': 'You are on the shortlist. We will contact you soon.',
    'trade_test': 'A short practical test of your skills.',
    'interview': 'A conversation with our team.',
    'offer': 'We would like to offer you the job.',
    'hired': 'You have joined Instant Mechanic.',
    'rejected': 'This application has closed.',
    'withdrawn': 'This application was withdrawn.',
}


def stage_message(stage: str, job_title: str) -> str | None:
    template = STAGE_MESSAGES.get(stage)
    return template.format(job=job_title) if template else None


def when(value: datetime | None, tz_name: str | None) -> str:
    if value is None:
        return 'a time we will confirm'
    try:
        zone = ZoneInfo(tz_name or 'Asia/Kolkata')
    except Exception:  # noqa: BLE001 - unknown zone names fall back to India time
        zone = ZoneInfo('Asia/Kolkata')
    local = value.astimezone(zone) if value.tzinfo else value.replace(tzinfo=ZoneInfo('UTC')).astimezone(zone)
    return local.strftime('%d %b %Y, %I:%M %p').lstrip('0') + f' ({zone.key})'
