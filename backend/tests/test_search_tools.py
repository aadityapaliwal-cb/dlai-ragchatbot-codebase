"""
Search tools tests - Verify CourseSearchTool and ToolManager behavior.

These tests confirm that tools handle empty results and errors gracefully,
and that the ToolManager correctly routes tool calls.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


def test_search_tool_with_empty_results():
    """
    Test that CourseSearchTool handles empty search results gracefully.

    When MAX_RESULTS=0, VectorStore returns empty results.
    The tool should return a user-friendly message.
    """
    # Create mock VectorStore that returns empty results
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )

    tool = CourseSearchTool(mock_store)
    result = tool.execute(query="test query")

    # Should return "No relevant content found" message
    assert "No relevant content found" in result, (
        "Should return empty result message when no results found"
    )


def test_search_tool_with_error():
    """
    Test that CourseSearchTool propagates errors from VectorStore.

    When VectorStore returns an error (e.g., MAX_RESULTS=0),
    the tool should return the error message.
    """
    # Create mock VectorStore that returns error
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults.empty("Search error: MAX_RESULTS is 0")

    tool = CourseSearchTool(mock_store)
    result = tool.execute(query="test query")

    # Should return the error message
    assert "Search error" in result, "Should return error message"
    assert "MAX_RESULTS" in result or "error" in result.lower(), (
        "Error message should be descriptive"
    )


def test_search_tool_result_formatting(valid_search_results):
    """
    Test that CourseSearchTool correctly formats results with sources.

    Verifies that results include course/lesson headers and content.
    """
    # Create mock VectorStore with results
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content from lesson 1 about testing basics"],
        metadata=[{
            'course_title': 'Test Course: Introduction to Testing',
            'lesson_number': 1
        }],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool = CourseSearchTool(mock_store)
    result = tool.execute(query="testing basics", course_name="Test Course")

    # Verify formatting
    assert "[Test Course: Introduction to Testing - Lesson 1]" in result, (
        "Should include course and lesson header"
    )
    assert "Content from lesson 1" in result, "Should include content"

    # Verify sources tracking
    assert len(tool.last_sources) == 1, "Should track one source"
    assert tool.last_sources[0]['text'] == "Test Course: Introduction to Testing - Lesson 1"
    assert tool.last_sources[0]['url'] == "https://example.com/lesson1"


def test_search_tool_multiple_results():
    """
    Test CourseSearchTool with multiple search results.
    """
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=[
            "First result about testing",
            "Second result about advanced testing"
        ],
        metadata=[
            {'course_title': 'Test Course', 'lesson_number': 1},
            {'course_title': 'Test Course', 'lesson_number': 2}
        ],
        distances=[0.3, 0.5]
    )
    mock_store.get_lesson_link.side_effect = [
        "https://example.com/lesson1",
        "https://example.com/lesson2"
    ]

    tool = CourseSearchTool(mock_store)
    result = tool.execute(query="testing")

    # Should have both results
    assert "First result" in result
    assert "Second result" in result
    assert len(tool.last_sources) == 2


def test_search_tool_get_tool_definition():
    """
    Test that CourseSearchTool returns proper Anthropic tool definition.
    """
    mock_store = MagicMock()
    tool = CourseSearchTool(mock_store)
    definition = tool.get_tool_definition()

    assert definition['name'] == 'search_course_content'
    assert 'description' in definition
    assert 'input_schema' in definition
    assert definition['input_schema']['type'] == 'object'
    assert 'query' in definition['input_schema']['properties']
    assert 'query' in definition['input_schema']['required']


def test_tool_manager_execute():
    """
    Test ToolManager correctly routes tool calls.

    Verifies that ToolManager can register and execute tools.
    """
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    # Execute tool via ToolManager
    result = tool_manager.execute_tool("search_course_content", query="test")

    # Should call the tool
    assert "No relevant content found" in result
    mock_store.search.assert_called_once()


def test_tool_manager_execute_nonexistent_tool():
    """
    Test ToolManager returns error for non-existent tools.
    """
    tool_manager = ToolManager()

    result = tool_manager.execute_tool("nonexistent_tool", query="test")

    assert "not found" in result.lower()


def test_tool_manager_get_tool_definitions():
    """
    Test ToolManager returns all registered tool definitions.
    """
    mock_store = MagicMock()

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    outline_tool = CourseOutlineTool(mock_store)

    tool_manager.register_tool(search_tool)
    tool_manager.register_tool(outline_tool)

    definitions = tool_manager.get_tool_definitions()

    assert len(definitions) == 2
    assert any(d['name'] == 'search_course_content' for d in definitions)
    assert any(d['name'] == 'get_course_outline' for d in definitions)


def test_tool_manager_get_last_sources():
    """
    Test ToolManager retrieves sources from last search.
    """
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{'course_title': 'Test Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    # Execute search
    tool_manager.execute_tool("search_course_content", query="test")

    # Get sources
    sources = tool_manager.get_last_sources()

    assert len(sources) == 1
    assert sources[0]['text'] == "Test Course - Lesson 1"


def test_tool_manager_reset_sources():
    """
    Test ToolManager can reset sources.
    """
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{'course_title': 'Test', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    # Execute and verify sources exist
    tool_manager.execute_tool("search_course_content", query="test")
    assert len(tool_manager.get_last_sources()) > 0

    # Reset sources
    tool_manager.reset_sources()
    assert len(tool_manager.get_last_sources()) == 0


def test_course_outline_tool_get_definition():
    """
    Test CourseOutlineTool returns proper tool definition.
    """
    mock_store = MagicMock()
    tool = CourseOutlineTool(mock_store)
    definition = tool.get_tool_definition()

    assert definition['name'] == 'get_course_outline'
    assert 'description' in definition
    assert 'course_title' in definition['input_schema']['properties']


def test_course_outline_tool_execute():
    """
    Test CourseOutlineTool execution with valid course.
    """
    mock_store = MagicMock()

    # Mock course name resolution
    mock_store._resolve_course_name.return_value = "Test Course: Introduction"

    # Mock course catalog get
    mock_store.course_catalog.get.return_value = {
        'metadatas': [{
            'title': 'Test Course: Introduction',
            'instructor': 'Test Instructor',
            'course_link': 'https://example.com/course',
            'lessons_json': '[{"lesson_number": 1, "lesson_title": "Lesson 1", "lesson_link": "https://example.com/lesson1"}]'
        }]
    }

    tool = CourseOutlineTool(mock_store)
    result = tool.execute(course_title="Test Course")

    assert "Test Course: Introduction" in result
    assert "Test Instructor" in result
    assert "Lesson 1" in result


def test_course_outline_tool_course_not_found():
    """
    Test CourseOutlineTool with non-existent course.
    """
    mock_store = MagicMock()
    mock_store._resolve_course_name.return_value = None

    tool = CourseOutlineTool(mock_store)
    result = tool.execute(course_title="Nonexistent Course")

    assert "No course found" in result
