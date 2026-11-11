"""Idempotent official role seed; does not create vacancies."""
from app.security.dependencies import session_factory
from app.models.categories import seed_official_roles


def main():
    with session_factory()() as db:
        count = seed_official_roles(db)
        db.commit()
    print(f"Official job categories: seeded {count} missing role(s).")


if __name__ == "__main__":
    main()
