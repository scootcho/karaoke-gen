"""
Audio Fetcher module - abstraction layer for fetching audio files.

This module provides a clean interface for searching and downloading audio files
using flacfetch, replacing the previous direct yt-dlp usage.
"""

import logging
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AudioSearchResult:
    """Represents a single search result for audio."""

    title: str
    artist: str
    url: str
    provider: str
    duration: Optional[int] = None  # Duration in seconds
    quality: Optional[str] = None  # e.g., "FLAC", "320kbps", etc.
    source_id: Optional[str] = None  # Unique ID from the source
    # Raw result object from the provider (for download)
    raw_result: Optional[object] = None


@dataclass
class AudioFetchResult:
    """Result of an audio fetch operation."""

    filepath: str
    artist: str
    title: str
    provider: str
    duration: Optional[int] = None
    quality: Optional[str] = None


class AudioFetcherError(Exception):
    """Base exception for audio fetcher errors."""

    pass


class NoResultsError(AudioFetcherError):
    """Raised when no search results are found."""

    pass


class DownloadError(AudioFetcherError):
    """Raised when download fails."""

    pass


class AudioFetcher(ABC):
    """Abstract base class for audio fetching implementations."""

    @abstractmethod
    def search(self, artist: str, title: str) -> List[AudioSearchResult]:
        """
        Search for audio matching the given artist and title.

        Args:
            artist: The artist name to search for
            title: The track title to search for

        Returns:
            List of AudioSearchResult objects

        Raises:
            NoResultsError: If no results are found
            AudioFetcherError: For other errors
        """
        pass

    @abstractmethod
    def download(
        self,
        result: AudioSearchResult,
        output_dir: str,
        output_filename: Optional[str] = None,
    ) -> AudioFetchResult:
        """
        Download audio from a search result.

        Args:
            result: The search result to download
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)

        Returns:
            AudioFetchResult with the downloaded file path

        Raises:
            DownloadError: If download fails
        """
        pass

    @abstractmethod
    def search_and_download(
        self,
        artist: str,
        title: str,
        output_dir: str,
        output_filename: Optional[str] = None,
        auto_select: bool = False,
    ) -> AudioFetchResult:
        """
        Search for audio and download it in one operation.

        In interactive mode (auto_select=False), this will present options to the user.
        In auto mode (auto_select=True), this will automatically select the best result.

        Args:
            artist: The artist name to search for
            title: The track title to search for
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)
            auto_select: If True, automatically select the best result

        Returns:
            AudioFetchResult with the downloaded file path

        Raises:
            NoResultsError: If no results are found
            DownloadError: If download fails
        """
        pass


class FlacFetchAudioFetcher(AudioFetcher):
    """
    Audio fetcher implementation using flacfetch library.

    This provides access to multiple audio sources including private music trackers
    and YouTube, with intelligent prioritization of high-quality sources.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        redacted_api_key: Optional[str] = None,
        ops_api_key: Optional[str] = None,
        provider_priority: Optional[List[str]] = None,
    ):
        """
        Initialize the FlacFetch audio fetcher.

        Args:
            logger: Logger instance for output
            redacted_api_key: API key for Redacted tracker (optional)
            ops_api_key: API key for OPS tracker (optional)
            provider_priority: Custom provider priority order (optional)
        """
        self.logger = logger or logging.getLogger(__name__)
        self._redacted_api_key = redacted_api_key or os.environ.get("REDACTED_API_KEY")
        self._ops_api_key = ops_api_key or os.environ.get("OPS_API_KEY")
        self._provider_priority = provider_priority
        self._manager = None

    def _get_manager(self):
        """Lazily initialize and return the FetchManager."""
        if self._manager is None:
            # Import flacfetch here to avoid import errors if not installed
            from flacfetch.core.manager import FetchManager
            from flacfetch.providers.youtube import YoutubeProvider
            from flacfetch.downloaders.youtube import YoutubeDownloader

            # Try to import TorrentDownloader (has optional dependencies)
            try:
                from flacfetch.downloaders.torrent import TorrentDownloader
            except ImportError:
                TorrentDownloader = None
                self.logger.debug("TorrentDownloader not available (missing dependencies)")

            self._manager = FetchManager()

            # Add providers and downloaders based on available API keys
            if self._redacted_api_key:
                from flacfetch.providers.redacted import RedactedProvider

                self._manager.add_provider(RedactedProvider(api_key=self._redacted_api_key))
                if TorrentDownloader:
                    self._manager.register_downloader("Redacted", TorrentDownloader())
                self.logger.debug("Added Redacted provider")

            if self._ops_api_key:
                from flacfetch.providers.ops import OPSProvider

                self._manager.add_provider(OPSProvider(api_key=self._ops_api_key))
                if TorrentDownloader:
                    self._manager.register_downloader("OPS", TorrentDownloader())
                self.logger.debug("Added OPS provider")

            # Always add YouTube as a fallback provider with its downloader
            self._manager.add_provider(YoutubeProvider())
            self._manager.register_downloader("YouTube", YoutubeDownloader())
            self.logger.debug("Added YouTube provider")

        return self._manager

    def search(self, artist: str, title: str) -> List[AudioSearchResult]:
        """
        Search for audio matching the given artist and title.

        Args:
            artist: The artist name to search for
            title: The track title to search for

        Returns:
            List of AudioSearchResult objects

        Raises:
            NoResultsError: If no results are found
        """
        from flacfetch.core.models import TrackQuery

        manager = self._get_manager()
        query = TrackQuery(artist=artist, title=title)

        self.logger.info(f"Searching for: {artist} - {title}")
        results = manager.search(query)

        if not results:
            raise NoResultsError(f"No results found for: {artist} - {title}")

        # Convert to our AudioSearchResult format
        search_results = []
        for result in results:
            # Get quality as string if it's a Quality object
            quality = getattr(result, "quality", None)
            quality_str = str(quality) if quality else None

            search_results.append(
                AudioSearchResult(
                    title=getattr(result, "title", title),
                    artist=getattr(result, "artist", artist),
                    url=getattr(result, "download_url", "") or "",
                    provider=getattr(result, "source_name", "Unknown"),
                    duration=getattr(result, "duration_seconds", None),
                    quality=quality_str,
                    source_id=getattr(result, "info_hash", None),
                    raw_result=result,
                )
            )

        self.logger.info(f"Found {len(search_results)} results")
        return search_results

    def download(
        self,
        result: AudioSearchResult,
        output_dir: str,
        output_filename: Optional[str] = None,
    ) -> AudioFetchResult:
        """
        Download audio from a search result.

        Args:
            result: The search result to download
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)

        Returns:
            AudioFetchResult with the downloaded file path

        Raises:
            DownloadError: If download fails
        """
        manager = self._get_manager()

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename if not provided
        if output_filename is None:
            output_filename = f"{result.artist} - {result.title}"

        self.logger.info(f"Downloading: {result.artist} - {result.title} from {result.provider or 'Unknown'}")

        try:
            # Use flacfetch to download
            filepath = manager.download(
                result.raw_result,
                output_path=output_dir,
                output_filename=output_filename,
            )

            if filepath is None:
                raise DownloadError(f"Download returned no file path for: {result.artist} - {result.title}")

            self.logger.info(f"Downloaded to: {filepath}")

            return AudioFetchResult(
                filepath=filepath,
                artist=result.artist,
                title=result.title,
                provider=result.provider,
                duration=result.duration,
                quality=result.quality,
            )

        except Exception as e:
            raise DownloadError(f"Failed to download {result.artist} - {result.title}: {e}") from e

    def search_and_download(
        self,
        artist: str,
        title: str,
        output_dir: str,
        output_filename: Optional[str] = None,
        auto_select: bool = False,
    ) -> AudioFetchResult:
        """
        Search for audio and download it in one operation.

        In interactive mode (auto_select=False), this will present options to the user.
        In auto mode (auto_select=True), this will automatically select the best result.

        Args:
            artist: The artist name to search for
            title: The track title to search for
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)
            auto_select: If True, automatically select the best result

        Returns:
            AudioFetchResult with the downloaded file path

        Raises:
            NoResultsError: If no results are found
            DownloadError: If download fails
        """
        from flacfetch.core.models import TrackQuery

        manager = self._get_manager()
        query = TrackQuery(artist=artist, title=title)

        self.logger.info(f"Searching for: {artist} - {title}")
        results = manager.search(query)

        if not results:
            raise NoResultsError(f"No results found for: {artist} - {title}")

        self.logger.info(f"Found {len(results)} results")

        if auto_select:
            # Auto mode: select best result based on flacfetch's ranking
            selected = manager.select_best(results)
            self.logger.info(f"Auto-selected: {getattr(selected, 'title', title)} from {getattr(selected, 'source_name', 'Unknown')}")
        else:
            # Interactive mode: present options to user
            selected = self._interactive_select(results, artist, title)

        if selected is None:
            raise NoResultsError(f"No result selected for: {artist} - {title}")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename if not provided
        if output_filename is None:
            output_filename = f"{artist} - {title}"

        self.logger.info(f"Downloading from {getattr(selected, 'source_name', 'Unknown')}...")

        try:
            filepath = manager.download(
                selected,
                output_path=output_dir,
                output_filename=output_filename,
            )

            if filepath is None:
                raise DownloadError(f"Download returned no file path for: {artist} - {title}")

            self.logger.info(f"Downloaded to: {filepath}")

            # Get quality as string if it's a Quality object
            quality = getattr(selected, "quality", None)
            quality_str = str(quality) if quality else None

            return AudioFetchResult(
                filepath=filepath,
                artist=artist,
                title=title,
                provider=getattr(selected, "source_name", "Unknown"),
                duration=getattr(selected, "duration_seconds", None),
                quality=quality_str,
            )

        except Exception as e:
            raise DownloadError(f"Failed to download {artist} - {title}: {e}") from e

    def _interactive_select(self, results: list, artist: str, title: str) -> object:
        """
        Present search results to the user for interactive selection.

        Uses flacfetch's built-in CLIHandler for rich, colorized output.

        Args:
            results: List of Release objects from flacfetch
            artist: The artist name being searched
            title: The track title being searched

        Returns:
            The selected Release object
        """
        try:
            # Use flacfetch's built-in CLIHandler for rich display
            from flacfetch.interface.cli import CLIHandler

            handler = CLIHandler(target_artist=artist)
            return handler.select_release(results)
        except ImportError:
            # Fallback to basic display if CLIHandler not available
            return self._basic_interactive_select(results, artist, title)
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled")
            return None
        except (AttributeError, TypeError):
            # Fallback if results aren't proper Release objects (e.g., in tests)
            return self._basic_interactive_select(results, artist, title)

    def _basic_interactive_select(self, results: list, artist: str, title: str) -> object:
        """
        Basic fallback for interactive selection without rich formatting.

        Args:
            results: List of Release objects from flacfetch
            artist: The artist name being searched
            title: The track title being searched

        Returns:
            The selected Release object
        """
        print(f"\n{'=' * 60}")
        print(f"Search Results for: {artist} - {title}")
        print(f"{'=' * 60}\n")

        for i, result in enumerate(results, 1):
            # Use correct flacfetch attribute names
            source_name = getattr(result, "source_name", "Unknown")
            result_title = getattr(result, "title", "Unknown")
            result_artist = getattr(result, "artist", "Unknown")
            quality = getattr(result, "quality", None)
            duration_seconds = getattr(result, "duration_seconds", None)
            seeders = getattr(result, "seeders", None)
            target_file = getattr(result, "target_file", None)

            # Format duration if available
            duration_str = ""
            if duration_seconds:
                minutes = duration_seconds // 60
                seconds = duration_seconds % 60
                duration_str = f" [{minutes}:{seconds:02d}]"

            # Format quality - it's a Quality object with __str__
            quality_str = f" ({quality})" if quality else ""

            # Format seeders for torrent sources
            seeders_str = f" Seeders: {seeders}" if seeders is not None else ""

            # Format target file
            file_str = f' "{target_file}"' if target_file else ""

            print(f"  {i}. [{source_name}] {result_artist} - {result_title}{quality_str}{duration_str}{seeders_str}{file_str}")

        print()
        print("  0. Cancel")
        print()

        while True:
            try:
                choice = input("Enter your choice (1-{}, or 0 to cancel): ".format(len(results))).strip()

                if choice == "0":
                    self.logger.info("User cancelled selection")
                    return None

                choice_num = int(choice)
                if 1 <= choice_num <= len(results):
                    selected = results[choice_num - 1]
                    self.logger.info(f"User selected option {choice_num}")
                    return selected
                else:
                    print(f"Please enter a number between 0 and {len(results)}")

            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nCancelled")
                return None


def create_audio_fetcher(
    logger: Optional[logging.Logger] = None,
    redacted_api_key: Optional[str] = None,
    ops_api_key: Optional[str] = None,
) -> AudioFetcher:
    """
    Factory function to create an appropriate AudioFetcher instance.

    Args:
        logger: Logger instance for output
        redacted_api_key: API key for Redacted tracker (optional)
        ops_api_key: API key for OPS tracker (optional)

    Returns:
        An AudioFetcher instance
    """
    return FlacFetchAudioFetcher(
        logger=logger,
        redacted_api_key=redacted_api_key,
        ops_api_key=ops_api_key,
    )
