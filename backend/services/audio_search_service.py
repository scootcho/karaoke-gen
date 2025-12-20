"""
Audio search service for finding and downloading audio files.

This service integrates with karaoke_gen.audio_fetcher (which wraps flacfetch)
to search for audio from various sources (YouTube, music trackers, etc.)
and download the selected audio file.

This is a thin wrapper that adds backend-specific functionality:
- Caching raw results for API-based selection flow
- Firestore-compatible serialization
- Singleton pattern for service lifecycle
"""
import logging
import os
from typing import List, Optional

# Import shared classes from karaoke_gen.audio_fetcher - single source of truth
# Note: Import directly from audio_fetcher module, not karaoke_gen.__init__
# to avoid pulling in heavier dependencies like lyrics_transcriber
from karaoke_gen.audio_fetcher import (
    FlacFetcher,
    AudioSearchResult,
    AudioFetchResult,
    AudioFetcherError,
    NoResultsError,
    DownloadError,
)

logger = logging.getLogger(__name__)


# Re-export exception under backend's naming convention for compatibility
AudioSearchError = AudioFetcherError


# Also alias AudioFetchResult as AudioDownloadResult for backwards compatibility
AudioDownloadResult = AudioFetchResult


class AudioSearchService:
    """
    Service for searching and downloading audio files.
    
    This is a thin wrapper around karaoke_gen.audio_fetcher.FlacFetcher that adds
    backend-specific functionality:
    - Caches raw results for API-based selection (client picks by index)
    - Provides Firestore-compatible serialization
    - Manages service lifecycle as singleton
    
    The actual flacfetch integration is in karaoke_gen.audio_fetcher.FlacFetcher,
    which is shared between local CLI and cloud backend.
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
            redacted_api_key = os.environ.get("REDACTED_API_KEY")
            
        if ops_api_key is self._USE_ENV:
            ops_api_key = os.environ.get("OPS_API_KEY")
        
        # Delegate to shared FlacFetcher implementation
        self._fetcher = FlacFetcher(
            redacted_api_key=redacted_api_key,
            ops_api_key=ops_api_key,
        )
        
        # Cache search results for API-based selection flow
        # Key: index, Value: AudioSearchResult (with raw_result)
        self._cached_results: List[AudioSearchResult] = []
    
    def search(self, artist: str, title: str) -> List[AudioSearchResult]:
        """
        Search for audio matching the given artist and title.
        
        Results are cached internally for later download via download().
        
        Args:
            artist: The artist name to search for
            title: The track title to search for
            
        Returns:
            List of AudioSearchResult objects
            
        Raises:
            NoResultsError: If no results are found
            AudioSearchError: For other errors (e.g., flacfetch not installed)
        """
        try:
            # Delegate to shared FlacFetcher
            results = self._fetcher.search(artist, title)
            
            # Cache results for later download
            self._cached_results = results
            
            logger.info(f"Found {len(results)} results for: {artist} - {title}")
            return results
            
        except (NoResultsError, AudioFetcherError):
            # Re-raise these as-is
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise AudioSearchError(f"Search failed: {e}") from e
    
    def select_best(self, results: List[AudioSearchResult]) -> int:
        """
        Select the best result from a list of search results.
        
        Uses flacfetch's built-in quality ranking to select the best source.
        
        Args:
            results: List of search results
            
        Returns:
            Index of the best result
        """
        return self._fetcher.select_best(results)
    
    def download(
        self,
        result_index: int,
        output_dir: str,
        output_filename: Optional[str] = None,
    ) -> AudioDownloadResult:
        """
        Download audio from a cached search result.
        
        This method uses the cached results from the last search() call.
        The API flow is:
        1. Client calls search() -> gets list of results
        2. Client picks an index
        3. Client calls download(index) -> gets downloaded file
        
        Args:
            result_index: Index of the result to download (from search results)
            output_dir: Directory to save the downloaded file
            output_filename: Optional filename (without extension)
            
        Returns:
            AudioDownloadResult with the downloaded file path
            
        Raises:
            DownloadError: If download fails or no cached result for index
        """
        if result_index < 0 or result_index >= len(self._cached_results):
            raise DownloadError(
                f"No cached result for index {result_index}. "
                f"Available indices: 0-{len(self._cached_results) - 1}. "
                "Run search() first."
            )
        
        result = self._cached_results[result_index]
        
        logger.info(f"Downloading: {result.artist} - {result.title} from {result.provider}")
        
        # Delegate to shared FlacFetcher
        fetch_result = self._fetcher.download(result, output_dir, output_filename)
        
        logger.info(f"Downloaded to: {fetch_result.filepath}")
        
        return fetch_result
    
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
        best_result = results[best_index]
        logger.info(
            f"Auto-selected result {best_index}: "
            f"{best_result.artist} - {best_result.title} ({best_result.provider})"
        )
        
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
