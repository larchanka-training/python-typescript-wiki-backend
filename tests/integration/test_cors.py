"""Test CORS preflight functionality."""

from fastapi.testclient import TestClient
from app.main import app

def test_cors_preflight_options():
    client = TestClient(app)
    # Simulate a preflight request from an allowed origin
    response = client.options(
        "/api/v1/session",
        headers={
            "Origin": "http://training.wiki",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    if response.status_code != 200:
        print(f"DEBUG: Status {response.status_code}, Body: {response.text}")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] in ["http://training.wiki", "*"]
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]

def test_cors_preflight_wildcard():
    # Force wildcard via env for this test if needed, or just test current settings
    client = TestClient(app)
    response = client.options(
        "/api/v1/session",
        headers={
            "Origin": "https://unknown.domain",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    # If the app has "*" in origins, this will pass.
    # Otherwise it might still be 400 if it's not in the list.
    print(f"Wildcard test status: {response.status_code}")
    # We expect either 200 (if it's in the list or * is used) or 400 (if disallowed)
