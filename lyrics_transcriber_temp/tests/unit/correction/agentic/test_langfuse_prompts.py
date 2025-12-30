"""Tests for LangFuse prompt management integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from lyrics_transcriber.correction.agentic.prompts.langfuse_prompts import (
    LangFusePromptService,
    LangFusePromptError,
    LangFuseDatasetError,
    get_prompt_service,
    reset_prompt_service,
)
from lyrics_transcriber.correction.agentic.observability.langfuse_integration import (
    get_langfuse_client,
    reset_langfuse_client,
    fetch_prompt,
    fetch_dataset,
    is_langfuse_configured,
    LangFuseConfigError,
)


class TestLangFusePromptService:
    """Tests for the LangFusePromptService class."""

    def setup_method(self):
        """Reset singletons before each test."""
        reset_prompt_service()
        reset_langfuse_client()

    def teardown_method(self):
        """Clean up after each test."""
        reset_prompt_service()
        reset_langfuse_client()

    def test_service_uses_hardcoded_when_langfuse_not_configured(self):
        """Service falls back to hardcoded prompts when LangFuse keys not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove LangFuse keys
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            service = LangFusePromptService()

            # Should not use LangFuse
            assert not service._use_langfuse
            assert service._client is None

    def test_service_uses_langfuse_when_configured(self):
        """Service uses LangFuse when keys are set."""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            with patch("langfuse.Langfuse") as mock_langfuse:
                mock_client = Mock()
                mock_langfuse.return_value = mock_client

                service = LangFusePromptService()

                assert service._use_langfuse
                assert service._client == mock_client

    def test_service_fails_fast_on_init_error(self):
        """Service raises error if LangFuse keys set but init fails."""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            with patch("langfuse.Langfuse") as mock_langfuse:
                mock_langfuse.side_effect = Exception("Connection failed")

                with pytest.raises(RuntimeError) as excinfo:
                    LangFusePromptService()

                assert "initialization failed" in str(excinfo.value)

    def test_get_classification_prompt_hardcoded_fallback(self):
        """get_classification_prompt returns hardcoded prompt when LangFuse not configured."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            service = LangFusePromptService()
            prompt = service.get_classification_prompt(
                gap_text="out, I'm starting",
                preceding_words="Oh no, was it",
                following_words="gonna sleep",
                reference_contexts={"genius": "now, I'm starting"},
                artist="Test Artist",
                title="Test Song",
                gap_id="gap_1",
            )

            # Should contain key elements of the hardcoded prompt
            assert "transcription errors" in prompt
            assert "SOUND_ALIKE" in prompt
            assert "PUNCTUATION_ONLY" in prompt
            assert "gap_1" in prompt
            assert "Test Artist" in prompt

    def test_get_classification_prompt_from_langfuse(self):
        """get_classification_prompt fetches from LangFuse when configured."""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            # Create mock client
            mock_client = Mock()

            # Mock prompt
            mock_prompt = Mock()
            mock_prompt.compile.return_value = "Compiled prompt with {{gap_text}}"
            mock_client.get_prompt.return_value = mock_prompt

            # Mock dataset
            mock_dataset = Mock()
            mock_item = Mock()
            mock_item.input = {"category": "sound_alike", "gap_text": "example"}
            mock_dataset.items = [mock_item]
            mock_client.get_dataset.return_value = mock_dataset

            with patch("langfuse.Langfuse", return_value=mock_client):
                service = LangFusePromptService()
                prompt = service.get_classification_prompt(
                    gap_text="test gap",
                    preceding_words="before",
                    following_words="after",
                    reference_contexts={"source": "reference"},
                    gap_id="gap_1",
                )

                # Verify prompt was returned from compile
                assert prompt == "Compiled prompt with {{gap_text}}"
                # Verify LangFuse was called with label parameter
                mock_client.get_prompt.assert_called_once_with("gap-classifier", label="production")
                mock_client.get_dataset.assert_called_once_with("gap-classifier-examples")
                mock_prompt.compile.assert_called_once()

    def test_service_raises_on_prompt_fetch_error(self):
        """Service raises LangFusePromptError on fetch failure."""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            mock_client = Mock()
            mock_client.get_prompt.side_effect = Exception("Network error")

            with patch("langfuse.Langfuse", return_value=mock_client):
                service = LangFusePromptService()

                with pytest.raises(LangFusePromptError) as excinfo:
                    service.get_classification_prompt(
                        gap_text="test",
                        preceding_words="before",
                        following_words="after",
                        reference_contexts={},
                    )

                assert "Failed to fetch" in str(excinfo.value)


class TestLangFuseIntegration:
    """Tests for the langfuse_integration module functions."""

    def setup_method(self):
        """Reset singletons before each test."""
        reset_langfuse_client()

    def teardown_method(self):
        """Clean up after each test."""
        reset_langfuse_client()

    def test_is_langfuse_configured_false_when_no_keys(self):
        """is_langfuse_configured returns False when keys not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            assert not is_langfuse_configured()

    def test_is_langfuse_configured_true_when_keys_set(self):
        """is_langfuse_configured returns True when both keys set."""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            assert is_langfuse_configured()

    def test_get_langfuse_client_returns_none_when_not_configured(self):
        """get_langfuse_client returns None when keys not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            client = get_langfuse_client()
            assert client is None

    def test_get_langfuse_client_fails_fast_on_error(self):
        """get_langfuse_client raises LangFuseConfigError on init failure."""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            with patch("langfuse.Langfuse") as mock_langfuse:
                mock_langfuse.side_effect = Exception("Auth failed")

                with pytest.raises(LangFuseConfigError) as excinfo:
                    get_langfuse_client()

                assert "initialization failed" in str(excinfo.value)

    def test_fetch_prompt_raises_when_not_configured(self):
        """fetch_prompt raises LangFuseConfigError when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            with pytest.raises(LangFuseConfigError):
                fetch_prompt("test-prompt")

    def test_fetch_dataset_raises_when_not_configured(self):
        """fetch_dataset raises LangFuseConfigError when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            with pytest.raises(LangFuseConfigError):
                fetch_dataset("test-dataset")


class TestPromptServiceSingleton:
    """Tests for the prompt service singleton pattern."""

    def setup_method(self):
        """Reset singletons before each test."""
        reset_prompt_service()
        reset_langfuse_client()

    def teardown_method(self):
        """Clean up after each test."""
        reset_prompt_service()
        reset_langfuse_client()

    def test_get_prompt_service_returns_same_instance(self):
        """get_prompt_service returns the same instance on subsequent calls."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            service1 = get_prompt_service()
            service2 = get_prompt_service()

            assert service1 is service2

    def test_reset_prompt_service_clears_singleton(self):
        """reset_prompt_service clears the singleton instance."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            service1 = get_prompt_service()
            reset_prompt_service()
            service2 = get_prompt_service()

            assert service1 is not service2


class TestBuildClassificationPrompt:
    """Tests for the build_classification_prompt function."""

    def setup_method(self):
        """Reset singletons before each test."""
        reset_prompt_service()
        reset_langfuse_client()

    def teardown_method(self):
        """Clean up after each test."""
        reset_prompt_service()
        reset_langfuse_client()

    def test_build_classification_prompt_works_without_langfuse(self):
        """build_classification_prompt works when LangFuse not configured."""
        from lyrics_transcriber.correction.agentic.prompts.classifier import build_classification_prompt

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            prompt = build_classification_prompt(
                gap_text="test gap text",
                preceding_words="words before",
                following_words="words after",
                reference_contexts={"genius": "reference text"},
                artist="Artist Name",
                title="Song Title",
                gap_id="gap_123",
            )

            # Verify prompt contains expected content
            assert "test gap text" in prompt
            assert "words before" in prompt
            assert "words after" in prompt
            assert "gap_123" in prompt
            assert "Artist Name" in prompt
            assert "Song Title" in prompt
            assert "GENIUS" in prompt  # Source name should be uppercase
            assert "SOUND_ALIKE" in prompt  # Categories should be present
