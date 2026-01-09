"""
Shared test fixtures and configuration for RAG chatbot tests.

This module provides centralized mocks for ChromaDB and Anthropic API
to enable isolated unit and integration testing.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, Mock
from typing import Any, Dict, List

# Add backend to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import Config
from models import Course, Lesson, CourseChunk
from vector_store import SearchResults


@pytest.fixture
def mock_chroma_collection():
    """
    Mock ChromaDB collection with configurable query results.

    Returns a MagicMock that simulates ChromaDB collection behavior.
    Default response includes sample course content.
    """
    mock = MagicMock()
    mock.query.return_value = {
        'documents': [['Sample content from lesson about testing']],
        'metadatas': [[{
            'course_title': 'Test Course: Introduction to Testing',
            'lesson_number': 1,
            'chunk_index': 0
        }]],
        'distances': [[0.5]]
    }
    mock.get.return_value = {
        'ids': ['Test Course: Introduction to Testing'],
        'metadatas': [{
            'title': 'Test Course: Introduction to Testing',
            'instructor': 'Test Instructor',
            'course_link': 'https://example.com/course',
            'lessons_json': '[{"lesson_number": 1, "lesson_title": "Getting Started", "lesson_link": "https://example.com/lesson1"}]',
            'lesson_count': 1
        }]
    }
    return mock


@pytest.fixture
def mock_anthropic_client():
    """
    Mock Anthropic client for API testing.

    Returns a MagicMock that simulates successful text responses from Claude.
    """
    mock_client = MagicMock()

    # Mock successful text response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is a test response from Claude", type="text")]
    mock_response.stop_reason = "end_turn"

    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_tool_use_response():
    """
    Mock Anthropic response with tool use.

    Simulates Claude requesting to use the search_course_content tool.
    """
    mock_response = MagicMock()

    # Mock tool use content block
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "test_tool_id_123"
    tool_block.input = {"query": "test query about courses"}

    mock_response.content = [tool_block]
    mock_response.stop_reason = "tool_use"

    return mock_response


@pytest.fixture
def test_config():
    """
    Test configuration with safe defaults.

    Overrides the broken MAX_RESULTS=0 with a valid value.
    Uses in-memory ChromaDB for faster testing.
    """
    config = Config()
    config.MAX_RESULTS = 5  # Override the broken value
    config.ANTHROPIC_API_KEY = "test-api-key-12345"
    config.CHROMA_PATH = ":memory:"  # Use in-memory for tests
    config.MAX_HISTORY = 2
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    return config


@pytest.fixture
def sample_course():
    """
    Sample course for testing.

    Provides a Course object with realistic test data.
    """
    return Course(
        title="Test Course: Introduction to Testing",
        instructor="Test Instructor",
        course_link="https://example.com/course",
        lessons=[
            Lesson(
                lesson_number=1,
                title="Getting Started with Testing",
                lesson_link="https://example.com/lesson1"
            ),
            Lesson(
                lesson_number=2,
                title="Advanced Testing Techniques",
                lesson_link="https://example.com/lesson2"
            ),
        ]
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    """
    Sample course chunks for testing VectorStore.

    Returns a list of CourseChunk objects for the sample course.
    """
    return [
        CourseChunk(
            content="This is lesson 1 content about testing fundamentals. We cover basic concepts.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="This is more content from lesson 1 about unit testing and best practices.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=1
        ),
        CourseChunk(
            content="Lesson 2 covers advanced topics like integration testing and mocking.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=0
        ),
    ]


@pytest.fixture
def empty_search_results():
    """
    Empty SearchResults for testing error conditions.
    """
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )


@pytest.fixture
def search_results_with_error():
    """
    SearchResults with error message for testing error handling.
    """
    return SearchResults.empty("Search error: MAX_RESULTS is 0")


@pytest.fixture
def valid_search_results():
    """
    Valid SearchResults with sample data.
    """
    return SearchResults(
        documents=["Sample content about testing"],
        metadata=[{
            'course_title': 'Test Course: Introduction to Testing',
            'lesson_number': 1,
            'chunk_index': 0
        }],
        distances=[0.5]
    )


# API Testing Fixtures

@pytest.fixture
def mock_rag_system():
    """
    Mock RAG system for API testing.

    Returns a MagicMock that simulates RAGSystem behavior with proper
    query responses and course analytics.
    """
    mock = MagicMock()

    # Mock session manager
    mock.session_manager.create_session.return_value = "test-session-123"

    # Mock query response
    mock.query.return_value = (
        "This is a test answer about testing fundamentals.",
        [
            {
                "course_title": "Test Course: Introduction to Testing",
                "lesson_number": "1",
                "lesson_title": "Getting Started"
            }
        ]
    )

    # Mock course analytics
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": [
            "Test Course: Introduction to Testing",
            "Advanced Testing Course"
        ]
    }

    return mock


@pytest.fixture
def test_client(mock_rag_system):
    """
    FastAPI test client with mocked RAG system.

    Creates a test app that avoids the static file mounting issue
    by defining only the API endpoints without the frontend mount.
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional, Dict

    # Create test app with only API endpoints
    test_app = FastAPI(title="Test RAG System")

    # Add CORS middleware
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pydantic models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, str]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # API endpoints
    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/")
    async def root():
        return {"message": "RAG System API"}

    # Create test client
    from fastapi.testclient import TestClient
    return TestClient(test_app)


@pytest.fixture
def sample_query_request():
    """
    Sample query request data for API testing.
    """
    return {
        "query": "What is testing?",
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_query_request_no_session():
    """
    Sample query request without session ID.
    """
    return {
        "query": "What is testing?"
    }
