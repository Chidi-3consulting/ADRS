"""
Test 2FA (TOTP).
Tests TOTP generation, verification, recovery codes, and URI generation.
"""
import pytest
from app.helpers import (
    totp_generate_secret, totp_code, totp_verify, totp_uri,
    generate_recovery_codes, consume_recovery_code,
)


def test_totp_secret_format():
    """Secret should be a base32-encoded string."""
    secret = totp_generate_secret()
    assert len(secret) >= 20
    assert secret.isalnum()


def test_totp_code_format():
    """TOTP code should be 6 digits, zero-padded."""
    secret = totp_generate_secret()
    code = totp_code(secret)
    assert len(code) == 6
    assert code.isdigit()


def test_totp_verify_current():
    """Current code should verify successfully."""
    secret = totp_generate_secret()
    code = totp_code(secret)
    assert totp_verify(secret, code) is True


def test_totp_verify_wrong_code():
    """Wrong code should fail verification."""
    secret = totp_generate_secret()
    assert totp_verify(secret, "000000") is False or totp_verify(secret, "999999") is False


def test_totp_uri():
    """URI should be properly formatted for QR code generation."""
    secret = totp_generate_secret()
    uri = totp_uri(secret, "user@example.com", "SafeData")
    assert uri.startswith("otpauth://totp/")
    assert "SafeData" in uri
    assert secret in uri


def test_recovery_codes_generation():
    """Should generate 8 unique recovery codes with hashes."""
    result = generate_recovery_codes(8)
    assert len(result["plain"]) == 8
    assert len(result["hashed"]) == 8
    assert len(set(result["plain"])) == 8  # All unique


def test_consume_recovery_code():
    """Valid code should be consumed; invalid should return None."""
    result = generate_recovery_codes(3)
    code = result["plain"][0]

    remaining = consume_recovery_code(result["hashed"], code)
    assert remaining is not None
    assert len(remaining) == 2

    # Invalid code
    assert consume_recovery_code(result["hashed"], "INVALID-CODE") is None
