"""Fill an EMPTY test database for the browser tests (frontend/e2e). Never run it on the real database.

It refuses unless E2E_SEED=YES and the database name contains "e2e" or "test".
Creates: organization Instant Mechanic, an HR manager, a hiring manager and one published job.
Password for both staff accounts comes from E2E_PASSWORD.
"""
import os
from sqlalchemy import select
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.models.categories import seed_official_roles
from app.models.schema import Job, JobCategory, Organization, OrganizationMembership, User
from app.security.dependencies import session_factory
from app.security.passwords import hash_password

STAFF = (('hr.e2e@instantmechanic.in', 'Neeraj (test)', 'hr_manager'),
         ('hiring.e2e@instantmechanic.in', 'Aarav Khanna (test)', 'hiring_manager'))


def main() -> None:
    database = make_url(settings.database_url).database or ''
    if os.getenv('E2E_SEED') != 'YES' or not any(word in database.lower() for word in ('e2e', 'test')):
        raise SystemExit('Refused: set E2E_SEED=YES and use a database whose name contains "e2e" or "test".')
    password = os.getenv('E2E_PASSWORD', '')
    if len(password) < 12:
        raise SystemExit('Set E2E_PASSWORD (12+ characters).')
    with session_factory()() as db:
        if db.scalar(select(JobCategory.slug).limit(1)) is None:
            seed_official_roles(db)
        org = db.scalar(select(Organization).where(Organization.slug == 'instant-mechanic'))
        if org is None:
            org = Organization(name='Instant Mechanic', slug='instant-mechanic')
            db.add(org)
            db.flush()
        for email, name, role in STAFF:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, full_name=name, password_hash=hash_password(password))
                db.add(user)
                db.flush()
                db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role=role))
        if db.scalar(select(Job.id).where(Job.organization_id == org.id)) is None:
            category = db.scalar(select(JobCategory.slug).order_by(JobCategory.slug).limit(1))
            db.add(Job(organization_id=org.id, category_slug=category, title='Roadside Mechanic (E2E)',
                       description='Fix cars at the roadside across Delhi NCR.', location='Delhi NCR',
                       status='published'))
        db.commit()
    print('E2E data ready.')


if __name__ == '__main__':
    main()
