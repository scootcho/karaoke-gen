"""
Audio search service for finding and downloading audio files.

This service integrates with flacfetch to search for audio from various sources
(YouTube, music trackers, etc.) and download the selected audio file.
"""
import logging
import os
import tempfile
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class AudioSearchResult:
    """
    Represents a single search result for audio.
    
    This is a serializable representation of a search result that can be
    stored in Firestore and sent to clients.
    """
    title: str
    artist: str
    provider: str
    url: str
    duration: Optional[int] = None  # Duration in seconds
    quality: Optional[str] = None  # e.g., "FLAC", "320kbps", etc.
    source_id: Optional[str] = None  # Unique ID from the source
    index: int = 0  # Index in the results list (for selection)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioSearchResult":
        """Create from dict."""
        return cls(**data)


@dataclass
class AudioDownloadResult:
    """Result of downloading an audio file."""
    filepath: str
    artist: str
    title: str
    provider: str
    duration: Optional[int] = None
    quality: Optional[str] = None


class AudioSearchError(Exception):
    """Base exception for audio search errors."""
    pass


class NoResultsError(AudioSearchError):
    """Raised when no search results are found."""
    pass


class DownloadError(AudioSearchError):
    """Raised when download fails."""
    pass


class AudioSearchService:
    """
    Service for searching and downloading audio files using flacfetch.
    
    This service is used by the backend to:
    1. Search for audio by artist/title
    2. Return results for user selection
    3. Download the selected audio to a local file
    """
    
    # Sentinel value to indicate "use environment variable"
    _USE_ENV = object()
    
    def __init__(
        self,
        redacted_api_key: Optional[str] = _USE_ENV,
        ops_api_key: Optional[str] = _USE_ENV,
    ):
        """
        Initialize the audio search service.
        
        Args:
            redacted_api_key: API key for Redacted tracker (optional, uses env if not provided)
            ops_api_key: API key for OPS tracker (optional, uses env if not provided)
        """
        # Use environment variables if not explicitly provided
        if redacted_api_key is self._USE_ENV:
            self._redacted_api_key = os.environ.get("REDACTED_API_KEY")
        else:
            self._redacted_api_key = redacted_api_key
            
        if ops_api_key is self._USE_ENV:
            self._ops_api_key = os.environ.get("OPS_API_KEY")
        else:
            self._ops_api_key = ops_api_key
            
        self._manager = None
        self._raw_results = {}  # Cache raw results for download
    
    def _get_manager(self):
        """Lazily initialize and return the FetchManager."""
        if self._manager is None:
            try:
                from flacfetch.core.manager import FetchManager
                from flacfetch.providers.youtube import YoutubeProvider
            except ImportError as e:
                logger.error(f"flacfetch not installed: {e}")
                raise AudioSearchError(
                    "flacfetch library is not installed. "
                    "Install with: pip install flacfetch"
                ) from e
            
            self._manager = FetchManager()
            
            # Add providers based on available API keys
            if self._redacted_api_key:
                try:
                    from flacfetch.providers.redacted import RedactedProvider
                    self._manager.add_provider(RedactedProvider(api_key=self._redacted_api_key))
                    logger.debug("Added Redacted provider")
                except ImportError:
                    logger.warning("Redacted provider not available")
            
            if self._ops_api_key:
                try:
                    from flacfetch.providers.ops import OPSProvider
                    self._manager.add_provider(OPSProvider(api_key=self._ops_api_key))
                    logger.debug("Added OPS provider")
                except ImportError:
                    logger.warning("OPS provider not available")
            
            # Always add YouTube as a fallback provider
            self._manager.add_provider(YoutubeProvider())
            logger.debug("Added YouTube provider")
        
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
            AudioSearchError: For other errors
        """
        try:
            from flacfetch.core.models import TrackQuery
        except ImportError as e:
            raise AudioSearchError("flacfetch not installed") from e
        
        manager = self._get_manager()
        query = TrackQuery(artist=artist, title=title)
        
        logger.info(f"Searching for audio: {artist} - {title}")
        
        try:
            results = manager.search(query)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise AudioSearchError(f"Search failed: {e}") from e
        
        if not results:
            raise NoResultsError(f"No results found for: {artist} - {title}")
        
        # Convert to our AudioSearchResult format and cache raw results
        search_results = []
        self._raw_results.clear()
        
        for i, result in enumerate(results):
            search_result = AudioSearchResult(
                title=getattr(result, "title", title),
                artist=getattr(result, "artist", artist),
                provider=getattr(result, "provider", "Unknown"),
                url=getattr(result, "url", ""),
                duration=getattr(result, "duration", None),
                quality=getattr(result, "quality", None),
                source_id=getattr(result, "id", str(i)),
                index=i,
            )
            search_results.append(search_result)
            
            # Cache raw result for later download
            self._raw_results[i] = result
        
        logger.info(f"Found {len(search_results)} results for: {artist} - {title}")
        return search_results
    
    def select_best(self, results: List[AudioSearchResult]) -> int:
        """
        Select the best result from a list of search results.
        
        Uses flacfetch's built-in quality ranking to select the best source.
        
        Args:
            results: List of search results
            
        Returns:
            Index of the best result
        """
        if not results:
            return 0
        
        manager = self._get_manager()
        
        # Get raw results for the indices we have
        raw_results = [self._raw_results.get(r.index) for r in results if r.index in self._raw_results]
        
        if raw_results:
            try:
                best = manager.select_best(raw_results)
                # Find index of best result
                for i, raw in enumerate(raw_results):
                    if raw == best:
                        return results[i].index
            except Exception as e:
                logger.warning(f"select_best failed, using first result: {e}")
        
        # Fallback: return first result
        return results[0].index if results else 0
    
    def download(
        self,
        result_index: int,
        output_dir: str,
        output_filename: Optional[str] = None,
    ) -> AudioDownloadResult:
        """
        Download audio from a search result.
        
        Args:
            result_index: Index of the result to download (from search results)
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)
            
        Returns:
            AudioDownloadResult with the downloaded file path
            
        Raises:
            DownloadError: If download fails
        """
        if result_index not in self._raw_results:
            raise DownloadError(f"No cached result for index {result_index}. Run search() first.")
        
        raw_result = self._raw_results[result_index]
        manager = self._get_manager()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Get metadata from raw result
        artist = getattr(raw_result, "artist", "Unknown")
        title = getattr(raw_result, "title", "Unknown")
        provider = getattr(raw_result, "provider", "Unknown")
        
        # Generate filename if not provided
        if output_filename is None:
            output_filename = f"{artist} - {title}"
        
        logger.info(f"Downloading: {artist} - {title} from {provider}")
        
        try:
            filepath = manager.download(
                raw_result,
                output_path=output_dir,
                output_filename=output_filename,
            )
            
            if filepath is None:
                raise DownloadError(f"Download returned no file path for: {artist} - {title}")
            
            logger.info(f"Downloaded to: {filepath}")
            
            return AudioDownloadResult(
                filepath=filepath,
                artist=artist,
                title=title,
                provider=provider,
                duration=getattr(raw_result, "duration", None),
                quality=getattr(raw_result, "quality", None),
            )
            
        except Exception as e:
            raise DownloadError(f"Failed to download {artist} - {title}: {e}") from e
    
    def search_and_download_auto(
        self,
        artist: str,
        title: str,
        output_dir: str,
        output_filename: Optional[str] = None,
    ) -> AudioDownloadResult:
        """
        Search for audio and automatically download the best result.
        
        This is a convenience method that combines search(), select_best(),
        and download() for automated/non-interactive usage.
        
        Args:
            artist: The artist name to search for
            title: The track title to search for
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)
            
        Returns:
            AudioDownloadResult with the downloaded file path
            
        Raises:
            NoResultsError: If no results are found
            DownloadError: If download fails
        """
        # Search
        results = self.search(artist, title)
        
        # Select best
        best_index = self.select_best(results)
        logger.info(f"Auto-selected result {best_index}: {results[best_index].artist} - {results[best_index].title} ({results[best_index].provider})")
        
        # Download
        return self.download(best_index, output_dir, output_filename)


# Singleton instance
_audio_search_service: Optional[AudioSearchService] = None


def get_audio_search_service() -> AudioSearchService:
    """Get the singleton AudioSearchService instance."""
    global _audio_search_service
    if _audio_search_service is None:
        _audio_search_service = AudioSearchService()
    return _audio_search_service


