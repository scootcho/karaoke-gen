"""
Lightweight local server for instrumental review.

This module provides a local HTTP server that serves the instrumental review
UI for local CLI usage. It mimics the remote backend API endpoints to allow
the same React frontend to work for both local and remote workflows.

Similar pattern to LyricsTranscriber's ReviewServer.
"""

import http.server
import json
import logging
import os
import socketserver
import threading
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from karaoke_gen.instrumental_review import (
    AnalysisResult,
    AudioAnalyzer,
    AudioEditor,
    MuteRegion,
    WaveformGenerator,
)

logger = logging.getLogger(__name__)


class InstrumentalReviewHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for instrumental review API and static files."""
    
    # Class-level attributes set by the server
    output_dir: str = ""
    base_name: str = ""
    analysis: Optional[AnalysisResult] = None
    waveform_path: str = ""
    backing_vocals_path: str = ""
    clean_instrumental_path: str = ""
    with_backing_path: str = ""
    custom_instrumental_path: Optional[str] = None
    selection: Optional[str] = None
    selection_event: Optional[threading.Event] = None
    
    def log_message(self, format: str, *args) -> None:
        """Override to use Python logging instead of stderr."""
        logger.debug(f"HTTP: {args[0]}")
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API endpoints
        if path == "/api/analysis":
            self._serve_analysis()
        elif path.startswith("/api/audio/"):
            stem_type = path.split("/")[-1]
            self._serve_audio(stem_type)
        elif path == "/api/waveform":
            self._serve_waveform()
        elif path == "/api/waveform-data":
            query = parse_qs(parsed.query)
            num_points = int(query.get("num_points", [500])[0])
            self._serve_waveform_data(num_points)
        else:
            # Serve static files or HTML page
            self._serve_static_or_index()
    
    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/create-custom":
            self._handle_create_custom()
        elif path == "/api/select":
            self._handle_select()
        else:
            self.send_error(404, "Not Found")
    
    def _serve_analysis(self) -> None:
        """Serve analysis data as JSON."""
        if not InstrumentalReviewHandler.analysis:
            self.send_error(500, "Analysis not available")
            return
        
        analysis = InstrumentalReviewHandler.analysis
        
        response = {
            "job_id": "local",
            "artist": "",  # Not needed for local
            "title": "",
            "status": "awaiting_instrumental_selection",
            "analysis": {
                "has_audible_content": analysis.has_audible_content,
                "total_duration_seconds": analysis.total_duration_seconds,
                "audible_segments": [
                    {
                        "start_seconds": seg.start_seconds,
                        "end_seconds": seg.end_seconds,
                        "duration_seconds": seg.duration_seconds,
                        "avg_amplitude_db": seg.avg_amplitude_db,
                        "peak_amplitude_db": seg.peak_amplitude_db,
                    }
                    for seg in analysis.audible_segments
                ],
                "recommended_selection": analysis.recommended_selection.value,
                "total_audible_duration_seconds": analysis.total_audible_duration_seconds,
                "audible_percentage": analysis.audible_percentage,
                "silence_threshold_db": analysis.silence_threshold_db,
            },
            "audio_urls": {
                "clean_instrumental": "/api/audio/clean_instrumental" if InstrumentalReviewHandler.clean_instrumental_path else None,
                "backing_vocals": "/api/audio/backing_vocals" if InstrumentalReviewHandler.backing_vocals_path else None,
                "with_backing": "/api/audio/with_backing" if InstrumentalReviewHandler.with_backing_path else None,
                "custom_instrumental": "/api/audio/custom_instrumental" if InstrumentalReviewHandler.custom_instrumental_path else None,
            },
            "waveform_url": "/api/waveform" if InstrumentalReviewHandler.waveform_path else None,
            "has_custom_instrumental": InstrumentalReviewHandler.custom_instrumental_path is not None,
        }
        
        self._send_json_response(response)
    
    def _serve_audio(self, stem_type: str) -> None:
        """Serve audio file."""
        path_map = {
            "clean_instrumental": InstrumentalReviewHandler.clean_instrumental_path,
            "backing_vocals": InstrumentalReviewHandler.backing_vocals_path,
            "with_backing": InstrumentalReviewHandler.with_backing_path,
            "custom_instrumental": InstrumentalReviewHandler.custom_instrumental_path,
        }
        
        audio_path = path_map.get(stem_type)
        if not audio_path or not os.path.exists(audio_path):
            self.send_error(404, f"Audio file not found: {stem_type}")
            return
        
        self._serve_file(audio_path, self._get_mime_type(audio_path))
    
    def _serve_waveform(self) -> None:
        """Serve waveform image."""
        waveform_path = InstrumentalReviewHandler.waveform_path
        if not waveform_path or not os.path.exists(waveform_path):
            self.send_error(404, "Waveform image not found")
            return
        
        self._serve_file(waveform_path, "image/png")
    
    def _serve_waveform_data(self, num_points: int) -> None:
        """Serve waveform amplitude data for client-side rendering."""
        backing_path = InstrumentalReviewHandler.backing_vocals_path
        if not backing_path or not os.path.exists(backing_path):
            self.send_error(404, "Backing vocals file not found")
            return
        
        try:
            generator = WaveformGenerator()
            amplitudes, duration = generator.generate_data_only(backing_path, num_points)
            
            response = {
                "amplitudes": amplitudes,
                "duration": duration,
            }
            self._send_json_response(response)
        except Exception as e:
            logger.error(f"Error generating waveform data: {e}")
            self.send_error(500, f"Error generating waveform data: {e}")
    
    def _handle_create_custom(self) -> None:
        """Handle custom instrumental creation request."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            mute_regions = [
                MuteRegion(
                    start_seconds=r["start_seconds"],
                    end_seconds=r["end_seconds"],
                )
                for r in data.get("mute_regions", [])
            ]
            
            if not mute_regions:
                self.send_error(400, "No mute regions provided")
                return
            
            # Create custom instrumental
            editor = AudioEditor()
            output_path = os.path.join(
                InstrumentalReviewHandler.output_dir,
                f"{InstrumentalReviewHandler.base_name} (Instrumental Custom).flac"
            )
            
            result = editor.create_custom_instrumental(
                clean_instrumental_path=InstrumentalReviewHandler.clean_instrumental_path,
                backing_vocals_path=InstrumentalReviewHandler.backing_vocals_path,
                mute_regions=mute_regions,
                output_path=output_path,
            )
            
            # Update the custom instrumental path
            InstrumentalReviewHandler.custom_instrumental_path = result.output_path
            
            response = {
                "status": "success",
                "custom_instrumental_url": "/api/audio/custom_instrumental",
                "statistics": {
                    "mute_regions_applied": len(result.mute_regions_applied),
                    "total_muted_duration_seconds": result.total_muted_duration_seconds,
                    "output_duration_seconds": result.output_duration_seconds,
                },
            }
            self._send_json_response(response)
            
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error creating custom instrumental: {e}")
            self.send_error(500, f"Error creating custom instrumental: {e}")
    
    def _handle_select(self) -> None:
        """Handle selection submission."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            selection = data.get("selection")
            if selection not in ("clean", "with_backing", "custom"):
                self.send_error(400, f"Invalid selection: {selection}")
                return
            
            # Store the selection
            InstrumentalReviewHandler.selection = selection
            
            # Signal that selection is complete
            if InstrumentalReviewHandler.selection_event:
                InstrumentalReviewHandler.selection_event.set()
            
            response = {"status": "success", "selection": selection}
            self._send_json_response(response)
            
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling selection: {e}")
            self.send_error(500, f"Error handling selection: {e}")
    
    def _serve_static_or_index(self) -> None:
        """Serve static files or the main index.html."""
        # For now, serve a simple HTML page that redirects to the review UI
        # In a full implementation, this would serve the React frontend
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Instrumental Review</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
        h1 { color: #333; }
        .info { background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; font-size: 16px; }
        button:hover { background: #0056b3; }
        .secondary { background: #6c757d; }
        .secondary:hover { background: #545b62; }
        pre { background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; }
        #status { margin-top: 20px; padding: 15px; border-radius: 8px; display: none; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>🎤 Instrumental Review</h1>
    <div class="info">
        <p><strong>Analysis Status:</strong> <span id="analysis-status">Loading...</span></p>
        <div id="analysis-details"></div>
    </div>
    <h2>Select Instrumental</h2>
    <div>
        <button onclick="selectInstrumental('clean')">Clean Instrumental</button>
        <button class="secondary" onclick="selectInstrumental('with_backing')">With Backing Vocals</button>
    </div>
    <div id="status"></div>
    
    <script>
        async function loadAnalysis() {
            try {
                const response = await fetch('/api/analysis');
                const data = await response.json();
                const analysis = data.analysis;
                
                document.getElementById('analysis-status').textContent = 
                    analysis.has_audible_content ? 'Backing vocals detected' : 'No backing vocals detected';
                
                let details = '<ul>';
                details += `<li>Duration: ${analysis.total_duration_seconds.toFixed(1)}s</li>`;
                details += `<li>Audible segments: ${analysis.audible_segments.length}</li>`;
                details += `<li>Recommendation: ${analysis.recommended_selection}</li>`;
                details += '</ul>';
                document.getElementById('analysis-details').innerHTML = details;
            } catch (error) {
                document.getElementById('analysis-status').textContent = 'Error loading analysis';
            }
        }
        
        async function selectInstrumental(selection) {
            try {
                const response = await fetch('/api/select', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({selection: selection})
                });
                const data = await response.json();
                
                const statusDiv = document.getElementById('status');
                if (data.status === 'success') {
                    statusDiv.className = 'success';
                    statusDiv.textContent = `Selection "${selection}" submitted! You can close this window.`;
                } else {
                    statusDiv.className = 'error';
                    statusDiv.textContent = 'Error submitting selection';
                }
                statusDiv.style.display = 'block';
            } catch (error) {
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'error';
                statusDiv.textContent = 'Error: ' + error.message;
                statusDiv.style.display = 'block';
            }
        }
        
        loadAnalysis();
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _send_json_response(self, data: Dict[str, Any]) -> None:
        """Send a JSON response."""
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def _serve_file(self, file_path: str, content_type: str) -> None:
        """Serve a file with the given content type."""
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error serving file: {e}")
    
    def _get_mime_type(self, path: str) -> str:
        """Get MIME type for a file."""
        ext = os.path.splitext(path)[1].lower()
        mime_types = {
            ".flac": "audio/flac",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        return mime_types.get(ext, "application/octet-stream")


class InstrumentalReviewServer:
    """
    Local HTTP server for instrumental review UI.
    
    This server provides a web interface for reviewing and selecting
    instrumental tracks in the local CLI workflow. It serves the same
    API endpoints as the cloud backend to enable UI reuse.
    """
    
    def __init__(
        self,
        output_dir: str,
        base_name: str,
        analysis: AnalysisResult,
        waveform_path: str,
        backing_vocals_path: str,
        clean_instrumental_path: str,
        with_backing_path: Optional[str] = None,
    ):
        """
        Initialize the review server.
        
        Args:
            output_dir: Directory containing the audio files
            base_name: Base name for output files (e.g., "Artist - Title")
            analysis: Analysis result from AudioAnalyzer
            waveform_path: Path to the waveform image
            backing_vocals_path: Path to the backing vocals audio file
            clean_instrumental_path: Path to the clean instrumental audio file
            with_backing_path: Path to the instrumental with backing vocals
        """
        self.output_dir = output_dir
        self.base_name = base_name
        self.analysis = analysis
        self.waveform_path = waveform_path
        self.backing_vocals_path = backing_vocals_path
        self.clean_instrumental_path = clean_instrumental_path
        self.with_backing_path = with_backing_path
        
        self._server: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._selection_event = threading.Event()
    
    def start_and_open_browser(self, port: int = 8765) -> str:
        """
        Start server, open browser, and block until selection is submitted.
        
        Args:
            port: Port to run the server on
            
        Returns:
            The user's selection ("clean", "with_backing", or "custom")
        """
        # Set up the handler's class attributes
        InstrumentalReviewHandler.output_dir = self.output_dir
        InstrumentalReviewHandler.base_name = self.base_name
        InstrumentalReviewHandler.analysis = self.analysis
        InstrumentalReviewHandler.waveform_path = self.waveform_path
        InstrumentalReviewHandler.backing_vocals_path = self.backing_vocals_path
        InstrumentalReviewHandler.clean_instrumental_path = self.clean_instrumental_path
        InstrumentalReviewHandler.with_backing_path = self.with_backing_path
        InstrumentalReviewHandler.custom_instrumental_path = None
        InstrumentalReviewHandler.selection = None
        InstrumentalReviewHandler.selection_event = self._selection_event
        
        # Start the server
        self._server = socketserver.TCPServer(("", port), InstrumentalReviewHandler)
        self._server.allow_reuse_address = True
        
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()
        
        url = f"http://localhost:{port}/"
        logger.info(f"Instrumental review server started at {url}")
        
        # Open browser
        webbrowser.open(url)
        
        # Wait for selection
        logger.info("Waiting for instrumental selection...")
        self._selection_event.wait()
        
        # Stop the server
        self.stop()
        
        return self.get_selection()
    
    def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
    
    def get_selection(self) -> str:
        """Get the user's selection."""
        selection = InstrumentalReviewHandler.selection
        if selection is None:
            raise ValueError("No selection has been made")
        return selection
    
    def get_custom_instrumental_path(self) -> Optional[str]:
        """Get the path to the custom instrumental if one was created."""
        return InstrumentalReviewHandler.custom_instrumental_path
