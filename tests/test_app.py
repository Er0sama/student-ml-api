import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/health")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "wrong"
    assert data["application"] == "student-ml-api"
    assert data["version"] == open("VERSION").read().strip()


def test_predict_success(client):
    response = client.post("/predict", json={"value": 10})

    assert response.status_code == 200
    assert response.get_json() == {"input": 10, "prediction": 20}


def test_predict_missing_input(client):
    response = client.post("/predict", json={})

    assert response.status_code == 400
    assert "value" in response.get_json()["error"]


def test_predict_invalid_input(client):
    response = client.post("/predict", json={"value": "ten"})

    assert response.status_code == 400
    assert "number" in response.get_json()["error"]
