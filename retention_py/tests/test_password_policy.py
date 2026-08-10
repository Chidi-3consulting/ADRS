"""
Test password policy.
Tests password strength enforcement.
"""
import pytest
from app.auth import password_policy_error


def test_too_short():
    assert password_policy_error("Short1") is not None


def test_no_numbers():
    assert password_policy_error("abcdefghijk") is not None


def test_no_letters():
    assert password_policy_error("12345678901") is not None


def test_valid_password():
    assert password_policy_error("Password123!") is None


def test_minimum_length():
    assert password_policy_error("Pass12345!") is None  # exactly 10 chars


def test_empty_password():
    assert password_policy_error("") is not None
