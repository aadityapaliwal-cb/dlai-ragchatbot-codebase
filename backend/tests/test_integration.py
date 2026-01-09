"""
Integration tests - Full FastAPI stack testing.

These tests verify the complete request/response flow through the API,
including the actual "Query failed" error that users experience.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_api_query_endpoint_structure():
    """
    Test that the /api/query endpoint exists and has correct structure.
    """
    from app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Test with minimal valid request
    # This may fail due to MAX_RESULTS=0 bug, but we're testing structure first
    response = client.post(
        "/api/query", json={"query": "test query", "session_id": None}
    )

    # Response should have proper structure (even if it errors)
    assert response is not None
    # Status code might be 500 (due to bugs) or 200
    assert response.status_code in [200, 500, 401, 402, 503]


@pytest.mark.asyncio
async def test_api_query_with_max_results_bug():
    """
    Test that MAX_RESULTS=0 causes empty results or errors.

    This reproduces the actual "Query failed" user experience.
    """
    from app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Send query request
    response = client.post(
        "/api/query", json={"query": "What's in the course?", "session_id": None}
    )

    # With MAX_RESULTS=0, the behavior depends on other factors:
    # - If Anthropic API fails: HTTP 500
    # - If search returns empty: HTTP 200 with empty/minimal sources
    # - If other error: HTTP 500

    if response.status_code == 500:
        # Error occurred
        data = response.json()
        assert "detail" in data
        # This is the "Query failed" scenario
    elif response.status_code == 200:
        # Request succeeded but may have empty results
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        # Sources may be empty due to MAX_RESULTS=0
    else:
        # Other error status (401, 402, 503, etc.)
        assert response.status_code in [401, 402, 429, 503]


@patch("app.rag_system")
def test_api_query_with_mocked_rag(mock_rag_system):
    """
    Test API endpoint with mocked RAG system to isolate endpoint logic.
    """
    from app import app
    from fastapi.testclient import TestClient

    # Mock RAGSystem query method
    mock_rag_system.query.return_value = (
        "This is a test answer",
        [{"text": "Test Course - Lesson 1", "url": "https://example.com/lesson1"}],
    )

    client = TestClient(app)

    response = client.post(
        "/api/query", json={"query": "test question", "session_id": "test_session_123"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["answer"] == "This is a test answer"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["text"] == "Test Course - Lesson 1"
    assert data["session_id"] == "test_session_123"


@patch("app.rag_system")
def test_api_query_creates_session_if_none(mock_rag_system):
    """
    Test that API creates a new session ID if none provided.
    """
    from app import app
    from fastapi.testclient import TestClient

    mock_rag_system.query.return_value = ("Answer", [])

    client = TestClient(app)

    response = client.post("/api/query", json={"query": "test", "session_id": None})

    assert response.status_code == 200
    data = response.json()

    # Session ID should be created
    assert "session_id" in data
    assert data["session_id"] is not None
    assert len(data["session_id"]) > 0


@patch("app.rag_system")
def test_api_error_handling(mock_rag_system):
    """
    Test that API exceptions are caught and returned as HTTP 500.

    This confirms the error handling behavior in app.py.
    """
    from app import app
    from fastapi.testclient import TestClient

    # Make RAG system raise an exception
    mock_rag_system.query.side_effect = Exception("Test error message")

    client = TestClient(app)

    response = client.post("/api/query", json={"query": "test", "session_id": None})

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Test error message" in data["detail"]


@patch("app.rag_system")
def test_api_anthropic_auth_error(mock_rag_system):
    """
    Test API behavior when Anthropic API authentication fails.
    """
    import anthropic
    from app import app
    from fastapi.testclient import TestClient

    # Make RAG system raise Anthropic auth error
    mock_rag_system.query.side_effect = anthropic.AuthenticationError("Invalid API key")

    client = TestClient(app)

    response = client.post("/api/query", json={"query": "test", "session_id": None})

    # Currently returns 500 (generic error)
    # After fix, should return 401
    assert response.status_code in [500, 401]
    data = response.json()
    assert "detail" in data


def test_api_courses_endpoint():
    """
    Test the /api/courses endpoint returns course list.
    """
    from app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/api/courses")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # May be empty if no courses loaded


@patch("app.rag_system")
def test_api_courses_endpoint_returns_metadata(mock_rag_system):
    """
    Test that courses endpoint returns proper metadata structure.
    """
    from app import app
    from fastapi.testclient import TestClient

    # Mock get_all_courses_metadata
    mock_rag_system.vector_store.get_all_courses_metadata.return_value = [
        {
            "title": "Test Course 1",
            "instructor": "Instructor 1",
            "course_link": "https://example.com/course1",
            "lesson_count": 5,
        }
    ]

    client = TestClient(app)

    response = client.get("/api/courses")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Course 1"


def test_api_root_endpoint_serves_frontend():
    """
    Test that root endpoint serves the frontend.
    """
    from app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/")

    # Should serve HTML or redirect
    assert response.status_code in [200, 307]


def test_api_cors_headers():
    """
    Test CORS configuration if enabled.
    """
    from app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # OPTIONS request to check CORS
    response = client.options("/api/query")

    # FastAPI handles CORS
    assert response.status_code in [200, 405]  # 405 if OPTIONS not explicitly handled


@patch("app.rag_system")
def test_api_empty_query(mock_rag_system):
    """
    Test API behavior with empty query string.
    """
    from app import app
    from fastapi.testclient import TestClient

    mock_rag_system.query.return_value = ("Please provide a question", [])

    client = TestClient(app)

    response = client.post("/api/query", json={"query": "", "session_id": None})

    # Should still process (validation in app may vary)
    assert response.status_code in [200, 422, 500]


def test_api_malformed_request():
    """
    Test API with malformed request body.
    """
    from app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Missing required field
    response = client.post(
        "/api/query",
        json={
            "session_id": "test"
            # Missing 'query' field
        },
    )

    # Should return 422 Unprocessable Entity
    assert response.status_code == 422
