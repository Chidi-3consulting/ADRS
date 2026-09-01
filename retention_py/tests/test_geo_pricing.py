"""
Tests for Geo-Location Detection and Dynamic Multi-Currency Pricing.
"""
import pytest
from app.helpers import (
    detect_visitor_currency, get_visitor_country, get_localized_pricing,
    CURRENCY_DATA, COUNTRY_TO_CURRENCY,
)


class MockRequest:
    def __init__(self, headers=None, query_params=None):
        self.headers = headers or {}
        self.query_params = query_params or {}


def test_detect_visitor_currency():
    assert detect_visitor_currency("NG")["code"] == "NGN"
    assert detect_visitor_currency("ZA")["code"] == "ZAR"
    assert detect_visitor_currency("GB")["code"] == "GBP"
    assert detect_visitor_currency("FR")["code"] == "EUR"
    assert detect_visitor_currency("KE")["code"] == "KES"
    assert detect_visitor_currency("GH")["code"] == "GHS"
    assert detect_visitor_currency("US")["code"] == "USD"
    assert detect_visitor_currency("UNKNOWN")["code"] == "USD"


def test_get_visitor_country_from_cloudflare_header():
    req = MockRequest(headers={"CF-IPCountry": "ZA"})
    assert get_visitor_country(req) == "ZA"


def test_get_visitor_country_from_query_override():
    req = MockRequest(query_params={"country": "NG"})
    assert get_visitor_country(req) == "NG"


def test_get_localized_pricing_calculation():
    # South Africa (ZAR)
    za_pricing = get_localized_pricing("ZA")
    assert za_pricing["currency_code"] == "ZAR"
    assert za_pricing["currency_symbol"] == "R"
    assert za_pricing["monthly"]["amount_usd"] == 40
    assert za_pricing["monthly"]["amount_local"] == int(round(40 * 18.5))
    assert "$40/mo" in za_pricing["monthly"]["full_display"]
    assert "R" in za_pricing["monthly"]["full_display"]

    # Nigeria (NGN)
    ng_pricing = get_localized_pricing("NG")
    assert ng_pricing["currency_code"] == "NGN"
    assert ng_pricing["currency_symbol"] == "₦"
    assert ng_pricing["yearly"]["amount_usd"] == 399
    assert ng_pricing["yearly"]["amount_local"] == int(round(399 * 1500.0))
    assert "$399/yr" in ng_pricing["yearly"]["full_display"]
    assert "₦" in ng_pricing["yearly"]["full_display"]

    # US (USD)
    us_pricing = get_localized_pricing("US")
    assert us_pricing["is_usd"] is True
    assert us_pricing["monthly"]["full_display"] == "$40/mo"
