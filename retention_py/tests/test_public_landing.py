def test_public_landing_renders_responsive_product_sections(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Give every data record a" in response.text
    assert 'id="features"' in response.text
    assert 'id="how-it-works"' in response.text
    assert 'id="pricing"' in response.text
    assert "safedata-wordmark-lockup-dark.svg" in response.text
    assert "Start your 14-day free trial" in response.text
    assert "id=\"btn-monthly\"" in response.text
    assert "id=\"btn-yearly\"" in response.text
    assert "aria-pressed=\"true\"" in response.text
    assert "automatically disposes of data" not in response.text
    assert "Full audit proof" not in response.text


def test_public_layout_has_useful_navigation_and_single_landing_stylesheet(client):
    response = client.get("/")

    assert response.text.count("/static/css/landing.css") == 1
    assert 'href="/#features"' in response.text
    assert 'href="/#pricing"' in response.text
    assert 'aria-label="Toggle navigation"' in response.text
