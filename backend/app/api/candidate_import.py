"""Reviewed bulk import of candidates into an organization's vacancies.

Flow mirrors the jobs import: a read-only preview, an all-or-nothing commit,
and an undo that only works while nothing imported has been acted on.

Every imported row becomes an application at the ``applied`` stage for one
vacancy of the organization, so the candidate is visible to its recruiters
through the normal, organization-scoped lists. Imported accounts are created
without a usable password; the person takes the account over through the
password-reset flow. Nothing here scores, ranks or rejects anyone.
"""
import re
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from app.api.management import csrf, log, parse_file
from app.models.admin_tables import import_batches, import_rows
from app.models.schema import (
    Application, ApplicationStageHistory, CandidateProfile, Interview, Job,
    Organization, OrganizationMembership, User,
)
from app.security.dependencies import get_db, require_recruiter_for_org

router = APIRouter(prefix="/api/admin-v3", tags=["Admin Phase 3"])

# Not a valid Argon2 hash, so verify_password() can never succeed against it.
UNUSABLE_PASSWORD = "!imported-account-no-password"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
MAX_SKILLS = 30
COLUMNS = "full_name,email,phone,city,skills,job_title"


def _cell(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _normalise(rows: list[dict]) -> list[tuple[int, dict]]:
    """Lower-case headers, keep spreadsheet line numbers, drop fully blank rows."""
    cleaned = []
    for number, row in enumerate(rows, start=2):
        item = {str(key or "").strip().lower(): value for key, value in row.items()}
        if any(str(value).strip() for value in item.values() if value is not None):
            cleaned.append((number, item))
    return cleaned


def _split_skills(raw: str) -> list[str]:
    seen: dict[str, None] = {}
    for part in re.split(r"[;,|]", raw):
        skill = part.strip()
        if skill:
            seen.setdefault(skill, None)
    return list(seen)


def validate_candidate_rows(rows: list[dict], jobs: list[Job], default_job: Job | None,
                            already_applied: set[tuple[str, UUID]]):
    """Return (valid, errors). ``already_applied`` holds (email, job_id) pairs."""
    by_title: dict[str, list[Job]] = {}
    for job in jobs:
        by_title.setdefault(job.title.strip().lower(), []).append(job)
    valid, errors, seen = [], [], set()
    for number, row in _normalise(rows):
        full_name, email = _cell(row, "full_name"), _cell(row, "email").lower()
        phone, city = _cell(row, "phone"), _cell(row, "city")
        skills, job_title = _split_skills(_cell(row, "skills")), _cell(row, "job_title")
        problems = []
        if not 2 <= len(full_name) <= 160:
            problems.append("full_name must be 2-160 characters")
        if len(email) > 320 or not EMAIL_PATTERN.fullmatch(email):
            problems.append("email is not valid")
        if len(phone) > 40:
            problems.append("phone too long")
        if len(city) > 120:
            problems.append("city too long")
        if len(skills) > MAX_SKILLS or any(len(skill) > 60 for skill in skills):
            problems.append(f"skills: at most {MAX_SKILLS} items of 60 characters")
        job = None
        if job_title:
            matches = by_title.get(job_title.lower(), [])
            if not matches:
                problems.append("job_title does not match an open vacancy")
            elif len(matches) > 1:
                problems.append("job_title matches more than one vacancy")
            else:
                job = matches[0]
        elif default_job is not None:
            job = default_job
        else:
            problems.append("no vacancy: fill job_title or choose a default vacancy")
        if job is not None and not problems:
            key = (email, job.id)
            if key in seen:
                problems.append("duplicate email for the same vacancy in this file")
            elif key in already_applied:
                problems.append("this person has already applied to that vacancy")
            seen.add(key)
        if problems:
            errors.append({"row": number, "errors": problems})
        else:
            valid.append({"row": number, "full_name": full_name, "email": email, "phone": phone or None,
                          "city": city or None, "skills": skills, "job_id": job.id, "job_title": job.title})
    return valid, errors


async def _load(upload: UploadFile, organization_id: UUID, job_id: UUID | None, db: Session):
    org = db.get(Organization, organization_id)
    if not org or not org.active:
        raise HTTPException(404, "Organization not found")
    name, rows = await parse_file(upload)
    jobs = db.scalars(select(Job).where(Job.organization_id == organization_id, Job.status != "closed")).all()
    default_job = None
    if job_id is not None:
        default_job = next((job for job in jobs if job.id == job_id), None)
        if default_job is None:
            raise HTTPException(422, "Default vacancy not found, or it is closed")
    applied = db.execute(
        select(User.email, Application.job_id)
        .join(CandidateProfile, CandidateProfile.user_id == User.id)
        .join(Application, Application.candidate_id == CandidateProfile.id)
        .join(Job, Application.job_id == Job.id)
        .where(Job.organization_id == organization_id)
    ).all()
    valid, errors = validate_candidate_rows(rows, jobs, default_job, {(email, jid) for email, jid in applied})
    return name, valid, errors


def _existing_emails(db: Session, emails: list[str]) -> set[str]:
    if not emails:
        return set()
    return set(db.scalars(select(User.email).where(User.email.in_(emails))).all())


@router.post("/organizations/{organization_id}/candidate-imports/preview")
async def preview_candidates(organization_id: UUID, file: UploadFile = File(...), job_id: UUID | None = Form(None),
                             _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    name, valid, errors = await _load(file, organization_id, job_id, db)
    emails = sorted({item["email"] for item in valid})
    existing = _existing_emails(db, emails)
    sample = [{"row": item["row"], "full_name": item["full_name"], "email": item["email"],
               "city": item["city"], "job_title": item["job_title"]} for item in valid[:10]]
    return {"filename": name, "columns": COLUMNS, "valid_count": len(valid), "errors": errors, "sample": sample,
            "new_accounts": len(emails) - len(existing), "existing_accounts": len(existing)}


@router.post("/organizations/{organization_id}/candidate-imports/commit", status_code=201)
async def commit_candidates(organization_id: UUID, file: UploadFile = File(...), job_id: UUID | None = Form(None),
                            consent_confirmed: bool = Form(False), _: None = Depends(csrf),
                            actor: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    if not consent_confirmed:
        raise HTTPException(422, "Confirm that these people agreed to be considered before importing")
    name, valid, errors = await _load(file, organization_id, job_id, db)
    if errors or not valid:
        raise HTTPException(422, {"message": "Correct every row before importing", "errors": errors})

    batch_id = uuid.uuid4()
    db.execute(insert(import_batches).values(id=batch_id, organization_id=organization_id, created_by_id=actor.id,
                                             filename=name[:240], kind="candidates", status="applied"))
    users = {user.email: user for user in db.scalars(
        select(User).where(User.email.in_(sorted({item["email"] for item in valid})))).all()}
    created_accounts = 0
    for item in valid:
        user, created = users.get(item["email"]), False
        if user is None:
            user = User(email=item["email"], full_name=item["full_name"], password_hash=UNUSABLE_PASSWORD,
                        active=True, is_platform_admin=False)
            db.add(user)
            db.flush()
            users[item["email"]], created = user, True
            created_accounts += 1
        profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if profile is None:
            # An existing person's own profile is never overwritten by a spreadsheet.
            profile = CandidateProfile(user_id=user.id, phone=item["phone"], city=item["city"],
                                       skills={skill: True for skill in item["skills"]})
            db.add(profile)
            db.flush()
        application = Application(job_id=item["job_id"], candidate_id=profile.id)
        db.add(application)
        db.flush()
        db.add(ApplicationStageHistory(application_id=application.id, changed_by_id=actor.id, new_stage="applied",
                                       note=f"Imported from {name}"[:2000]))
        db.execute(insert(import_rows).values(
            id=uuid.uuid4(), batch_id=batch_id, row_number=item["row"], user_id=user.id,
            application_id=application.id, created_user=created,
            data={"email": item["email"], "job_id": str(item["job_id"])}))
    log(db, actor.id, "candidate_import.create", organization_id, batch_id,
        {"rows": len(valid), "new_accounts": created_accounts, "consent_confirmed": True})
    db.commit()
    return {"batch_id": str(batch_id), "created": len(valid), "new_accounts": created_accounts,
            "status": "applied", "stage": "applied"}


@router.post("/organizations/{organization_id}/candidate-imports/{batch_id}/undo")
def undo_candidates(organization_id: UUID, batch_id: UUID, _: None = Depends(csrf),
                    actor: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    batch = db.execute(select(import_batches.c.status, import_batches.c.kind).where(
        import_batches.c.id == batch_id, import_batches.c.organization_id == organization_id
    ).with_for_update()).first()
    if batch is None or batch.kind != "candidates":
        raise HTTPException(404, "Batch not found")
    if batch.status != "applied":
        raise HTTPException(409, "Batch already undone")
    rows = db.execute(select(import_rows.c.user_id, import_rows.c.application_id, import_rows.c.created_user)
                      .where(import_rows.c.batch_id == batch_id)).all()
    application_ids = [row.application_id for row in rows if row.application_id]
    applications = db.scalars(select(Application).where(Application.id.in_(application_ids))).all() if application_ids else []
    if len(applications) != len(application_ids) or any(a.stage != "applied" for a in applications):
        raise HTTPException(409, "Cannot undo: an imported application has been moved or removed")
    if application_ids and db.scalar(select(func.count(Interview.id)).where(Interview.application_id.in_(application_ids))):
        raise HTTPException(409, "Cannot undo: an imported application has an interview")

    if application_ids:
        db.execute(delete(ApplicationStageHistory).where(ApplicationStageHistory.application_id.in_(application_ids)))
        db.execute(delete(Application).where(Application.id.in_(application_ids)))
    removed_accounts = 0
    for user_id in {row.user_id for row in rows if row.created_user and row.user_id}:
        user = db.get(User, user_id)
        # Keep any account its owner has taken over or that gained another role or application.
        if not user or user.password_hash != UNUSABLE_PASSWORD or user.is_platform_admin:
            continue
        if db.scalar(select(OrganizationMembership.id).where(OrganizationMembership.user_id == user_id).limit(1)):
            continue
        profile_ids = db.scalars(select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)).all()
        if profile_ids and db.scalar(select(Application.id).where(Application.candidate_id.in_(profile_ids)).limit(1)):
            continue
        db.execute(update(import_rows).where(import_rows.c.user_id == user_id).values(user_id=None, data={}))
        db.execute(delete(CandidateProfile).where(CandidateProfile.user_id == user_id))
        db.execute(delete(User).where(User.id == user_id))
        removed_accounts += 1
    db.execute(update(import_rows).where(import_rows.c.batch_id == batch_id).values(application_id=None))
    db.execute(update(import_batches).where(import_batches.c.id == batch_id).values(status="undone"))
    log(db, actor.id, "candidate_import.undo", organization_id, batch_id,
        {"removed_applications": len(application_ids), "removed_accounts": removed_accounts})
    db.commit()
    return {"undone": len(application_ids), "removed_accounts": removed_accounts}
