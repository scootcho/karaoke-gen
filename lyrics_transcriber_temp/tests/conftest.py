import pytest
import logging
import shutil
import os
import tempfile
import sys

# Add the project root to the path so we can import from the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# All tests are now working! No more skip patterns needed.
SKIP_PATTERNS = []


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (run with --run-slow)"
    )


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests that execute expensive algorithms"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip slow tests unless --run-slow is specified."""
    # Skip slow tests unless --run-slow is specified
    if not config.getoption("--run-slow", default=False):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    # Legacy skip patterns
    for item in items:
        for pattern in SKIP_PATTERNS:
            if pattern in item.nodeid:
                item.add_marker(pytest.mark.skip(reason="Skipped due to codebase changes"))
                break


@pytest.fixture
def sample_audio_file(tmp_path):
    """Create a dummy audio file for testing."""
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"dummy audio content")
    return str(audio_file)


@pytest.fixture
def test_logger():
    """Create a logger for testing."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture(autouse=True)
def reset_langfuse_singletons():
    """Reset LangFuse singletons before each test to avoid state leakage."""
    # Reset before test
    try:
        from lyrics_transcriber.correction.agentic.prompts.langfuse_prompts import reset_prompt_service
        from lyrics_transcriber.correction.agentic.observability.langfuse_integration import reset_langfuse_client
        reset_prompt_service()
        reset_langfuse_client()
    except ImportError:
        pass  # Module may not be available in all test contexts

    yield  # Run the test

    # Reset after test
    try:
        from lyrics_transcriber.correction.agentic.prompts.langfuse_prompts import reset_prompt_service
        from lyrics_transcriber.correction.agentic.observability.langfuse_integration import reset_langfuse_client
        reset_prompt_service()
        reset_langfuse_client()
    except ImportError:
        pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_directories():
    """Clean up test directories after all tests complete."""
    yield  # Run all tests first

    # Clean up test_cache in temp directory
    cache_dir = os.path.join(tempfile.gettempdir(), "lyrics-transcriber-test-cache")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

    # Clean up local test_cache
    if os.path.exists("test_cache"):
        shutil.rmtree("test_cache")

    # Clean up test_output
    if os.path.exists("test_output"):
        shutil.rmtree("test_output")


def main():
    """Run the test suite with coverage reporting."""
    import pytest
    sys.exit(pytest.main(["-xvs", "--cov=lyrics_transcriber", "--cov-report=term", "--cov-report=html"]))


if __name__ == "__main__":
    main()
