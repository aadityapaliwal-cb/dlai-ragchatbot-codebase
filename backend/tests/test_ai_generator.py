"""
AI Generator tests - CRITICAL for proving SECONDARY BUG.

These tests verify AIGenerator's tool calling flow and prove that
Anthropic API errors are NOT caught, causing HTTP 500 errors.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, Mock

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool
from vector_store import SearchResults


def test_generate_response_without_tools(mock_anthropic_client):
    """
    Test AIGenerator with direct text response (no tools).

    Verifies basic response generation without tool calling.
    """
    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(query="What is 2+2?")

    # Should return text from mock
    assert response == "This is a test response from Claude"

    # Verify API was called correctly
    mock_anthropic_client.messages.create.assert_called_once()
    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args.kwargs['model'] == "claude-sonnet-4-20250514"
    assert call_args.kwargs['temperature'] == 0
    assert call_args.kwargs['max_tokens'] == 800


def test_generate_response_with_conversation_history(mock_anthropic_client):
    """
    Test that conversation history is included in system prompt.
    """
    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    history = "User: Previous question\nAssistant: Previous answer"
    response = generator.generate_response(
        query="Follow-up question",
        conversation_history=history
    )

    # Verify system prompt includes history
    call_args = mock_anthropic_client.messages.create.call_args
    system_content = call_args.kwargs['system']
    assert "Previous conversation:" in system_content
    assert history in system_content


def test_generate_response_with_tool_use(mock_anthropic_client, mock_tool_use_response):
    """
    Test AIGenerator handles tool use correctly.

    This is the full tool calling flow that Claude uses.
    """
    # Setup mock to return tool use, then final response
    final_response = MagicMock()
    final_response.content = [MagicMock(
        text="Here's what I found about testing basics",
        type="text"
    )]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        mock_tool_use_response,  # First call: tool use
        final_response           # Second call: final answer
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content about testing basics"],
        metadata=[{'course_title': 'Test Course', 'lesson_number': 1}],
        distances=[0.5],
        error=None
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    # Generate response
    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(
        query="Tell me about testing basics",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Should call API twice (initial + follow-up)
    assert mock_anthropic_client.messages.create.call_count == 2
    assert response == "Here's what I found about testing basics"


def test_api_error_propagates(mock_anthropic_client):
    """
    Test that Anthropic API authentication errors are caught and wrapped.

    Authentication errors should be caught and re-raised as generic Exceptions
    with user-friendly messages.
    """
    import anthropic

    # Create proper mock response
    mock_response = Mock()
    mock_response.status_code = 401

    # Make API raise an authentication error
    api_error = anthropic.AuthenticationError(
        message="Invalid API key",
        response=mock_response,
        body={"error": {"message": "Invalid API key"}}
    )
    mock_anthropic_client.messages.create.side_effect = api_error

    generator = AIGenerator(api_key="invalid-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    # Should raise wrapped exception
    with pytest.raises(Exception) as exc_info:
        generator.generate_response(query="test")

    assert "Anthropic API authentication failed" in str(exc_info.value)


def test_api_credit_error_propagates(mock_anthropic_client):
    """
    Test Anthropic API error when credits are insufficient.

    This is a common error that should be caught and wrapped with helpful message.
    """
    import anthropic

    # Create a proper mock response object
    mock_response = Mock()
    mock_response.status_code = 400

    # Simulate credit balance error
    api_error = anthropic.BadRequestError(
        message="credit balance too low",
        response=mock_response,
        body={"error": {"message": "credit balance too low"}}
    )
    mock_anthropic_client.messages.create.side_effect = api_error

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    # Should raise wrapped exception
    with pytest.raises(Exception) as exc_info:
        generator.generate_response(query="test")

    assert "credit balance" in str(exc_info.value).lower()


def test_api_rate_limit_error_propagates(mock_anthropic_client):
    """
    Test that rate limit errors are caught and wrapped.
    """
    import anthropic

    # Create proper mock response
    mock_response = Mock()
    mock_response.status_code = 429

    api_error = anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=mock_response,
        body={"error": {"message": "Rate limit exceeded"}}
    )
    mock_anthropic_client.messages.create.side_effect = api_error

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    with pytest.raises(Exception) as exc_info:
        generator.generate_response(query="test")

    assert "rate limit exceeded" in str(exc_info.value).lower()


def test_api_generic_error_propagates(mock_anthropic_client):
    """
    Test that generic API errors are caught and wrapped.
    """
    import anthropic

    # Create proper mock response
    mock_response = Mock()
    mock_response.status_code = 503

    api_error = anthropic.APIError(
        message="Service temporarily unavailable",
        request=Mock(),
        body={"error": {"message": "Service temporarily unavailable"}}
    )
    mock_anthropic_client.messages.create.side_effect = api_error

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    with pytest.raises(Exception) as exc_info:
        generator.generate_response(query="test")

    assert "Anthropic API error" in str(exc_info.value)


def test_tool_execution_with_multiple_tools(mock_anthropic_client):
    """
    Test handling of multiple tool uses in a single response.

    Note: Current system prompt limits to one tool call, but test the capability.
    """
    # Mock response with multiple tool uses
    tool_response = MagicMock()

    tool_block_1 = MagicMock()
    tool_block_1.type = "tool_use"
    tool_block_1.name = "search_course_content"
    tool_block_1.id = "tool_1"
    tool_block_1.input = {"query": "first query"}

    tool_block_2 = MagicMock()
    tool_block_2.type = "tool_use"
    tool_block_2.name = "search_course_content"
    tool_block_2.id = "tool_2"
    tool_block_2.input = {"query": "second query"}

    tool_response.content = [tool_block_1, tool_block_2]
    tool_response.stop_reason = "tool_use"

    final_response = MagicMock()
    final_response.content = [MagicMock(text="Combined answer", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Result"],
        metadata=[{'course_title': 'Test', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(
        query="test",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Both tools should be executed
    assert mock_store.search.call_count == 2
    assert response == "Combined answer"


def test_system_prompt_content():
    """
    Test that the system prompt contains key instructions.
    """
    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")

    # Check static system prompt
    assert "Maximum 2 rounds of tool calls per query" in generator.SYSTEM_PROMPT
    assert "search_course_content" in generator.SYSTEM_PROMPT
    assert "get_course_outline" in generator.SYSTEM_PROMPT
    assert "Multi-round scenarios" in generator.SYSTEM_PROMPT


def test_base_params_initialization():
    """
    Test that AIGenerator initializes with correct base parameters.
    """
    generator = AIGenerator(
        api_key="test-key",
        model="claude-sonnet-4-20250514"
    )

    assert generator.base_params['model'] == "claude-sonnet-4-20250514"
    assert generator.base_params['temperature'] == 0
    assert generator.base_params['max_tokens'] == 800


# ============================================================================
# Multi-Round Tool Calling Tests
# ============================================================================

def test_two_round_tool_calling_success(mock_anthropic_client):
    """
    Test successful 2-round tool calling flow.

    Round 1: Claude searches for "Python basics"
    Round 2: Claude searches for "Python advanced"
    Final: Claude synthesizes the answer
    """
    # Setup mock responses for 2 rounds + final
    # Round 1: tool use
    tool_response_1 = MagicMock()
    tool_block_1 = MagicMock()
    tool_block_1.type = "tool_use"
    tool_block_1.name = "search_course_content"
    tool_block_1.id = "tool_1"
    tool_block_1.input = {"query": "Python basics"}
    tool_response_1.content = [tool_block_1]
    tool_response_1.stop_reason = "tool_use"

    # Round 2: another tool use
    tool_response_2 = MagicMock()
    tool_block_2 = MagicMock()
    tool_block_2.type = "tool_use"
    tool_block_2.name = "search_course_content"
    tool_block_2.id = "tool_2"
    tool_block_2.input = {"query": "Python advanced"}
    tool_response_2.content = [tool_block_2]
    tool_response_2.stop_reason = "tool_use"

    # Final response after max rounds
    final_response = MagicMock()
    final_response.content = [MagicMock(text="Here's the comparison of Python basics and advanced topics", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response_1,
        tool_response_2,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content about Python"],
        metadata=[{'course_title': 'Python Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(
        query="Compare Python basics and advanced topics",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Verify: 3 API calls (2 rounds + final synthesis)
    assert mock_anthropic_client.messages.create.call_count == 3
    # Verify: 2 tool executions
    assert mock_store.search.call_count == 2
    # Verify: correct final response
    assert response == "Here's the comparison of Python basics and advanced topics"


def test_early_termination_no_tool_use_round_1(mock_anthropic_client):
    """
    Test that system terminates after round 1 if Claude doesn't use tools.

    Claude answers directly without tools.
    """
    # Mock: response with no tool use
    direct_response = MagicMock()
    direct_response.content = [MagicMock(text="This is a general knowledge answer", type="text")]
    direct_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.return_value = direct_response

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(query="What is 2+2?")

    # Verify: Only 1 API call made
    assert mock_anthropic_client.messages.create.call_count == 1
    # Verify: Response returned immediately
    assert response == "This is a general knowledge answer"


def test_mid_round_termination_round_2(mock_anthropic_client):
    """
    Test termination after first round when Claude doesn't need more tools.

    Round 1: Claude searches
    Round 2: Claude has enough info, returns final answer without more tools
    """
    # Round 1: tool use
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_1"
    tool_block.input = {"query": "testing"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    # Round 2: final answer (no more tools)
    final_response = MagicMock()
    final_response.content = [MagicMock(text="Based on the search, here's the answer", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Testing content"],
        metadata=[{'course_title': 'Test Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(
        query="Tell me about testing",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Verify: 2 API calls (round 1 + final)
    assert mock_anthropic_client.messages.create.call_count == 2
    # Verify: Loop terminated correctly
    assert response == "Based on the search, here's the answer"


def test_max_rounds_reached_with_final_text(mock_anthropic_client):
    """
    Test that system terminates after exactly 2 rounds and makes a final synthesis call.

    Claude uses tools in both rounds, then system makes final call for synthesis.
    """
    # Round 1: tool use
    tool_response_1 = MagicMock()
    tool_block_1 = MagicMock()
    tool_block_1.type = "tool_use"
    tool_block_1.name = "search_course_content"
    tool_block_1.id = "tool_1"
    tool_block_1.input = {"query": "first search"}
    tool_response_1.content = [tool_block_1]
    tool_response_1.stop_reason = "tool_use"

    # Round 2: another tool use
    tool_response_2 = MagicMock()
    tool_block_2 = MagicMock()
    tool_block_2.type = "tool_use"
    tool_block_2.name = "search_course_content"
    tool_block_2.id = "tool_2"
    tool_block_2.input = {"query": "second search"}
    tool_response_2.content = [tool_block_2]
    tool_response_2.stop_reason = "tool_use"

    # Final synthesis response
    final_response = MagicMock()
    final_response.content = [MagicMock(text="Here's what I found from both searches", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response_1,
        tool_response_2,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{'course_title': 'Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(
        query="Complex query",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Verify: 3 API calls (2 rounds + final synthesis)
    assert mock_anthropic_client.messages.create.call_count == 3
    # Verify: Text extracted from final response
    assert response == "Here's what I found from both searches"


def test_tool_execution_error_in_round_1(mock_anthropic_client):
    """
    Test tool failure on first round is passed to Claude as error.

    Claude receives error result and can respond accordingly.
    """
    # Round 1: tool use
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_1"
    tool_block.input = {"query": "test"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    # Round 2: Claude acknowledges error
    final_response = MagicMock()
    final_response.content = [MagicMock(text="I encountered an error searching. Please try again.", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response,
        final_response
    ]

    # Setup tool manager that raises exception
    mock_store = MagicMock()
    mock_store.search.side_effect = Exception("Database connection failed")
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    response = generator.generate_response(
        query="Search for something",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Verify: System continued to round 2 despite error
    assert mock_anthropic_client.messages.create.call_count == 2
    # Verify: Claude received error and responded
    assert response == "I encountered an error searching. Please try again."


def test_messages_array_grows_correctly(mock_anthropic_client):
    """
    Test that messages array grows with each round.

    Verify proper message alternation: user → assistant → user → assistant
    """
    # Round 1: tool use
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_1"
    tool_block.input = {"query": "test"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    # Round 2: final answer
    final_response = MagicMock()
    final_response.content = [MagicMock(text="Final answer", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{'course_title': 'Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    generator.generate_response(
        query="Test query",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Capture all API calls
    calls = mock_anthropic_client.messages.create.call_args_list

    # Verify: 1st call has 1 message (user query)
    first_call_messages = calls[0].kwargs['messages']
    assert len(first_call_messages) == 1
    assert first_call_messages[0]['role'] == 'user'

    # Verify: 2nd call has 3 messages (user, assistant tool_use, user tool_results)
    second_call_messages = calls[1].kwargs['messages']
    assert len(second_call_messages) == 3
    assert second_call_messages[0]['role'] == 'user'
    assert second_call_messages[1]['role'] == 'assistant'
    assert second_call_messages[2]['role'] == 'user'


def test_conversation_history_preserved_multi_round(mock_anthropic_client):
    """
    Test that conversation history is included in all rounds.
    """
    # Round 1: tool use
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_1"
    tool_block.input = {"query": "test"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    # Round 2: final
    final_response = MagicMock()
    final_response.content = [MagicMock(text="Answer", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{'course_title': 'Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    history = "User: Previous question\nAssistant: Previous answer"
    generator.generate_response(
        query="Follow-up question",
        conversation_history=history,
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Verify: All API calls include history in system prompt
    calls = mock_anthropic_client.messages.create.call_args_list
    for call in calls:
        system_content = call.kwargs['system']
        assert "Previous conversation:" in system_content
        assert history in system_content


def test_tools_parameter_present_in_all_rounds(mock_anthropic_client):
    """
    Test tools parameter is sent on every round (key difference from old implementation).
    """
    # Round 1: tool use
    tool_response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_1"
    tool_block.input = {"query": "test"}
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    # Round 2: final
    final_response = MagicMock()
    final_response.content = [MagicMock(text="Answer", type="text")]
    final_response.stop_reason = "end_turn"

    mock_anthropic_client.messages.create.side_effect = [
        tool_response,
        final_response
    ]

    # Setup tool manager
    mock_store = MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{'course_title': 'Course', 'lesson_number': 1}],
        distances=[0.5]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

    tool_manager = ToolManager()
    search_tool = CourseSearchTool(mock_store)
    tool_manager.register_tool(search_tool)

    generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client

    generator.generate_response(
        query="Test query",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager
    )

    # Verify: All API calls include tools parameter
    calls = mock_anthropic_client.messages.create.call_args_list
    for call in calls:
        assert 'tools' in call.kwargs
        assert call.kwargs['tools'] is not None
        assert 'tool_choice' in call.kwargs
