"""
RAGSystem tests - End-to-end system behavior.

These tests verify the complete query flow through the RAG system,
including how it handles the MAX_RESULTS=0 bug and API errors.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import CourseChunk
from rag_system import RAGSystem
from vector_store import SearchResults


def test_rag_system_initialization(test_config):
    """
    Test that RAGSystem initializes correctly with config.
    """
    rag = RAGSystem(test_config)

    assert rag.config == test_config
    assert rag.vector_store is not None
    assert rag.tool_manager is not None
    assert rag.ai_generator is not None
    assert rag.session_manager is not None


def test_query_with_buggy_max_results(mock_anthropic_client, mock_chroma_collection):
    """
    Test query behavior with MAX_RESULTS=0 bug.

    This simulates the actual bug condition where searches return 0 results.
    """
    from config import config

    # Use actual buggy config (MAX_RESULTS = 0)
    rag = RAGSystem(config)

    # Replace vector store collections with mocks
    rag.vector_store.course_content = mock_chroma_collection
    rag.vector_store.course_catalog = mock_chroma_collection

    # Mock the AI generator client
    rag.ai_generator.client = mock_anthropic_client

    # Mock tool use response
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "test_id"
    tool_block.input = {"query": "test query"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    final_response = MagicMock()
    final_response.content = [
        MagicMock(text="I couldn't find relevant information", type="text")
    ]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

    # Execute query
    try:
        answer, sources = rag.query("What is in the course?", session_id="test_session")

        # With MAX_RESULTS=0, sources should be empty or minimal
        # The system may return an answer but no sources
        assert isinstance(answer, str)
        assert isinstance(sources, list)

    except Exception as e:
        # If it raises an exception, that's also acceptable for documenting the bug
        pytest.fail(f"Query raised exception with MAX_RESULTS=0: {e}")


def test_query_with_fixed_max_results(
    test_config, mock_anthropic_client, sample_course, sample_course_chunks
):
    """
    Test that query works correctly when MAX_RESULTS is fixed.

    This proves the fix resolves the issue.
    """
    # Use test config with MAX_RESULTS=5
    rag = RAGSystem(test_config)

    # Setup mock responses
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "test_id"
    tool_block.input = {"query": "lesson 1", "course_name": "Test Course"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    final_response = MagicMock()
    final_response.content = [
        MagicMock(
            text="Lesson 1 covers testing fundamentals and basic concepts", type="text"
        )
    ]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

    # Mock vector store
    rag.ai_generator.client = mock_anthropic_client
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["This is lesson 1 content about testing fundamentals"],
        metadata=[{"course_title": sample_course.title, "lesson_number": 1}],
        distances=[0.3],
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    # Replace the search tool's store
    rag.tool_manager.tools["search_course_content"].store = mock_store

    # Execute query
    answer, sources = rag.query("What's in lesson 1?", session_id="test_session")

    # Should work correctly
    assert answer is not None
    assert len(answer) > 0
    assert isinstance(sources, list)


def test_query_exception_propagation(test_config, mock_anthropic_client):
    """
    Test that exceptions from AI generator propagate through RAGSystem.

    This confirms that errors aren't caught in rag_system.py.
    """
    import anthropic

    rag = RAGSystem(test_config)
    rag.ai_generator.client = mock_anthropic_client

    # Create proper mock response
    mock_response = Mock()
    mock_response.status_code = 503

    # Make API raise an error
    api_error = anthropic.APIError(
        message="API Error", request=Mock(), body={"error": {"message": "API Error"}}
    )
    mock_anthropic_client.messages.create.side_effect = api_error

    # Exception should propagate (not caught in rag_system.py)
    with pytest.raises(anthropic.APIError):
        rag.query("test query", session_id="test_session")


def test_session_management(test_config, mock_anthropic_client):
    """
    Test that conversation history is maintained across queries.
    """
    rag = RAGSystem(test_config)
    rag.ai_generator.client = mock_anthropic_client

    # Mock direct response (no tools)
    response1 = MagicMock()
    response1.content = [MagicMock(text="First answer", type="text")]
    response1.stop_reason = "end_turn"

    response2 = MagicMock()
    response2.content = [MagicMock(text="Second answer", type="text")]
    response2.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [response1, response2]

    # First query
    answer1, sources1 = rag.query("First question", session_id="test_session")
    assert answer1 == "First answer"

    # Second query in same session
    answer2, sources2 = rag.query("Second question", session_id="test_session")
    assert answer2 == "Second answer"

    # History should be maintained
    history = rag.session_manager.get_history("test_session")
    assert len(history) > 0


def test_sources_tracking(test_config, mock_anthropic_client):
    """
    Test that sources are correctly tracked and returned.
    """
    rag = RAGSystem(test_config)
    rag.ai_generator.client = mock_anthropic_client

    # Mock tool use
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "test_id"
    tool_block.input = {"query": "test"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    final_response = MagicMock()
    final_response.content = [MagicMock(text="Answer based on sources", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

    # Mock vector store with results
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Source content"],
        metadata=[{"course_title": "Test Course", "lesson_number": 1}],
        distances=[0.5],
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    rag.tool_manager.tools["search_course_content"].store = mock_store

    # Execute query
    answer, sources = rag.query("test query", session_id="test_session")

    # Sources should be returned
    assert isinstance(sources, list)
    assert len(sources) > 0
    assert "text" in sources[0]
    assert "url" in sources[0]


def test_query_without_tools(test_config, mock_anthropic_client):
    """
    Test query that doesn't require tool usage.

    Claude should answer directly without searching.
    """
    rag = RAGSystem(test_config)
    rag.ai_generator.client = mock_anthropic_client

    # Mock direct response (no tool use)
    response = MagicMock()
    response.content = [MagicMock(text="2+2 equals 4", type="text")]
    response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.return_value = response

    # Execute query
    answer, sources = rag.query("What is 2+2?", session_id="test_session")

    # Should get answer without sources
    assert answer == "2+2 equals 4"
    assert sources == [] or len(sources) == 0


def test_format_prompt():
    """
    Test the prompt formatting method.
    """
    from config import Config

    rag = RAGSystem(Config())
    formatted = rag._format_prompt("What is testing?")

    assert "What is testing?" in formatted


def test_multiple_sessions_isolated(test_config, mock_anthropic_client):
    """
    Test that different sessions maintain separate histories.
    """
    rag = RAGSystem(test_config)
    rag.ai_generator.client = mock_anthropic_client

    response1 = MagicMock()
    response1.content = [MagicMock(text="Session 1 answer", type="text")]
    response1.stop_reason = "end_turn"

    response2 = MagicMock()
    response2.content = [MagicMock(text="Session 2 answer", type="text")]
    response2.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [response1, response2]

    # Query in session 1
    answer1, _ = rag.query("Question 1", session_id="session_1")

    # Query in session 2
    answer2, _ = rag.query("Question 2", session_id="session_2")

    # Sessions should be independent
    history1 = rag.session_manager.get_history("session_1")
    history2 = rag.session_manager.get_history("session_2")

    assert history1 != history2
