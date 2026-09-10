"""
Tests for Zero-Knowledge Architecture Safeguards and PII Detection on Metadata Fields.
"""
import pytest
from app.helpers import detect_pii_in_text


def test_detect_pii_clean_metadata():
    """Operational context notes must pass cleanly without flags."""
    assert detect_pii_in_text("Statutory tax audit archive 2024") == []
    assert detect_pii_in_text("Batch ingest from CRM migration ref #4401") == []
    assert detect_pii_in_text("") == []
    assert detect_pii_in_text(None) == []


def test_detect_pii_email_address():
    """Detects raw email addresses inside text notes."""
    findings = detect_pii_in_text("Customer contact: john.doe@example.com for compliance")
    assert "email_address" in findings


def test_detect_pii_credit_card():
    """Detects raw payment card numbers in text notes."""
    findings = detect_pii_in_text("Billing card 4111 2222 3333 4444 on file")
    assert "payment_card" in findings


def test_detect_pii_national_id_ssn():
    """Detects 9-digit SSN format in text notes."""
    findings = detect_pii_in_text("Beneficiary SSN 123-45-6789 verified")
    assert "national_id_ssn" in findings
