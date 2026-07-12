"""Unit tests for the backend API endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    """Tests the health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    
    # Test trailing slash redirect or matching
    response_slash = client.get("/api/v1/health/")
    assert response_slash.status_code == 200


def test_list_ingested_laws() -> None:
    """Tests the list_ingested_laws endpoint."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    laws = response.json()
    assert isinstance(laws, list)
    assert "GDPR" in laws


def test_get_law_documents_gdpr() -> None:
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


def test_graph_data_endpoint() -> None:
    """Tests the graph data endpoint."""
    response = client.get("/api/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_ask_question_endpoint() -> None:
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
    
    # Test empty question validation
    response_empty = client.post("/api/v1/ask", json={"question": ""})
    assert response_empty.status_code == 400
