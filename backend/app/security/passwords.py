"""Password storage: Argon2id; no reversible passwords."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# Make invalid users take a comparable Argon2 verification path.
_dummy_hash = _hasher.hash("nonexistent_account_placeholder_password")


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Password must be 12-128 characters")
    return _hasher.hash(password)


def verify_password(stored: str | None, supplied: str) -> bool:
    try:
        return _hasher.verify(stored or _dummy_hash, supplied)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError, ValueError):
        return False
