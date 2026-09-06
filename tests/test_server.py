"""
Unit tests for FastAPI backend server endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from rpra.server import app

client = TestClient(app)

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "pdf_count" in data
    assert "config" in data

def test_api_graph_empty():
    response = client.get("/api/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data

def test_api_contradictions_empty():
    response = client.get("/api/contradictions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_gaps_empty():
    response = client.get("/api/gaps")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_documents_empty():
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_config_weights_valid():
    payload = {
        "objective": 0.2,
        "methodology": 0.3,
        "dataset": 0.2,
        "results_metrics": 0.2,
        "citation": 0.1
    }
    response = client.post("/api/config/weights", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["weights"]["objective"] == 0.2

def test_api_config_weights_invalid_sum():
    payload = {
        "objective": 0.5,
        "methodology": 0.5,
        "dataset": 0.5,
        "results_metrics": 0.5,
        "citation": 0.5
    }
    response = client.post("/api/config/weights", json=payload)
    assert response.status_code == 400
    assert "Weights must sum to 1.0" in response.json()["detail"]
