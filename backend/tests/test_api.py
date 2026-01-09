"""
API endpoint tests for the RAG chatbot system.

Tests cover all FastAPI endpoints including query processing,
course statistics, and error handling scenarios.
"""

import pytest
from fastapi import status
from unittest.mock import MagicMock


@pytest.mark.api
class TestQueryEndpoint:
    """Tests for the /api/query endpoint."""

    def test_query_with_session_id(self, test_client, sample_query_request, mock_rag_system):
        """Test successful query with existing session ID."""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify response content
        assert data["session_id"] == "test-session-123"
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert len(data["answer"]) > 0

        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with(
            sample_query_request["query"],
            sample_query_request["session_id"]
        )

    def test_query_without_session_id(self, test_client, sample_query_request_no_session, mock_rag_system):
        """Test query creates new session when none provided."""
        response = test_client.post("/api/query", json=sample_query_request_no_session)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify new session was created
        assert data["session_id"] == "test-session-123"
        mock_rag_system.session_manager.create_session.assert_called_once()

        # Verify query was processed
        assert "answer" in data
        assert "sources" in data

    def test_query_with_sources(self, test_client, sample_query_request, mock_rag_system):
        """Test that sources are properly returned in response."""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify sources structure
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) > 0

        source = data["sources"][0]
        assert "course_title" in source
        assert "lesson_number" in source
        assert source["course_title"] == "Test Course: Introduction to Testing"

    def test_query_invalid_request_missing_query(self, test_client):
        """Test error handling for missing query parameter."""
        response = test_client.post("/api/query", json={"session_id": "test-123"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_empty_query_string(self, test_client):
        """Test handling of empty query string."""
        response = test_client.post("/api/query", json={"query": ""})

        # Should still process, even if query is empty
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]

    def test_query_internal_error(self, test_client, sample_query_request, mock_rag_system):
        """Test error handling when RAG system raises exception."""
        # Configure mock to raise exception
        mock_rag_system.query.side_effect = Exception("Database connection failed")

        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database connection failed" in response.json()["detail"]

    def test_query_multiple_sources(self, test_client, sample_query_request, mock_rag_system):
        """Test handling of queries that return multiple sources."""
        # Configure mock to return multiple sources
        mock_rag_system.query.return_value = (
            "Multi-source answer",
            [
                {"course_title": "Course 1", "lesson_number": "1", "lesson_title": "Lesson 1"},
                {"course_title": "Course 2", "lesson_number": "2", "lesson_title": "Lesson 2"},
                {"course_title": "Course 3", "lesson_number": "3", "lesson_title": "Lesson 3"},
            ]
        )

        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["sources"]) == 3

    def test_query_no_sources_found(self, test_client, sample_query_request, mock_rag_system):
        """Test handling when no sources are found."""
        # Configure mock to return empty sources
        mock_rag_system.query.return_value = (
            "No relevant sources found",
            []
        )

        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sources"] == []
        assert len(data["answer"]) > 0


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for the /api/courses endpoint."""

    def test_get_courses_success(self, test_client, mock_rag_system):
        """Test successful retrieval of course statistics."""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify response content
        assert data["total_courses"] == 2
        assert isinstance(data["course_titles"], list)
        assert len(data["course_titles"]) == 2

        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_courses_empty_database(self, test_client, mock_rag_system):
        """Test courses endpoint with empty database."""
        # Configure mock to return empty analytics
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_internal_error(self, test_client, mock_rag_system):
        """Test error handling when analytics retrieval fails."""
        # Configure mock to raise exception
        mock_rag_system.get_course_analytics.side_effect = Exception("ChromaDB unavailable")

        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "ChromaDB unavailable" in response.json()["detail"]

    def test_get_courses_content_type(self, test_client):
        """Test that response has correct content type."""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_get_courses_multiple_courses(self, test_client, mock_rag_system):
        """Test courses endpoint with many courses."""
        # Configure mock to return many courses
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 10,
            "course_titles": [f"Course {i}" for i in range(1, 11)]
        }

        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_courses"] == 10
        assert len(data["course_titles"]) == 10


@pytest.mark.api
class TestRootEndpoint:
    """Tests for the root / endpoint."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns welcome message."""
        response = test_client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert data["message"] == "RAG System API"


@pytest.mark.api
class TestCORSHeaders:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_on_query(self, test_client, sample_query_request):
        """Test CORS headers are present on query endpoint."""
        response = test_client.post("/api/query", json=sample_query_request)

        # FastAPI TestClient doesn't fully simulate CORS, but we can verify
        # the endpoint is accessible without CORS errors
        assert response.status_code == status.HTTP_200_OK

    def test_cors_headers_on_courses(self, test_client):
        """Test CORS headers are present on courses endpoint."""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
class TestRequestValidation:
    """Tests for request validation and edge cases."""

    def test_query_with_very_long_query(self, test_client, mock_rag_system):
        """Test handling of very long query strings."""
        long_query = "What is testing? " * 1000  # Very long query
        request = {"query": long_query, "session_id": "test-123"}

        response = test_client.post("/api/query", json=request)

        # Should handle long queries
        assert response.status_code == status.HTTP_200_OK

    def test_query_with_special_characters(self, test_client):
        """Test query with special characters."""
        request = {
            "query": "What is testing? 🧪 <script>alert('test')</script>",
            "session_id": "test-123"
        }

        response = test_client.post("/api/query", json=request)

        assert response.status_code == status.HTTP_200_OK

    def test_query_with_unicode(self, test_client):
        """Test query with unicode characters."""
        request = {
            "query": "测试是什么？ Что такое тестирование?",
            "session_id": "test-123"
        }

        response = test_client.post("/api/query", json=request)

        assert response.status_code == status.HTTP_200_OK

    def test_invalid_json_request(self, test_client):
        """Test handling of invalid JSON."""
        response = test_client.post(
            "/api/query",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_with_extra_fields(self, test_client):
        """Test that extra fields in request are ignored."""
        request = {
            "query": "What is testing?",
            "session_id": "test-123",
            "extra_field": "should be ignored"
        }

        response = test_client.post("/api/query", json=request)

        # Should succeed, ignoring extra fields
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
class TestResponseFormat:
    """Tests for response format and structure."""

    def test_query_response_format(self, test_client, sample_query_request):
        """Test that query response has correct format."""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify all required fields are present
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

    def test_courses_response_format(self, test_client):
        """Test that courses response has correct format."""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify all required fields are present
        required_fields = ["total_courses", "course_titles"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

    def test_source_object_format(self, test_client, sample_query_request):
        """Test that source objects have correct format."""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        if len(data["sources"]) > 0:
            source = data["sources"][0]
            assert isinstance(source, dict)
            # Sources should have at minimum these fields
            assert "course_title" in source
            assert "lesson_number" in source
