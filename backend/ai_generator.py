from typing import Any, Dict, List, Optional

import anthropic
from config import config


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive tools for course information.

Tool Usage Guidelines:
- **Content search tool**: Use for questions about specific course content, topics, or detailed educational materials
- **Outline tool**: Use for questions about course structure, lesson listings, or "what's in this course"
- **Maximum 2 rounds of tool calls per query** - Use tools strategically
- You can make multiple tool calls in a single round if needed
- You can make additional tool calls in a follow-up round if the first results were insufficient
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results or errors, state this clearly

When to use each tool:
- **search_course_content**: For content-based queries (e.g., "What does this course teach about X?", "How do I do Y?")
- **get_course_outline**: For structure queries (e.g., "What's in this course?", "Show me the lessons", "Course outline")

Multi-round scenarios:
- If search results are too broad, refine your query in a second round
- If you need both outline AND content, use both tools (same or different rounds)
- If a tool returns an error, you can try an alternative approach in the next round

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific questions**: Use appropriate tool(s), then answer
- **Outline queries**: Always return the complete course title, course link, and full lesson list with lesson numbers and titles
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the tool results" or "I searched" or similar phrases


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with multi-round tool usage support.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize messages with user query
        messages = [{"role": "user", "content": query}]

        # Prepare base API parameters
        api_params = {**self.base_params, "system": system_content}

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Multi-round loop
        MAX_ROUNDS = config.MAX_TOOL_ROUNDS
        round_count = 0
        response = None

        while round_count < MAX_ROUNDS:
            round_count += 1

            # Make API call with current messages (use copy to avoid mutation issues in tests)
            try:
                response = self.client.messages.create(
                    **api_params, messages=messages.copy()
                )
            except anthropic.AuthenticationError as e:
                raise Exception(
                    f"Anthropic API authentication failed: {str(e)}. Please check your API key in .env file."
                )
            except anthropic.BadRequestError as e:
                if "credit balance" in str(e).lower():
                    raise Exception(
                        "Anthropic API credit balance is too low. Please add credits to your account at https://console.anthropic.com/"
                    )
                raise Exception(f"Anthropic API request error: {str(e)}")
            except anthropic.RateLimitError as e:
                raise Exception(
                    "Anthropic API rate limit exceeded. Please wait a moment and try again."
                )
            except anthropic.APIError as e:
                raise Exception(
                    f"Anthropic API error: {str(e)}. The service may be temporarily unavailable. Please try again later."
                )

            # Check termination condition: Claude doesn't want to use tools
            if response.stop_reason != "tool_use":
                return self._extract_text_from_response(response)

            # Check termination condition: Tools needed but no manager available
            if not tool_manager:
                return self._extract_text_from_response(response)

            # Execute tools and update messages for next round
            messages = self._execute_tools_and_update_messages(
                messages, response, tool_manager
            )

        # Max rounds reached - make one final API call without tools to get synthesized answer
        # Remove tools to force Claude to provide a text response
        final_params = {
            k: v for k, v in api_params.items() if k not in ("tools", "tool_choice")
        }
        try:
            final_response = self.client.messages.create(
                **final_params, messages=messages.copy()
            )
            return self._extract_text_from_response(final_response)
        except Exception:
            # If final call fails, return whatever text we have from the last response
            return self._extract_text_from_response(response)

    def _execute_tools_and_update_messages(
        self, messages: List[Dict], response, tool_manager
    ) -> List[Dict]:
        """
        Execute all tools in a response and update the messages array.

        Args:
            messages: Current messages list
            response: The response containing tool use requests
            tool_manager: Manager to execute tools

        Returns:
            Updated messages list with assistant response and tool results
        """
        # Add assistant's tool use response
        messages.append({"role": "assistant", "content": response.content})

        # Execute all tool calls and collect results
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                try:
                    tool_result = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result,
                        }
                    )
                except Exception as e:
                    # Tool execution failed - return error to Claude
                    error_msg = f"Error executing tool {content_block.name}: {str(e)}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": error_msg,
                            "is_error": True,
                        }
                    )

        # Add tool results as user message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        return messages

    def _extract_text_from_response(self, response) -> str:
        """
        Extract text content from a response.

        Args:
            response: API response object

        Returns:
            Extracted text string
        """
        # Look for text content in response
        for content_block in response.content:
            if content_block.type == "text":
                return content_block.text

        # No text found - return empty string
        return ""
