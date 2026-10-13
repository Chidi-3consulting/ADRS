def test_safedata_content_page_uses_standalone_product_branding(client):
    response = client.get("/safedata")

    assert response.status_code == 200
    assert "SafeData by 3Consulting" in response.text
    assert "Keep what you must. Release what you should." in response.text
    assert "We govern your data without hoarding it." in response.text
    assert "Governance support—not legal advice." in response.text
    assert "Open SafeData" in response.text
    assert "FraudGuard" not in response.text
    assert "company homepage" not in response.text.lower()
