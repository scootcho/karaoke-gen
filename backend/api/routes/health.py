"""
Health check routes.
"""
import os
import logging
from fastapi import APIRouter
from typing import Dict, Any

from backend.version import VERSION

router = APIRouter()
logger = logging.getLogger(__name__)


def check_transmission_status() -> Dict[str, Any]:
    """Check if Transmission daemon is available and responsive."""
    try:
        import transmission_rpc
        host = os.environ.get("TRANSMISSION_HOST", "localhost")
        port = int(os.environ.get("TRANSMISSION_PORT", "9091"))
        
        client = transmission_rpc.Client(host=host, port=port, timeout=5)
        stats = client.session_stats()
        
        # Get detailed torrent info
        torrents = client.get_torrents()
        torrent_details = []
        for t in torrents:
            torrent_info = {
                "name": t.name,
                "progress": round(t.progress, 1),
                "status": str(t.status),
                "peers": t.peers_connected if hasattr(t, 'peers_connected') else 0,
                "download_speed": round(t.rate_download / 1024, 1) if hasattr(t, 'rate_download') else 0,  # KB/s
            }
            # Check if stalled (downloading but no progress and no peers)
            if t.status.downloading and t.progress < 100 and torrent_info['peers'] == 0:
                torrent_info['stalled'] = True
            torrent_details.append(torrent_info)
        
        return {
            "available": True,
            "host": host,
            "port": port,
            "download_dir": stats.download_dir if hasattr(stats, 'download_dir') else None,
            "active_torrent_count": stats.active_torrent_count if hasattr(stats, 'active_torrent_count') else 0,
            "torrents": torrent_details,
        }
    except ImportError as e:
        return {
            "available": False,
            "error": f"transmission_rpc not installed: {e}",
        }
    except Exception as e:
        return {
            "available": False,
            "host": os.environ.get("TRANSMISSION_HOST", "localhost"),
            "port": int(os.environ.get("TRANSMISSION_PORT", "9091")),
            "error": str(e),
        }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "karaoke-gen-backend"
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check including dependencies.
    
    Use this to debug issues with Transmission, etc.
    """
    transmission_status = check_transmission_status()
    
    # Log for debugging
    if not transmission_status.get("available"):
        logger.warning(f"Transmission not available: {transmission_status.get('error')}")
    else:
        logger.info(f"Transmission available at {transmission_status.get('host')}:{transmission_status.get('port')}")
    
    return {
        "status": "healthy",
        "service": "karaoke-gen-backend",
        "version": VERSION,
        "dependencies": {
            "transmission": transmission_status,
        }
    }


@router.get("/readiness")
async def readiness_check() -> Dict[str, str]:
    """Readiness check endpoint for Cloud Run."""
    return {
        "status": "ready",
        "service": "karaoke-gen-backend"
    }

