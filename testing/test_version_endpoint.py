"""
Test the version endpoint of the /version application."""
import requests


def test_version_endpoint():
    """Test the version endpoint of the /version application."""
    response = requests.get("http://localhost:8000/version", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"version": "1.0.0"}
