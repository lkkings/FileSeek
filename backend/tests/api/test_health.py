import pytest
from fastapi.testclient import TestClient

def test_health_check_does_not_need_token(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"]["status"] == "ok"
    assert "version" in json_data["data"]

def test_health_check_with_token(auth_client: TestClient):
    response = auth_client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"]["status"] == "ok"
