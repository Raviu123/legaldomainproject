"""Unit tests for the backend API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Module-scoped client fixture that triggers FastAPI startup/shutdown lifespan events."""
    with TestClient(app) as c:
        yield c


def test_health_check(client) -> None:
    """Tests the health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    
    # Test trailing slash redirect or matching
    response_slash = client.get("/api/v1/health/")
    assert response_slash.status_code == 200


def test_list_ingested_laws(client) -> None:
    """Tests the list_ingested_laws endpoint."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    laws = response.json()
    assert isinstance(laws, list)
    assert "GDPR" in laws


def test_get_law_documents_gdpr(client) -> None:
    """Tests the get_law_documents endpoint for GDPR."""
    response = client.get("/api/v1/documents/GDPR")
    assert response.status_code == 200
    documents = response.json()
    assert isinstance(documents, list)
    assert len(documents) > 0
    first_doc = documents[0]
    assert "id" in first_doc
    assert "law" in first_doc
    assert first_doc["law"] == "GDPR"


def test_graph_data_endpoint(client) -> None:
    """Tests the graph data endpoint."""
    response = client.get("/api/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_ask_question_endpoint(client) -> None:
    """Tests the ask question endpoint."""
    # Test valid request
    response = client.post("/api/v1/ask", json={"question": "What is personal data?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "confidence" in data
    assert "related_laws" in data
    assert isinstance(data["sources"], list)
    
    # Test empty question validation (whitespace string passes length constraint but fails strip check)
    response_whitespace = client.post("/api/v1/ask", json={"question": "     "})
    assert response_whitespace.status_code == 400

    # Test short question validation (Pydantic min_length=5 validation failure)
    response_short = client.post("/api/v1/ask", json={"question": ""})
    assert response_short.status_code == 422
