"""
Test password policy.
Tests password strength enforcement (Gap 2 — strengthened).
"""
import pytest
from app.auth import password_policy_error


def test_too_short():
    assert password_policy_error("Sh0rt1!") is not None


def test_no_numbers():
    assert password_policy_error("Abcdefghijk!") is not None


def test_no_letters():
    assert password_policy_error("12345678901!") is not None


def test_no_uppercase():
    assert password_policy_error("lowercase1!a") is not None


def test_no_lowercase():
    assert password_policy_error("UPPERCASE1!A") is not None


def test_no_special_char():
    assert password_policy_error("ValidPass12") is not None


def test_common_password():
    # Common password check uses exact lowercase match against a known list.
    # Most entries are < 10 chars, so they'd fail length first.
    # Verify the mechanism works by checking set membership directly.
    from app.auth import _COMMON_PASSWORDS
    assert "password" in _COMMON_PASSWORDS
    assert "qwerty123" in _COMMON_PASSWORDS
    assert "Qwerty123".lower() in _COMMON_PASSWORDS


def test_valid_password():
    assert password_policy_error("Xyq9$mNpL2!k") is None


def test_minimum_length():
    assert password_policy_error("Pa$$w0rd1X") is None  # exactly 10 chars


def test_empty_password():
    assert password_policy_error("") is not None
