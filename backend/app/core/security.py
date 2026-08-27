import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

PASSWORD_HASHER = PasswordHasher()


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
