"""
Configuration tests - CRITICAL for proving PRIMARY BUG.

These tests validate that all configuration values are within acceptable ranges.
The test_max_results_is_zero test is expected to FAIL, proving the MAX_RESULTS=0 bug.
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import config, Config


def test_max_results_is_zero():
    """
    CRITICAL TEST: Detect MAX_RESULTS=0 bug.

    This test should FAIL before the fix is applied, proving the bug exists.
    After fixing config.py line 21 to set MAX_RESULTS=5, this test should PASS.
    """
    assert config.MAX_RESULTS > 0, (
        "BUG DETECTED: MAX_RESULTS is set to 0 in config.py:21. "
        "This causes ChromaDB to return zero search results, breaking the RAG system. "
        "Expected: MAX_RESULTS >= 1 (recommended: 5)"
    )


def test_config_values_are_valid():
    """
    Validate all configuration values are within acceptable ranges.

    This comprehensive test checks all config settings for validity.
    """
    # Chunk size validations
    assert config.CHUNK_SIZE > 0, "CHUNK_SIZE must be positive"
    assert config.CHUNK_SIZE >= 100, "CHUNK_SIZE should be at least 100 characters for meaningful chunks"

    # Chunk overlap validations
    assert config.CHUNK_OVERLAP >= 0, "CHUNK_OVERLAP must be non-negative"
    assert config.CHUNK_OVERLAP < config.CHUNK_SIZE, (
        "CHUNK_OVERLAP must be less than CHUNK_SIZE"
    )

    # Search results validation - THIS WILL FAIL with MAX_RESULTS=0
    assert config.MAX_RESULTS > 0, (
        "MAX_RESULTS must be positive to return search results"
    )
    assert config.MAX_RESULTS <= 20, (
        "MAX_RESULTS should not exceed 20 to avoid excessive token usage"
    )

    # History validation
    assert config.MAX_HISTORY >= 0, "MAX_HISTORY must be non-negative"
    assert config.MAX_HISTORY <= 10, "MAX_HISTORY should not exceed 10 to manage context window"

    # Model name validation
    assert config.ANTHROPIC_MODEL, "ANTHROPIC_MODEL must be set"
    assert "claude" in config.ANTHROPIC_MODEL.lower(), "ANTHROPIC_MODEL should be a Claude model"

    # Embedding model validation
    assert config.EMBEDDING_MODEL, "EMBEDDING_MODEL must be set"


def test_config_instance_creation():
    """
    Test that Config instances can be created with custom values.

    This verifies the Config dataclass works correctly.
    """
    custom_config = Config()
    custom_config.MAX_RESULTS = 10
    custom_config.CHUNK_SIZE = 1000

    assert custom_config.MAX_RESULTS == 10
    assert custom_config.CHUNK_SIZE == 1000


def test_config_api_key_from_env():
    """
    Test that API key is loaded from environment.

    Note: This test checks the mechanism, not the actual key value.
    """
    # The config should have attempted to load from environment
    assert hasattr(config, 'ANTHROPIC_API_KEY')
    # In test environment, may be empty string if .env not loaded
    assert isinstance(config.ANTHROPIC_API_KEY, str)


def test_chroma_path_is_set():
    """
    Test that ChromaDB path is configured.
    """
    assert config.CHROMA_PATH, "CHROMA_PATH must be set"
    assert isinstance(config.CHROMA_PATH, str)
