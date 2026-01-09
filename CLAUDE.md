# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A full-stack RAG (Retrieval-Augmented Generation) chatbot for querying course materials. Users ask questions, and the system uses semantic search + Claude AI to provide answers with source citations.

## Running the Application

**Start the server:**
```bash
./run.sh
```
Or manually:
```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

**Access points:**
- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs

**Environment setup:**
- Requires `.env` file in project root with `ANTHROPIC_API_KEY=...`
- Python 3.13+ required
- Uses `uv` package manager: `uv sync` to install dependencies

## Architecture

### Request Flow: Tool-Augmented RAG Pattern

Unlike traditional RAG (automatic retrieval → context injection), this uses **Claude's tool calling**:

```
User Query → FastAPI → RAGSystem → Claude API (with search tool definition)
                                        ↓
                            Claude decides: "Do I need to search?"
                                        ↓
                                   [If yes] Tool call returned
                                        ↓
                            CourseSearchTool.execute()
                                        ↓
                            VectorStore.search() → ChromaDB
                                        ↓
                            Results returned to Claude
                                        ↓
                            Claude generates final answer
                                        ↓
                            Response + sources → Frontend
```

**Key difference:** Claude autonomously decides when to search using tool calling, rather than always retrieving context.

### Core Components

**1. RAGSystem (`rag_system.py`)** - Main orchestrator
- Coordinates all components
- Manages query flow: format prompt → get history → call AI → extract sources → update history
- Entry point: `query(query, session_id)` returns `(answer, sources)`

**2. AIGenerator (`ai_generator.py`)** - Claude API integration
- System prompt enforces: "One search per query maximum" and "No meta-commentary"
- `generate_response()` handles tool calling flow
- `_handle_tool_execution()` runs tools and sends results back to Claude for final answer

**3. VectorStore (`vector_store.py`)** - ChromaDB wrapper
- **Two collections:**
  - `course_catalog`: Course titles/metadata (for semantic course name resolution)
  - `course_content`: Text chunks (for content search)
- `search()` method does semantic course name matching first, then filters content
- Uses `all-MiniLM-L6-v2` embedding model

**4. CourseSearchTool (`search_tools.py`)** - Tool definition + execution
- Defines Anthropic tool schema with parameters: `query`, `course_name`, `lesson_number`
- `execute()` calls VectorStore, formats results, tracks sources
- Sources stored in `last_sources` for UI display

**5. DocumentProcessor (`document_processor.py`)** - Document ingestion
- Parses course files from `/docs` folder
- Extracts metadata (title, instructor, lessons) from structured text
- Chunks text: 800 chars with 100 char overlap, sentence-aware splitting
- Outputs: `Course` objects and `CourseChunk` objects

**6. SessionManager (`session_manager.py`)** - Conversation history
- Maintains last 2 exchanges per session (configurable via `MAX_HISTORY`)
- Formats history for Claude context

### Data Models (`models.py`)

- **Course**: `title` (unique ID), `instructor`, `lessons[]`, `course_link`
- **Lesson**: `lesson_number`, `title`, `lesson_link`
- **CourseChunk**: `content`, `course_title`, `lesson_number`, `chunk_index`

### Configuration (`config.py`)

All settings centralized:
- `ANTHROPIC_MODEL`: `claude-sonnet-4-20250514`
- `CHUNK_SIZE`: 800 chars
- `CHUNK_OVERLAP`: 100 chars
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation exchanges
- `CHROMA_PATH`: `./chroma_db` (persistent storage)

## Document Processing

**Startup behavior:** On server start, `app.py:startup_event` loads all files from `../docs/`:
- Checks existing course titles to avoid duplicates
- Processes `.txt`, `.pdf`, `.docx` files
- Adds to both ChromaDB collections

**Format expectations:** Course documents should have structured sections for metadata extraction (see `DocumentProcessor.process_course_document()`).

## Frontend Integration

**Frontend location:** `frontend/` directory (HTML/CSS/JS)
- Static files served by FastAPI at root path
- API calls to `/api/query` and `/api/courses`
- Displays responses with collapsible sources
- Session management via `currentSessionId`

## Debugging Common Issues

**"Internal Server Error" when querying:**
- Check Anthropic API key has sufficient credits
- Error appears as 400 response: "credit balance too low"
- Update `.env` with valid API key, then restart server (reload doesn't pick up `.env` changes)

**ChromaDB issues:**
- Database persists in `./chroma_db/`
- To reset: delete `chroma_db/` folder and restart
- `VectorStore.clear_all_data()` method available for programmatic reset

**Course not found:**
- Course name resolution uses semantic search on `course_catalog` collection
- Partial matches work (e.g., "MCP" matches "MCP: Build Rich-Context AI Apps")
- Check `get_existing_course_titles()` to see what's loaded

## Key Design Decisions

1. **Tool-based search** (not automatic RAG): Claude decides when to search, enabling it to answer general questions without unnecessary retrieval

2. **Dual collections**: Separating course metadata from content enables semantic course name matching before content filtering

3. **Sentence-aware chunking**: `DocumentProcessor` splits on sentence boundaries (respecting abbreviations) to maintain semantic coherence

4. **One tool call maximum**: System prompt limits Claude to single search per query to control costs and latency

5. **Session-based history**: Maintains conversation context while limiting token usage (`MAX_HISTORY=2`)

- Always use uv to run the server, do not use pip directly. Also use uv to manage dependencies.