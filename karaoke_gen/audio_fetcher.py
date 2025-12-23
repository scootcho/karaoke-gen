"""
Audio Fetcher module - abstraction layer for fetching audio files.

This module provides a clean interface for searching and downloading audio files
using flacfetch, replacing the previous direct yt-dlp usage.
"""

import logging
import os
import signal
import sys
import tempfile
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any

# Global flag to track if user requested cancellation via Ctrl+C
_interrupt_requested = False


@dataclass
class AudioSearchResult:
    """Represents a single search result for audio.
    
    Used by both local CLI and cloud backend. Supports serialization
    for Firestore storage via to_dict()/from_dict().
    
    For rich display, this class can serialize the full flacfetch Release
    data so remote CLIs can use flacfetch's shared display functions.
    """

    title: str
    artist: str
    url: str
    provider: str
    duration: Optional[int] = None  # Duration in seconds
    quality: Optional[str] = None  # e.g., "FLAC", "320kbps", etc.
    source_id: Optional[str] = None  # Unique ID from the source
    index: int = 0  # Index in the results list (for API selection)
    seeders: Optional[int] = None  # Number of seeders (for torrent sources)
    target_file: Optional[str] = None  # Target filename in the release
    # Raw result object from the provider (for download) - not serialized
    raw_result: Optional[object] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON/Firestore serialization.
        
        Includes full flacfetch Release data if available, enabling
        remote CLIs to use flacfetch's shared display functions.
        """
        result = {
            "title": self.title,
            "artist": self.artist,
            "url": self.url,
            "provider": self.provider,
            "duration": self.duration,
            "quality": self.quality,
            "source_id": self.source_id,
            "index": self.index,
            "seeders": self.seeders,
            "target_file": self.target_file,
        }
        
        # If we have a raw_result (flacfetch Release), include its full data
        # This enables rich display on the remote CLI
        if self.raw_result:
            try:
                release_dict = self.raw_result.to_dict()
                # Merge Release fields into result (they may override basic fields)
                for key in ['year', 'label', 'edition_info', 'release_type', 'channel',
                           'view_count', 'size_bytes', 'target_file_size', 'track_pattern',
                           'match_score', 'formatted_size', 'formatted_duration',
                           'formatted_views', 'is_lossless', 'quality_str', 'quality']:
                    if key in release_dict:
                        # Use 'quality_data' for the quality dict to avoid confusion with quality string
                        result_key = 'quality_data' if key == 'quality' else key
                        result[result_key] = release_dict[key]
            except AttributeError:
                pass  # raw_result doesn't have to_dict() method
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioSearchResult":
        """Create from dict (e.g., from Firestore)."""
        return cls(
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            url=data.get("url", ""),
            provider=data.get("provider", "Unknown"),
            duration=data.get("duration"),
            quality=data.get("quality"),
            source_id=data.get("source_id"),
            index=data.get("index", 0),
            seeders=data.get("seeders"),
            target_file=data.get("target_file"),
            raw_result=None,  # Not stored in serialized form
        )


@dataclass
class AudioFetchResult:
    """Result of an audio fetch operation.
    
    Used by both local CLI and cloud backend. Supports serialization
    for Firestore storage via to_dict()/from_dict().
    """

    filepath: str
    artist: str
    title: str
    provider: str
    duration: Optional[int] = None
    quality: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON/Firestore serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioFetchResult":
        """Create from dict (e.g., from Firestore)."""
        return cls(
            filepath=data.get("filepath", ""),
            artist=data.get("artist", ""),
            title=data.get("title", ""),
            provider=data.get("provider", "Unknown"),
            duration=data.get("duration"),
            quality=data.get("quality"),
        )


class AudioFetcherError(Exception):
    """Base exception for audio fetcher errors."""

    pass


class NoResultsError(AudioFetcherError):
    """Raised when no search results are found."""

    pass


class DownloadError(AudioFetcherError):
    """Raised when download fails."""

    pass


class UserCancelledError(AudioFetcherError):
    """Raised when user explicitly cancels the operation (e.g., enters 0 or Ctrl+C)."""

    pass


def _check_interrupt():
    """Check if interrupt was requested and raise UserCancelledError if so."""
    global _interrupt_requested
    if _interrupt_requested:
        raise UserCancelledError("Operation cancelled by user")


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
    
    Also exported as FlacFetcher for shorter name.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        red_api_key: Optional[str] = None,
        red_api_url: Optional[str] = None,
        ops_api_key: Optional[str] = None,
        ops_api_url: Optional[str] = None,
        provider_priority: Optional[List[str]] = None,
    ):
        """
        Initialize the FlacFetch audio fetcher.

        Args:
            logger: Logger instance for output
            red_api_key: API key for RED tracker (optional)
            red_api_url: Base URL for RED tracker API (optional, required if using RED)
            ops_api_key: API key for OPS tracker (optional)
            ops_api_url: Base URL for OPS tracker API (optional, required if using OPS)
            provider_priority: Custom provider priority order (optional)
        """
        self.logger = logger or logging.getLogger(__name__)
        self._red_api_key = red_api_key or os.environ.get("RED_API_KEY")
        self._red_api_url = red_api_url or os.environ.get("RED_API_URL")
        self._ops_api_key = ops_api_key or os.environ.get("OPS_API_KEY")
        self._ops_api_url = ops_api_url or os.environ.get("OPS_API_URL")
        self._provider_priority = provider_priority
        self._manager = None
        self._transmission_available = None  # Cached result of Transmission check

    def _check_transmission_available(self) -> bool:
        """
        Check if Transmission daemon is available for torrent downloads.
        
        This prevents adding tracker providers (RED/OPS) when Transmission
        isn't running, which would result in search results that can't be downloaded.
        
        Returns:
            True if Transmission is available and responsive, False otherwise.
        """
        if self._transmission_available is not None:
            self.logger.info(f"[Transmission] Using cached status: available={self._transmission_available}")
            return self._transmission_available
        
        host = os.environ.get("TRANSMISSION_HOST", "localhost")
        port = int(os.environ.get("TRANSMISSION_PORT", "9091"))
        self.logger.info(f"[Transmission] Checking availability at {host}:{port}")
        
        try:
            import transmission_rpc
            self.logger.info(f"[Transmission] transmission_rpc imported successfully")
            
            client = transmission_rpc.Client(host=host, port=port, timeout=5)
            self.logger.info(f"[Transmission] Client created, calling session_stats()...")
            
            # Simple test to verify connection works
            stats = client.session_stats()
            self.logger.info(f"[Transmission] Connected! Download dir: {getattr(stats, 'download_dir', 'unknown')}")
            
            self._transmission_available = True
        except ImportError as e:
            self._transmission_available = False
            self.logger.warning(f"[Transmission] transmission_rpc not installed: {e}")
        except Exception as e:
            self._transmission_available = False
            self.logger.warning(f"[Transmission] Connection failed to {host}:{port}: {type(e).__name__}: {e}")
        
        self.logger.info(f"[Transmission] Final status: available={self._transmission_available}")
        return self._transmission_available

    def _get_manager(self):
        """Lazily initialize and return the FetchManager."""
        if self._manager is None:
            # Import flacfetch here to avoid import errors if not installed
            from flacfetch.core.manager import FetchManager
            from flacfetch.providers.youtube import YoutubeProvider
            from flacfetch.downloaders.youtube import YoutubeDownloader

            # Try to import TorrentDownloader (has optional dependencies)
            TorrentDownloader = None
            try:
                from flacfetch.downloaders.torrent import TorrentDownloader
            except ImportError:
                self.logger.debug("TorrentDownloader not available (missing dependencies)")

            self._manager = FetchManager()

            # Only add tracker providers if we can actually download from them
            # This requires both TorrentDownloader and a running Transmission daemon
            has_torrent_downloader = TorrentDownloader is not None
            transmission_available = self._check_transmission_available()
            can_use_trackers = has_torrent_downloader and transmission_available
            
            self.logger.info(
                f"[FlacFetcher] Provider setup: TorrentDownloader={has_torrent_downloader}, "
                f"Transmission={transmission_available}, can_use_trackers={can_use_trackers}"
            )
            
            if not can_use_trackers and (self._red_api_key or self._ops_api_key):
                self.logger.warning(
                    "[FlacFetcher] Tracker providers (RED/OPS) DISABLED: "
                    f"TorrentDownloader={has_torrent_downloader}, Transmission={transmission_available}. "
                    "Only YouTube sources will be used."
                )

            # Add providers and downloaders based on available API keys and URLs
            if self._red_api_key and self._red_api_url and can_use_trackers:
                from flacfetch.providers.red import REDProvider

                self._manager.add_provider(REDProvider(api_key=self._red_api_key, base_url=self._red_api_url))
                self._manager.register_downloader("RED", TorrentDownloader())
                self.logger.info("[FlacFetcher] Added RED provider with TorrentDownloader")
            elif self._red_api_key and not self._red_api_url:
                self.logger.warning("[FlacFetcher] RED_API_KEY set but RED_API_URL not set - RED provider disabled")

            if self._ops_api_key and self._ops_api_url and can_use_trackers:
                from flacfetch.providers.ops import OPSProvider

                self._manager.add_provider(OPSProvider(api_key=self._ops_api_key, base_url=self._ops_api_url))
                self._manager.register_downloader("OPS", TorrentDownloader())
                self.logger.info("[FlacFetcher] Added OPS provider with TorrentDownloader")
            elif self._ops_api_key and not self._ops_api_url:
                self.logger.warning("[FlacFetcher] OPS_API_KEY set but OPS_API_URL not set - OPS provider disabled")

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
        for i, result in enumerate(results):
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
                    index=i,  # Set index for API selection
                    seeders=getattr(result, "seeders", None),
                    target_file=getattr(result, "target_file", None),
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

    def select_best(self, results: List[AudioSearchResult]) -> int:
        """
        Select the best result from a list of search results.
        
        Uses flacfetch's built-in quality ranking to determine the best source.
        This is useful for automated/non-interactive usage.
        
        Args:
            results: List of AudioSearchResult objects from search()
            
        Returns:
            Index of the best result in the list
        """
        if not results:
            return 0
        
        manager = self._get_manager()
        
        # Get raw results that have raw_result set
        raw_results = [r.raw_result for r in results if r.raw_result is not None]
        
        if raw_results:
            try:
                best = manager.select_best(raw_results)
                # Find index of best result
                for i, r in enumerate(results):
                    if r.raw_result == best:
                        return i
            except Exception as e:
                self.logger.warning(f"select_best failed, using first result: {e}")
        
        # Fallback: return first result
        return 0

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
            UserCancelledError: If user cancels (Ctrl+C or enters 0)
        """
        from flacfetch.core.models import TrackQuery

        manager = self._get_manager()
        query = TrackQuery(artist=artist, title=title)

        self.logger.info(f"Searching for: {artist} - {title}")
        
        # Run search in a thread so we can handle Ctrl+C
        results = self._interruptible_search(manager, query)

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

        # Note: _interactive_select now raises UserCancelledError instead of returning None
        # This check is kept as a safety net
        if selected is None:
            raise NoResultsError(f"No result selected for: {artist} - {title}")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename if not provided
        if output_filename is None:
            output_filename = f"{artist} - {title}"

        self.logger.info(f"Downloading from {getattr(selected, 'source_name', 'Unknown')}...")

        try:
            # Use interruptible download so Ctrl+C works during torrent downloads
            filepath = self._interruptible_download(
                manager,
                selected,
                output_path=output_dir,
                output_filename=output_filename,
            )

            if not filepath:
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

        except (UserCancelledError, KeyboardInterrupt):
            # Let cancellation exceptions propagate without wrapping
            raise
        except Exception as e:
            raise DownloadError(f"Failed to download {artist} - {title}: {e}") from e

    def _interruptible_search(self, manager, query) -> list:
        """
        Run search in a way that can be interrupted by Ctrl+C.
        
        The flacfetch search is a blocking network operation that doesn't
        respond to SIGINT while running. This method runs it in a background
        thread and periodically checks for interrupts.
        
        Args:
            manager: The FetchManager instance
            query: The TrackQuery to search for
            
        Returns:
            List of search results
            
        Raises:
            UserCancelledError: If user presses Ctrl+C during search
        """
        global _interrupt_requested
        _interrupt_requested = False
        result_container = {"results": None, "error": None}
        
        def do_search():
            try:
                result_container["results"] = manager.search(query)
            except Exception as e:
                result_container["error"] = e
        
        # Set up signal handler for immediate response to Ctrl+C
        original_handler = signal.getsignal(signal.SIGINT)
        
        def interrupt_handler(signum, frame):
            global _interrupt_requested
            _interrupt_requested = True
            # Print immediately so user knows it was received
            print("\nCancelling... please wait", file=sys.stderr)
        
        signal.signal(signal.SIGINT, interrupt_handler)
        
        try:
            # Start search in background thread
            search_thread = threading.Thread(target=do_search, daemon=True)
            search_thread.start()
            
            # Wait for completion with periodic interrupt checks
            while search_thread.is_alive():
                search_thread.join(timeout=0.1)  # Check every 100ms
                if _interrupt_requested:
                    # Don't wait for thread - it's a daemon and will be killed
                    raise UserCancelledError("Search cancelled by user (Ctrl+C)")
            
            # Check for errors from the search
            if result_container["error"] is not None:
                raise result_container["error"]
                
            return result_container["results"]
            
        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, original_handler)
            _interrupt_requested = False

    def _interruptible_download(self, manager, selected, output_path: str, output_filename: str) -> str:
        """
        Run download in a way that can be interrupted by Ctrl+C.
        
        The flacfetch/transmission download is a blocking operation that doesn't
        respond to SIGINT while running (especially for torrent downloads).
        This method runs it in a background thread and periodically checks for interrupts.
        
        Args:
            manager: The FetchManager instance
            selected: The selected result to download
            output_path: Directory to save the file
            output_filename: Filename to save as
            
        Returns:
            Path to the downloaded file
            
        Raises:
            UserCancelledError: If user presses Ctrl+C during download
            DownloadError: If download fails
        """
        global _interrupt_requested
        _interrupt_requested = False
        result_container = {"filepath": None, "error": None}
        was_cancelled = False
        
        def do_download():
            try:
                result_container["filepath"] = manager.download(
                    selected,
                    output_path=output_path,
                    output_filename=output_filename,
                )
            except Exception as e:
                result_container["error"] = e
        
        # Set up signal handler for immediate response to Ctrl+C
        original_handler = signal.getsignal(signal.SIGINT)
        
        def interrupt_handler(signum, frame):
            global _interrupt_requested
            _interrupt_requested = True
            # Print immediately so user knows it was received
            print("\nCancelling download... please wait (may take a few seconds)", file=sys.stderr)
        
        signal.signal(signal.SIGINT, interrupt_handler)
        
        try:
            # Start download in background thread
            download_thread = threading.Thread(target=do_download, daemon=True)
            download_thread.start()
            
            # Wait for completion with periodic interrupt checks
            while download_thread.is_alive():
                download_thread.join(timeout=0.2)  # Check every 200ms
                if _interrupt_requested:
                    was_cancelled = True
                    # Clean up any pending torrents before raising
                    self._cleanup_transmission_torrents(selected)
                    raise UserCancelledError("Download cancelled by user (Ctrl+C)")
            
            # Check for errors from the download
            if result_container["error"] is not None:
                raise result_container["error"]
                
            return result_container["filepath"]
            
        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, original_handler)
            _interrupt_requested = False

    def _cleanup_transmission_torrents(self, selected) -> None:
        """
        Clean up any torrents in Transmission that were started for this download.
        
        Called when a download is cancelled to remove incomplete torrents and their data.
        
        Args:
            selected: The selected result that was being downloaded
        """
        try:
            import transmission_rpc
            host = os.environ.get("TRANSMISSION_HOST", "localhost")
            port = int(os.environ.get("TRANSMISSION_PORT", "9091"))
            client = transmission_rpc.Client(host=host, port=port, timeout=5)
            
            # Get the release name to match against torrents
            release_name = getattr(selected, 'name', None) or getattr(selected, 'title', None)
            if not release_name:
                self.logger.debug("[Transmission] No release name to match for cleanup")
                return
            
            # Find and remove matching incomplete torrents
            torrents = client.get_torrents()
            for torrent in torrents:
                # Match by name similarity and incomplete status
                if torrent.progress < 100 and release_name.lower() in torrent.name.lower():
                    self.logger.info(f"[Transmission] Removing cancelled torrent: {torrent.name}")
                    client.remove_torrent(torrent.id, delete_data=True)
                    
        except Exception as e:
            # Don't fail the cancellation if cleanup fails
            self.logger.debug(f"[Transmission] Cleanup failed (non-fatal): {e}")

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
            
        Raises:
            UserCancelledError: If user cancels selection
        """
        try:
            # Use flacfetch's built-in CLIHandler for rich display
            from flacfetch.interface.cli import CLIHandler

            handler = CLIHandler(target_artist=artist)
            result = handler.select_release(results)
            if result is None:
                # User selected 0 to cancel
                raise UserCancelledError("Selection cancelled by user")
            return result
        except ImportError:
            # Fallback to basic display if CLIHandler not available
            return self._basic_interactive_select(results, artist, title)
        except (KeyboardInterrupt, EOFError):
            raise UserCancelledError("Selection cancelled by user (Ctrl+C)")
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
            
        Raises:
            UserCancelledError: If user cancels selection
        """
        # Use flacfetch's shared display function
        from flacfetch import print_releases
        print_releases(results, target_artist=artist, use_colors=True)

        while True:
            try:
                choice = input("Enter your choice (1-{}, or 0 to cancel): ".format(len(results))).strip()

                if choice == "0":
                    self.logger.info("User cancelled selection")
                    raise UserCancelledError("Selection cancelled by user")

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
                raise UserCancelledError("Selection cancelled by user (Ctrl+C)")


# Alias for shorter name - used by backend and other consumers
FlacFetcher = FlacFetchAudioFetcher


def create_audio_fetcher(
    logger: Optional[logging.Logger] = None,
    red_api_key: Optional[str] = None,
    red_api_url: Optional[str] = None,
    ops_api_key: Optional[str] = None,
    ops_api_url: Optional[str] = None,
) -> AudioFetcher:
    """
    Factory function to create an appropriate AudioFetcher instance.

    Args:
        logger: Logger instance for output
        red_api_key: API key for RED tracker (optional)
        red_api_url: Base URL for RED tracker API (optional, required if using RED)
        ops_api_key: API key for OPS tracker (optional)
        ops_api_url: Base URL for OPS tracker API (optional, required if using OPS)

    Returns:
        An AudioFetcher instance
    """
    return FlacFetchAudioFetcher(
        logger=logger,
        red_api_key=red_api_key,
        red_api_url=red_api_url,
        ops_api_key=ops_api_key,
        ops_api_url=ops_api_url,
    )
