"""Tests for thread safety in LangChainBridge.

This test module specifically targets the race condition where multiple threads
calling generate_correction_proposals() simultaneously could all try to initialize
the model, leading to:
- Multiple concurrent model initialization attempts
- Resource contention and timeouts
- Wasted API calls and credits

The fix should ensure only ONE thread initializes the model, while others wait.
"""
import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from lyrics_transcriber.correction.agentic.providers.langchain_bridge import LangChainBridge
from lyrics_transcriber.correction.agentic.providers.config import ProviderConfig


class TestLangChainBridgeThreadSafety:
    """Test thread safety of LangChainBridge model initialization."""

    def test_concurrent_calls_should_initialize_model_only_once(self):
        """
        GIVEN a LangChainBridge instance with no model initialized
        WHEN multiple threads call generate_correction_proposals simultaneously
        THEN the model should be initialized exactly once (not once per thread)

        This test reproduces the bug from job 2ccbdf6b where 5 parallel workers
        all tried to initialize the model, causing 6+ minute delays.
        """
        # Track how many times model initialization is called
        init_call_count = 0
        init_call_lock = threading.Lock()

        # Create a mock model that tracks initialization
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content='{"proposals": []}')

        def mock_create_chat_model(model_spec, config):
            """Mock factory that counts initialization calls."""
            nonlocal init_call_count
            with init_call_lock:
                init_call_count += 1

            # Simulate model initialization taking some time (like Vertex AI)
            # This increases the window for race conditions
            time.sleep(0.1)

            return mock_model

        # Create bridge with mocked factory
        config = ProviderConfig.from_env()
        mock_factory = Mock()
        mock_factory.create_chat_model = mock_create_chat_model

        # Mock circuit breaker to not interfere
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.is_open.return_value = False
        mock_circuit_breaker.record_success = Mock()
        mock_circuit_breaker.record_failure = Mock()

        # Mock cache to always miss (so we go through model init)
        mock_cache = Mock()
        mock_cache.get.return_value = None  # Cache miss
        mock_cache.set = Mock()

        bridge = LangChainBridge(
            model="test/model",
            config=config,
            model_factory=mock_factory,
            circuit_breaker=mock_circuit_breaker,
            response_cache=mock_cache,
        )

        # Verify model is not yet initialized
        assert bridge._chat_model is None

        # Launch multiple threads simultaneously (simulating parallel gap processing)
        num_threads = 5
        results = []
        errors = []

        def call_generate():
            try:
                result = bridge.generate_correction_proposals(
                    prompt="test prompt",
                    schema={}
                )
                return result
            except Exception as e:
                return {"error": str(e)}

        # Use a barrier to ensure all threads start at the same time
        barrier = threading.Barrier(num_threads)

        def synchronized_call():
            barrier.wait()  # All threads wait here until all are ready
            return call_generate()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(synchronized_call) for _ in range(num_threads)]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    errors.append(str(e))

        # THE KEY ASSERTION: Model should only be initialized ONCE
        # Before the fix, this will be 5 (one per thread)
        # After the fix, this should be 1
        assert init_call_count == 1, (
            f"Model was initialized {init_call_count} times, expected 1. "
            f"This indicates a race condition where multiple threads are "
            f"initializing the model concurrently."
        )

        # All threads should have gotten results (no errors from race condition)
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == num_threads

    def test_sequential_calls_reuse_initialized_model(self):
        """
        GIVEN a LangChainBridge with an initialized model
        WHEN subsequent calls are made
        THEN the existing model should be reused (not re-initialized)
        """
        init_call_count = 0

        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content='{"proposals": []}')

        def mock_create_chat_model(model_spec, config):
            nonlocal init_call_count
            init_call_count += 1
            return mock_model

        config = ProviderConfig.from_env()
        mock_factory = Mock()
        mock_factory.create_chat_model = mock_create_chat_model

        mock_circuit_breaker = Mock()
        mock_circuit_breaker.is_open.return_value = False
        mock_circuit_breaker.record_success = Mock()

        # Mock cache to always miss
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache.set = Mock()

        bridge = LangChainBridge(
            model="test/model",
            config=config,
            model_factory=mock_factory,
            circuit_breaker=mock_circuit_breaker,
            response_cache=mock_cache,
        )

        # Make multiple sequential calls
        for i in range(5):
            bridge.generate_correction_proposals(prompt=f"prompt {i}", schema={})

        # Model should only be initialized once (on first call)
        assert init_call_count == 1, (
            f"Model was initialized {init_call_count} times for sequential calls, "
            f"expected 1. Model should be reused after first initialization."
        )

    def test_model_initialization_failure_does_not_block_other_threads(self):
        """
        GIVEN a LangChainBridge where model initialization fails
        WHEN multiple threads try to initialize
        THEN failed initialization should not permanently block other threads
        """
        init_attempts = 0
        init_lock = threading.Lock()

        def mock_create_chat_model_failing(model_spec, config):
            nonlocal init_attempts
            with init_lock:
                init_attempts += 1
            time.sleep(0.05)
            raise Exception("Simulated initialization failure")

        config = ProviderConfig.from_env()
        mock_factory = Mock()
        mock_factory.create_chat_model = mock_create_chat_model_failing

        mock_circuit_breaker = Mock()
        mock_circuit_breaker.is_open.return_value = False
        mock_circuit_breaker.record_failure = Mock()

        # Mock cache to always miss
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache.set = Mock()

        bridge = LangChainBridge(
            model="test/model",
            config=config,
            model_factory=mock_factory,
            circuit_breaker=mock_circuit_breaker,
            response_cache=mock_cache,
        )

        num_threads = 3
        results = []

        def call_generate():
            return bridge.generate_correction_proposals(prompt="test", schema={})

        barrier = threading.Barrier(num_threads)

        def synchronized_call():
            barrier.wait()
            return call_generate()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(synchronized_call) for _ in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())

        # All threads should get error responses (not hang indefinitely)
        assert len(results) == num_threads
        for result in results:
            assert "error" in result[0], f"Expected error response, got: {result}"


class TestLangChainBridgeInitializationTiming:
    """Test that thread-safe initialization doesn't significantly impact performance."""

    def test_waiting_threads_get_result_promptly_after_init_completes(self):
        """
        GIVEN multiple threads waiting for model initialization
        WHEN the first thread completes initialization
        THEN waiting threads should proceed promptly (not restart initialization)
        """
        init_start_times = []
        init_end_times = []
        call_complete_times = []
        times_lock = threading.Lock()

        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content='{"proposals": []}')

        def mock_create_chat_model(model_spec, config):
            with times_lock:
                init_start_times.append(time.time())
            # Simulate 200ms initialization time
            time.sleep(0.2)
            with times_lock:
                init_end_times.append(time.time())
            return mock_model

        config = ProviderConfig.from_env()
        mock_factory = Mock()
        mock_factory.create_chat_model = mock_create_chat_model

        mock_circuit_breaker = Mock()
        mock_circuit_breaker.is_open.return_value = False
        mock_circuit_breaker.record_success = Mock()

        # Mock cache to always miss
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache.set = Mock()

        bridge = LangChainBridge(
            model="test/model",
            config=config,
            model_factory=mock_factory,
            circuit_breaker=mock_circuit_breaker,
            response_cache=mock_cache,
        )

        num_threads = 5
        barrier = threading.Barrier(num_threads)

        def synchronized_call():
            barrier.wait()
            start = time.time()
            bridge.generate_correction_proposals(prompt="test", schema={})
            with times_lock:
                call_complete_times.append(time.time() - start)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(synchronized_call) for _ in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # Only one initialization should have occurred
        assert len(init_start_times) == 1, (
            f"Expected 1 initialization, got {len(init_start_times)}"
        )

        # All calls should complete within reasonable time
        # (init time + small overhead, not init_time * num_threads)
        max_call_time = max(call_complete_times)
        # Allow 500ms total (200ms init + 300ms overhead for model invocation)
        assert max_call_time < 0.5, (
            f"Slowest call took {max_call_time:.2f}s, expected < 0.5s. "
            f"This suggests threads are initializing sequentially instead of waiting."
        )
