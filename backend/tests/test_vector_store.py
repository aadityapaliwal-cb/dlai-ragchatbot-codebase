"""
VectorStore tests - Verify search behavior with different MAX_RESULTS values.

These tests confirm that MAX_RESULTS=0 flows through to ChromaDB queries
and that fixing it resolves the search issue.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vector_store import VectorStore, SearchResults
from config import config


def test_search_with_zero_max_results(mock_chroma_collection):
    """
    Test that MAX_RESULTS=0 is passed to ChromaDB query.

    This test confirms the bug flows through VectorStore to ChromaDB.
    """
    # Create VectorStore with MAX_RESULTS=0 (the actual bug)
    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=0  # Simulating the buggy config
    )
    store.course_content = mock_chroma_collection
    store.course_catalog = mock_chroma_collection

    # Perform search
    results = store.search(query="test query")

    # Verify ChromaDB was called with n_results=0
    mock_chroma_collection.query.assert_called()
    call_args = mock_chroma_collection.query.call_args

    assert call_args is not None, "ChromaDB query should have been called"
    assert call_args.kwargs['n_results'] == 0, (
        "ChromaDB should be queried with n_results=0 when MAX_RESULTS=0"
    )


def test_search_with_valid_max_results(mock_chroma_collection):
    """
    Test that search works correctly with MAX_RESULTS > 0.

    This proves that fixing MAX_RESULTS resolves the issue.
    """
    # Create VectorStore with corrected MAX_RESULTS
    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5  # Fixed value
    )
    store.course_content = mock_chroma_collection
    store.course_catalog = mock_chroma_collection

    # Perform search
    results = store.search(query="test query about testing")

    # Should return results
    assert not results.is_empty(), "Should return results when MAX_RESULTS > 0"
    assert len(results.documents) > 0, "Should have documents"
    assert len(results.metadata) > 0, "Should have metadata"

    # Verify ChromaDB was called with correct n_results
    call_args = mock_chroma_collection.query.call_args
    assert call_args.kwargs['n_results'] == 5, "Should query with n_results=5"


def test_course_name_resolution(mock_chroma_collection):
    """
    Test semantic course name matching.

    Verifies that partial course names are resolved to full titles.
    """
    # Mock catalog query to return course metadata
    mock_chroma_collection.query.return_value = {
        'documents': [['Test Course: Introduction to Testing']],
        'metadatas': [[{'title': 'Test Course: Introduction to Testing'}]],
        'distances': [[0.2]]
    }

    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )
    store.course_catalog = mock_chroma_collection

    # Test partial match
    resolved = store._resolve_course_name("Test Course")

    assert resolved == "Test Course: Introduction to Testing", (
        "Should resolve partial course name to full title"
    )


def test_course_name_resolution_returns_none_when_not_found(mock_chroma_collection):
    """
    Test that course name resolution returns None for non-existent courses.
    """
    # Mock catalog query to return empty results
    mock_chroma_collection.query.return_value = {
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    }

    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )
    store.course_catalog = mock_chroma_collection

    # Test with non-existent course
    resolved = store._resolve_course_name("Non-existent Course")

    assert resolved is None, "Should return None when course not found"


def test_search_error_handling(mock_chroma_collection):
    """
    Test that search errors are caught and returned in SearchResults.

    Verifies that exceptions don't crash the system.
    """
    # Make ChromaDB raise an exception
    mock_chroma_collection.query.side_effect = Exception("ChromaDB connection error")

    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )
    store.course_content = mock_chroma_collection

    # Should not raise exception
    results = store.search(query="test query")

    # Should return error in SearchResults
    assert results.error is not None, "Should return error in SearchResults"
    assert "ChromaDB connection error" in results.error, (
        "Error message should include original exception"
    )
    assert results.is_empty(), "Should be empty when error occurs"


def test_search_with_course_filter(mock_chroma_collection):
    """
    Test search with course name filtering.
    """
    # Mock catalog to resolve course name
    catalog_mock = MagicMock()
    catalog_mock.query.return_value = {
        'documents': [['Test Course: Introduction to Testing']],
        'metadatas': [[{'title': 'Test Course: Introduction to Testing'}]],
        'distances': [[0.1]]
    }

    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )
    store.course_catalog = catalog_mock
    store.course_content = mock_chroma_collection

    # Search with course filter
    results = store.search(
        query="testing basics",
        course_name="Test Course"
    )

    # Verify course filter was applied
    call_args = mock_chroma_collection.query.call_args
    assert call_args.kwargs['where'] == {'course_title': 'Test Course: Introduction to Testing'}, (
        "Should apply course filter to query"
    )


def test_search_with_lesson_filter(mock_chroma_collection):
    """
    Test search with lesson number filtering.
    """
    store = VectorStore(
        chroma_path=":memory:",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )
    store.course_content = mock_chroma_collection
    store.course_catalog = mock_chroma_collection

    # Search with lesson filter
    results = store.search(
        query="testing basics",
        lesson_number=1
    )

    # Verify lesson filter was applied
    call_args = mock_chroma_collection.query.call_args
    assert call_args.kwargs['where'] == {'lesson_number': 1}, (
        "Should apply lesson filter to query"
    )


def test_search_results_from_chroma():
    """
    Test SearchResults.from_chroma() correctly converts ChromaDB format.
    """
    chroma_results = {
        'documents': [['Doc 1', 'Doc 2']],
        'metadatas': [[{'key': 'value1'}, {'key': 'value2'}]],
        'distances': [[0.1, 0.2]]
    }

    results = SearchResults.from_chroma(chroma_results)

    assert len(results.documents) == 2
    assert results.documents[0] == 'Doc 1'
    assert results.documents[1] == 'Doc 2'
    assert len(results.metadata) == 2
    assert len(results.distances) == 2


def test_search_results_empty():
    """
    Test SearchResults.empty() creates proper empty result with error.
    """
    error_msg = "Test error message"
    results = SearchResults.empty(error_msg)

    assert results.is_empty()
    assert results.error == error_msg
    assert len(results.documents) == 0


def test_search_results_is_empty():
    """
    Test SearchResults.is_empty() correctly identifies empty results.
    """
    empty = SearchResults(documents=[], metadata=[], distances=[])
    assert empty.is_empty()

    non_empty = SearchResults(
        documents=['doc'],
        metadata=[{'key': 'value'}],
        distances=[0.5]
    )
    assert not non_empty.is_empty()
