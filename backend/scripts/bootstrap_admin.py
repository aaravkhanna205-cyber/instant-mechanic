"""One-time interactive platform-admin bootstrap. Never accepts passwords as CLI args."""
import argparse
import getpass
from sqlalchemy import select
from app.security.dependencies import session_factory
from app.security.passwords import hash_password
from app.models.schema import User


def main():
    parser = argparse.ArgumentParser(description="Create the first platform administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    email = args.email.strip().lower()
    if "@" not in email or len(email) > 320 or len(args.name.strip()) < 2:
        raise SystemExit("Invalid email or name")
    factory = session_factory()
    with factory() as db:
        if db.scalar(select(User.id).where(User.is_platform_admin.is_(True))) is not None:
            raise SystemExit("A platform admin already exists. No changes made.")
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit("Email is registered. No privileges changed.")
        print("Creating FIRST platform administrator for:", email)
        if input("Type CREATE-ADMIN to confirm: ").strip() != "CREATE-ADMIN":
            raise SystemExit("Cancelled")
        password = getpass.getpass("New password (12-128 chars): ")
        again = getpass.getpass("Confirm password: ")
        if password != again:
            raise SystemExit("Passwords do not match")
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        db.add(User(email=email, full_name=args.name.strip(), password_hash=password_hash,
                    is_platform_admin=True, active=True))
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        print("SUCCESS: First administrator created. Keep credentials private.")


if __name__ == "__main__":
    main()
