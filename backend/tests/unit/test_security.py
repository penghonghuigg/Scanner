import pytest


def test_argon2id_hash_is_salted_and_verifiable() -> None:
    try:
        from app.core.security import hash_password, verify_password
    except ModuleNotFoundError:
        pytest.fail("密码安全工具尚未实现")

    first = hash_password("a-secure-password")
    second = hash_password("a-secure-password")

    assert first.startswith("$argon2id$")
    assert first != second
    assert "a-secure-password" not in first
    assert verify_password(first, "a-secure-password") is True
    assert verify_password(first, "wrong-password") is False


def test_session_tokens_have_entropy_and_stable_sha256_digest() -> None:
    from app.core.security import digest_token, generate_token

    first = generate_token()
    second = generate_token()

    assert first != second
    assert len(first) >= 43
    assert len(digest_token(first)) == 64
    assert digest_token(first) == digest_token(first)
    assert digest_token(first) != digest_token(second)
