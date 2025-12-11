"""
Local FastAPI server for instrumental review.

This module provides a local HTTP server that serves the instrumental review
UI for local CLI usage. It provides the same API endpoints as the cloud backend
to enable UI reuse.

Similar pattern to LyricsTranscriber's ReviewServer.
"""

import logging
import os
import threading
import webbrowser
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

from karaoke_gen.instrumental_review import (
    AnalysisResult,
    AudioAnalyzer,
    AudioEditor,
    MuteRegion,
    WaveformGenerator,
)

logger = logging.getLogger(__name__)


# Request/Response Models
class MuteRegionRequest(BaseModel):
    start_seconds: float
    end_seconds: float


class CreateCustomRequest(BaseModel):
    mute_regions: List[MuteRegionRequest]


class SelectionRequest(BaseModel):
    selection: str


class InstrumentalReviewServer:
    """
    Local FastAPI server for instrumental review UI.
    
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
        self.custom_instrumental_path: Optional[str] = None
        self.selection: Optional[str] = None
        
        self._app: Optional[FastAPI] = None
        self._server_thread: Optional[threading.Thread] = None
        self._selection_event = threading.Event()
        self._shutdown_event = threading.Event()
    
    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(title="Instrumental Review", docs_url=None, redoc_url=None)
        
        # Configure CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes(app)
        
        return app
    
    def _register_routes(self, app: FastAPI) -> None:
        """Register API routes."""
        
        @app.get("/")
        async def serve_frontend():
            """Serve the frontend HTML."""
            return HTMLResponse(content=self._get_frontend_html())
        
        @app.get("/api/jobs/local/instrumental-analysis")
        async def get_analysis():
            """Get analysis data for the instrumental review."""
            return {
                "job_id": "local",
                "artist": self.base_name.split(" - ")[0] if " - " in self.base_name else "",
                "title": self.base_name.split(" - ")[1] if " - " in self.base_name else self.base_name,
                "status": "awaiting_instrumental_selection",
                "analysis": {
                    "has_audible_content": self.analysis.has_audible_content,
                    "total_duration_seconds": self.analysis.total_duration_seconds,
                    "audible_segments": [
                        {
                            "start_seconds": seg.start_seconds,
                            "end_seconds": seg.end_seconds,
                            "duration_seconds": seg.duration_seconds,
                            "avg_amplitude_db": seg.avg_amplitude_db,
                            "peak_amplitude_db": seg.peak_amplitude_db,
                        }
                        for seg in self.analysis.audible_segments
                    ],
                    "recommended_selection": self.analysis.recommended_selection.value,
                    "total_audible_duration_seconds": self.analysis.total_audible_duration_seconds,
                    "audible_percentage": self.analysis.audible_percentage,
                    "silence_threshold_db": self.analysis.silence_threshold_db,
                },
                "audio_urls": {
                    "clean_instrumental": "/api/audio/clean_instrumental" if self.clean_instrumental_path else None,
                    "backing_vocals": "/api/audio/backing_vocals" if self.backing_vocals_path else None,
                    "with_backing": "/api/audio/with_backing" if self.with_backing_path else None,
                    "custom_instrumental": "/api/audio/custom_instrumental" if self.custom_instrumental_path else None,
                },
                "waveform_url": "/api/waveform" if self.waveform_path else None,
                "has_custom_instrumental": self.custom_instrumental_path is not None,
            }
        
        @app.get("/api/jobs/local/waveform-data")
        async def get_waveform_data(num_points: int = 600):
            """Get waveform amplitude data for client-side rendering."""
            # Validate num_points parameter
            if num_points <= 0 or num_points > 10000:
                raise HTTPException(
                    status_code=400, 
                    detail="num_points must be between 1 and 10000"
                )
            
            if not self.backing_vocals_path or not os.path.exists(self.backing_vocals_path):
                raise HTTPException(status_code=404, detail="Backing vocals file not found")
            
            try:
                generator = WaveformGenerator()
                amplitudes, duration = generator.generate_data_only(self.backing_vocals_path, num_points)
                return {"amplitudes": amplitudes, "duration": duration}
            except Exception as e:
                logger.exception(f"Error generating waveform data: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e
        
        @app.get("/api/audio/{stem_type}")
        async def stream_audio(stem_type: str):
            """Stream audio file."""
            path_map = {
                "clean_instrumental": self.clean_instrumental_path,
                "backing_vocals": self.backing_vocals_path,
                "with_backing": self.with_backing_path,
                "custom_instrumental": self.custom_instrumental_path,
            }
            
            audio_path = path_map.get(stem_type)
            if not audio_path or not os.path.exists(audio_path):
                raise HTTPException(status_code=404, detail=f"Audio file not found: {stem_type}")
            
            # Determine content type
            ext = os.path.splitext(audio_path)[1].lower()
            content_types = {
                ".flac": "audio/flac",
                ".mp3": "audio/mpeg",
                ".wav": "audio/wav",
            }
            content_type = content_types.get(ext, "application/octet-stream")
            
            return FileResponse(audio_path, media_type=content_type)
        
        @app.get("/api/waveform")
        async def get_waveform_image():
            """Serve waveform image."""
            if not self.waveform_path or not os.path.exists(self.waveform_path):
                raise HTTPException(status_code=404, detail="Waveform image not found")
            return FileResponse(self.waveform_path, media_type="image/png")
        
        @app.post("/api/jobs/local/create-custom-instrumental")
        async def create_custom_instrumental(request: CreateCustomRequest):
            """Create a custom instrumental with muted regions."""
            if not request.mute_regions:
                raise HTTPException(status_code=400, detail="No mute regions provided")
            
            try:
                mute_regions = [
                    MuteRegion(
                        start_seconds=r.start_seconds,
                        end_seconds=r.end_seconds,
                    )
                    for r in request.mute_regions
                ]
                
                editor = AudioEditor()
                output_path = os.path.join(
                    self.output_dir,
                    f"{self.base_name} (Instrumental Custom).flac"
                )
                
                result = editor.create_custom_instrumental(
                    clean_instrumental_path=self.clean_instrumental_path,
                    backing_vocals_path=self.backing_vocals_path,
                    mute_regions=mute_regions,
                    output_path=output_path,
                )
                
                self.custom_instrumental_path = result.output_path
                
                return {
                    "status": "success",
                    "custom_instrumental_url": "/api/audio/custom_instrumental",
                    "statistics": {
                        "mute_regions_applied": len(result.mute_regions_applied),
                        "total_muted_duration_seconds": result.total_muted_duration_seconds,
                        "output_duration_seconds": result.output_duration_seconds,
                    },
                }
            except Exception as e:
                logger.exception(f"Error creating custom instrumental: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e
        
        @app.post("/api/jobs/local/select-instrumental")
        async def select_instrumental(request: SelectionRequest):
            """Submit instrumental selection."""
            if request.selection not in ("clean", "with_backing", "custom"):
                raise HTTPException(status_code=400, detail=f"Invalid selection: {request.selection}")
            
            self.selection = request.selection
            self._selection_event.set()
            
            return {"status": "success", "selection": request.selection}
    
    def _get_frontend_html(self) -> str:
        """Return the complete frontend HTML with all features."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instrumental Review</title>
    <style>
        :root {
            --bg: #0a0a0a;
            --card: #18181b;
            --card-border: #27272a;
            --text: #fafafa;
            --text-muted: #a1a1aa;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --secondary: #27272a;
            --secondary-hover: #3f3f46;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
            --badge-bg: #27272a;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        header {
            background: var(--card);
            border-bottom: 1px solid var(--card-border);
            padding: 1rem 2rem;
            margin-bottom: 2rem;
        }
        
        header h1 {
            font-size: 1.25rem;
            font-weight: 600;
        }
        
        .page-title {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .page-subtitle {
            color: var(--text-muted);
            margin-bottom: 2rem;
        }
        
        .card {
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
        }
        
        .card-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--card-border);
        }
        
        .card-title {
            font-size: 1.125rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .card-description {
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }
        
        .card-content {
            padding: 1.5rem;
        }
        
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
            background: var(--badge-bg);
            border: 1px solid var(--card-border);
        }
        
        .badge-success { background: rgba(34, 197, 94, 0.2); color: var(--success); border-color: var(--success); }
        .badge-warning { background: rgba(234, 179, 8, 0.2); color: var(--warning); border-color: var(--warning); }
        
        .flex { display: flex; }
        .flex-wrap { flex-wrap: wrap; }
        .gap-2 { gap: 0.5rem; }
        .gap-4 { gap: 1rem; }
        .items-center { align-items: center; }
        .justify-between { justify-content: space-between; }
        
        .grid { display: grid; }
        .grid-cols-2 { grid-template-columns: repeat(2, 1fr); }
        @media (max-width: 1024px) { .grid-cols-2 { grid-template-columns: 1fr; } }
        
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            border: none;
            transition: background 0.2s;
        }
        
        .btn-primary {
            background: var(--primary);
            color: white;
        }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .btn-secondary {
            background: var(--secondary);
            color: var(--text);
        }
        .btn-secondary:hover { background: var(--secondary-hover); }
        
        .btn-outline {
            background: transparent;
            border: 1px solid var(--card-border);
            color: var(--text);
        }
        .btn-outline:hover { background: var(--secondary); }
        .btn-outline.active { background: var(--primary); border-color: var(--primary); }
        
        .btn-sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }
        .btn-lg { padding: 0.75rem 1.5rem; font-size: 1rem; }
        
        .btn-danger { background: var(--danger); color: white; }
        .btn-success { background: var(--success); color: white; }
        
        /* Waveform */
        #waveform-container {
            position: relative;
            background: #1a1a2e;
            border-radius: 0.5rem;
            overflow: hidden;
        }
        
        #waveform-canvas {
            display: block;
            width: 100%;
            cursor: crosshair;
        }
        
        .time-axis {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 1rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            background: rgba(0,0,0,0.3);
        }
        
        /* Audio Player */
        .audio-player {
            background: var(--secondary);
            padding: 1rem;
            border-radius: 0.5rem;
        }
        
        .audio-player audio {
            width: 100%;
        }
        
        .audio-label {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }
        
        /* Region List */
        .region-list {
            max-height: 200px;
            overflow-y: auto;
        }
        
        .region-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem;
            background: var(--secondary);
            border-radius: 0.375rem;
            margin-bottom: 0.5rem;
        }
        
        .region-item:last-child { margin-bottom: 0; }
        
        /* Radio Group */
        .radio-group { display: flex; flex-direction: column; gap: 1rem; }
        
        .radio-item {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            padding: 1rem;
            background: var(--secondary);
            border-radius: 0.5rem;
            cursor: pointer;
            border: 2px solid transparent;
            transition: border-color 0.2s;
        }
        
        .radio-item:hover { border-color: var(--card-border); }
        .radio-item.selected { border-color: var(--primary); }
        
        .radio-item input { margin-top: 0.25rem; }
        .radio-item-content { flex: 1; }
        .radio-item-title { font-weight: 500; }
        .radio-item-desc { font-size: 0.875rem; color: var(--text-muted); }
        
        /* Alert */
        .alert {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
        }
        
        .alert-error {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid var(--danger);
            color: var(--danger);
        }
        
        .alert-success {
            background: rgba(34, 197, 94, 0.2);
            border: 1px solid var(--success);
            color: var(--success);
        }
        
        /* Loading */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4rem;
        }
        
        .spinner {
            width: 2rem;
            height: 2rem;
            border: 3px solid var(--card-border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* Segment markers */
        .segment-marker {
            position: absolute;
            background: rgba(234, 179, 8, 0.3);
            border-left: 1px solid var(--warning);
            border-right: 1px solid var(--warning);
            pointer-events: none;
        }
        
        .mute-region {
            position: absolute;
            background: rgba(239, 68, 68, 0.4);
            border: 1px dashed var(--danger);
            pointer-events: none;
        }
        
        .playhead {
            position: absolute;
            width: 2px;
            background: var(--primary);
            pointer-events: none;
        }
        
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <header>
        <h1>🎤 Karaoke Generator</h1>
    </header>
    
    <main class="container" id="main-content">
        <div class="loading" id="loading">
            <div class="spinner"></div>
        </div>
    </main>

    <script>
        // State
        let analysisData = null;
        let waveformData = null;
        let muteRegions = [];
        let currentTime = 0;
        let isSelectionMode = false;
        let selectionStart = null;
        let activeAudio = 'backing';
        let selectedOption = 'clean';
        let hasCustom = false;
        
        const API_BASE = '/api/jobs/local';
        
        // Initialize
        async function init() {
            try {
                // Fetch analysis
                const analysisRes = await fetch(`${API_BASE}/instrumental-analysis`);
                if (!analysisRes.ok) throw new Error('Failed to load analysis');
                analysisData = await analysisRes.json();
                
                // Fetch waveform data
                const waveformRes = await fetch(`${API_BASE}/waveform-data?num_points=800`);
                if (waveformRes.ok) {
                    waveformData = await waveformRes.json();
                }
                
                // Set initial selection based on recommendation
                selectedOption = analysisData.analysis.recommended_selection === 'clean' ? 'clean' : 'with_backing';
                
                render();
            } catch (error) {
                showError(error.message);
            }
        }
        
        function render() {
            const main = document.getElementById('main-content');
            main.innerHTML = `
                <h1 class="page-title">Select Instrumental Track</h1>
                <p class="page-subtitle">${analysisData.artist || ''} ${analysisData.artist && analysisData.title ? '-' : ''} ${analysisData.title || ''}</p>
                
                <div id="error-container"></div>
                
                <!-- Analysis Summary -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <span>🎵</span> Backing Vocals Analysis
                        </div>
                        <div class="card-description">Automated analysis of the backing vocals stem</div>
                    </div>
                    <div class="card-content">
                        <div class="flex flex-wrap gap-4 items-center">
                            <div class="flex items-center gap-2">
                                ${analysisData.analysis.has_audible_content 
                                    ? '<span style="color: var(--warning)">🔊</span> Backing vocals detected'
                                    : '<span style="color: var(--success)">🔇</span> No backing vocals detected'}
                            </div>
                            ${analysisData.analysis.has_audible_content ? `
                                <span class="badge">${analysisData.analysis.audible_segments.length} segments</span>
                                <span class="badge">${analysisData.analysis.audible_percentage.toFixed(1)}% of track</span>
                                <span class="badge">${analysisData.analysis.total_audible_duration_seconds.toFixed(1)}s total</span>
                            ` : ''}
                            <span class="badge ${analysisData.analysis.recommended_selection === 'clean' ? 'badge-success' : 'badge-warning'}">
                                Recommended: ${analysisData.analysis.recommended_selection === 'clean' ? 'Clean Instrumental' : 'Review Needed'}
                            </span>
                        </div>
                    </div>
                </div>
                
                <!-- Waveform -->
                ${waveformData ? `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Backing Vocals Waveform</div>
                        <div class="card-description">
                            Click to seek • ${isSelectionMode ? 'Click and drag to select mute region' : 'Click "Add Mute Region" to start selecting'}
                        </div>
                    </div>
                    <div class="card-content">
                        <div id="waveform-container">
                            <canvas id="waveform-canvas" width="800" height="150"></canvas>
                            <div id="segments-overlay"></div>
                            <div id="mute-overlay"></div>
                            <div id="playhead" class="playhead hidden"></div>
                        </div>
                        <div class="time-axis">
                            <span>0:00</span>
                            <span>${formatTime(waveformData.duration / 4)}</span>
                            <span>${formatTime(waveformData.duration / 2)}</span>
                            <span>${formatTime(waveformData.duration * 3 / 4)}</span>
                            <span>${formatTime(waveformData.duration)}</span>
                        </div>
                    </div>
                </div>
                ` : ''}
                
                <!-- Audio & Regions Grid -->
                <div class="grid grid-cols-2 gap-4">
                    <!-- Audio Player -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Audio Preview</div>
                            <div class="card-description">Listen to different instrumental options</div>
                        </div>
                        <div class="card-content">
                            <div class="flex flex-wrap gap-2" style="margin-bottom: 1rem;">
                                <button class="btn btn-sm ${activeAudio === 'backing' ? 'btn-primary' : 'btn-outline'}" onclick="setActiveAudio('backing')">Backing Vocals</button>
                                <button class="btn btn-sm ${activeAudio === 'clean' ? 'btn-primary' : 'btn-outline'}" onclick="setActiveAudio('clean')">Clean Instrumental</button>
                                ${analysisData.audio_urls.with_backing ? `
                                <button class="btn btn-sm ${activeAudio === 'with_backing' ? 'btn-primary' : 'btn-outline'}" onclick="setActiveAudio('with_backing')">With Backing</button>
                                ` : ''}
                                ${hasCustom ? `
                                <button class="btn btn-sm ${activeAudio === 'custom' ? 'btn-primary' : 'btn-outline'}" onclick="setActiveAudio('custom')">Custom</button>
                                ` : ''}
                            </div>
                            <div class="audio-player">
                                <div class="audio-label">${getAudioLabel()}</div>
                                <audio id="audio-player" controls src="${getAudioUrl()}" ontimeupdate="onTimeUpdate(this)"></audio>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Region Selector -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Mute Regions</div>
                            <div class="card-description">Select sections of backing vocals to mute</div>
                        </div>
                        <div class="card-content">
                            <div class="flex gap-2" style="margin-bottom: 1rem;">
                                <button class="btn btn-sm ${isSelectionMode ? 'btn-primary' : 'btn-outline'}" onclick="toggleSelectionMode()">
                                    ${isSelectionMode ? '✓ Selecting...' : '+ Add Mute Region'}
                                </button>
                                ${muteRegions.length > 0 ? `
                                <button class="btn btn-sm btn-outline" onclick="clearAllRegions()">Clear All</button>
                                ` : ''}
                            </div>
                            
                            ${muteRegions.length > 0 ? `
                            <div class="region-list">
                                ${muteRegions.map((r, i) => `
                                <div class="region-item">
                                    <span>${formatTime(r.start_seconds)} - ${formatTime(r.end_seconds)} (${(r.end_seconds - r.start_seconds).toFixed(1)}s)</span>
                                    <div class="flex gap-2">
                                        <button class="btn btn-sm btn-outline" onclick="seekTo(${r.start_seconds})">▶</button>
                                        <button class="btn btn-sm btn-danger" onclick="removeRegion(${i})">×</button>
                                    </div>
                                </div>
                                `).join('')}
                            </div>
                            ` : `
                            <p style="color: var(--text-muted); font-size: 0.875rem;">
                                No mute regions selected. Click "Add Mute Region" then click and drag on the waveform to select sections to mute.
                            </p>
                            `}
                            
                            ${analysisData.analysis.audible_segments.length > 0 ? `
                            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--card-border);">
                                <div style="font-size: 0.875rem; color: var(--text-muted); margin-bottom: 0.5rem;">Quick mute detected segments:</div>
                                <div class="flex flex-wrap gap-2">
                                    ${analysisData.analysis.audible_segments.slice(0, 5).map((seg, i) => `
                                    <button class="btn btn-sm btn-outline" onclick="addSegmentAsRegion(${i})">
                                        ${formatTime(seg.start_seconds)} - ${formatTime(seg.end_seconds)}
                                    </button>
                                    `).join('')}
                                    ${analysisData.analysis.audible_segments.length > 5 ? `<span class="badge">+${analysisData.analysis.audible_segments.length - 5} more</span>` : ''}
                                </div>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
                
                <!-- Create Custom Button -->
                ${muteRegions.length > 0 && !hasCustom ? `
                <div class="card">
                    <div class="card-content">
                        <div class="flex items-center justify-between">
                            <div>
                                <p style="font-weight: 500;">Ready to create custom instrumental</p>
                                <p style="font-size: 0.875rem; color: var(--text-muted);">${muteRegions.length} region${muteRegions.length > 1 ? 's' : ''} will be muted</p>
                            </div>
                            <button class="btn btn-primary" id="create-custom-btn" onclick="createCustomInstrumental()">
                                Create Custom Instrumental
                            </button>
                        </div>
                    </div>
                </div>
                ` : ''}
                
                <!-- Selection Options -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Final Selection</div>
                        <div class="card-description">Choose which instrumental to use for your karaoke video</div>
                    </div>
                    <div class="card-content">
                        <div class="radio-group">
                            <label class="radio-item ${selectedOption === 'clean' ? 'selected' : ''}" onclick="setSelection('clean')">
                                <input type="radio" name="selection" value="clean" ${selectedOption === 'clean' ? 'checked' : ''}>
                                <div class="radio-item-content">
                                    <div class="radio-item-title">Clean Instrumental</div>
                                    <div class="radio-item-desc">Use the instrumental with no backing vocals at all</div>
                                </div>
                                ${analysisData.analysis.recommended_selection === 'clean' ? '<span class="badge badge-success">✓ Recommended</span>' : ''}
                            </label>
                            
                            <label class="radio-item ${selectedOption === 'with_backing' ? 'selected' : ''}" onclick="setSelection('with_backing')">
                                <input type="radio" name="selection" value="with_backing" ${selectedOption === 'with_backing' ? 'checked' : ''}>
                                <div class="radio-item-content">
                                    <div class="radio-item-title">Instrumental with Backing Vocals</div>
                                    <div class="radio-item-desc">Use the instrumental with all backing vocals included</div>
                                </div>
                            </label>
                            
                            ${hasCustom ? `
                            <label class="radio-item ${selectedOption === 'custom' ? 'selected' : ''}" onclick="setSelection('custom')">
                                <input type="radio" name="selection" value="custom" ${selectedOption === 'custom' ? 'checked' : ''}>
                                <div class="radio-item-content">
                                    <div class="radio-item-title">Custom Instrumental</div>
                                    <div class="radio-item-desc">Use your custom instrumental with ${muteRegions.length} muted region${muteRegions.length > 1 ? 's' : ''}</div>
                                </div>
                                <span class="badge">Custom</span>
                            </label>
                            ` : ''}
                        </div>
                    </div>
                </div>
                
                <!-- Submit Button -->
                <button class="btn btn-primary btn-lg" id="submit-btn" onclick="submitSelection()" style="width: 100%; max-width: 400px; margin-top: 1rem;">
                    ✓ Confirm Selection & Continue
                </button>
            `;
            
            // Initialize waveform after render
            if (waveformData) {
                setTimeout(drawWaveform, 0);
                setupWaveformInteraction();
            }
        }
        
        function drawWaveform() {
            const canvas = document.getElementById('waveform-canvas');
            if (!canvas || !waveformData) return;
            
            const ctx = canvas.getContext('2d');
            const { amplitudes, duration } = waveformData;
            const width = canvas.width;
            const height = canvas.height;
            const centerY = height / 2;
            
            // Clear canvas
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(0, 0, width, height);
            
            // Draw threshold line
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(0, centerY);
            ctx.lineTo(width, centerY);
            ctx.stroke();
            ctx.setLineDash([]);
            
            // Draw waveform
            const barWidth = width / amplitudes.length;
            
            amplitudes.forEach((amp, i) => {
                const x = i * barWidth;
                const barHeight = Math.max(2, amp * height);
                const y = centerY - barHeight / 2;
                
                // Check if this point is in a muted region
                const time = (i / amplitudes.length) * duration;
                const inMuteRegion = muteRegions.some(r => time >= r.start_seconds && time <= r.end_seconds);
                
                // Check if in audible segment
                const inAudibleSegment = analysisData.analysis.audible_segments.some(
                    s => time >= s.start_seconds && time <= s.end_seconds
                );
                
                if (inMuteRegion) {
                    ctx.fillStyle = '#ef4444';
                } else if (inAudibleSegment) {
                    ctx.fillStyle = '#ec4899';
                } else {
                    ctx.fillStyle = '#60a5fa';
                }
                
                ctx.fillRect(x, y, Math.max(1, barWidth - 1), barHeight);
            });
            
            // Draw playhead
            const playhead = document.getElementById('playhead');
            if (playhead && currentTime > 0) {
                const x = (currentTime / duration) * width;
                playhead.style.left = `${x}px`;
                playhead.style.height = `${height}px`;
                playhead.classList.remove('hidden');
            }
        }
        
        function setupWaveformInteraction() {
            const canvas = document.getElementById('waveform-canvas');
            if (!canvas) return;
            
            let isDragging = false;
            let dragStart = 0;
            
            canvas.onmousedown = (e) => {
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const time = (x / rect.width) * waveformData.duration;
                
                if (isSelectionMode) {
                    isDragging = true;
                    dragStart = time;
                    selectionStart = time;
                } else {
                    seekTo(time);
                }
            };
            
            canvas.onmousemove = (e) => {
                if (!isDragging || !isSelectionMode) return;
                // Visual feedback could be added here
            };
            
            canvas.onmouseup = (e) => {
                if (!isDragging || !isSelectionMode) return;
                
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const time = (x / rect.width) * waveformData.duration;
                
                const start = Math.min(dragStart, time);
                const end = Math.max(dragStart, time);
                
                if (end - start > 0.1) {
                    addRegion(start, end);
                }
                
                isDragging = false;
                isSelectionMode = false;
                render();
            };
            
            canvas.onmouseleave = () => {
                if (isDragging) {
                    isDragging = false;
                }
            };
        }
        
        function formatTime(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        }
        
        function getAudioUrl() {
            const urls = {
                backing: '/api/audio/backing_vocals',
                clean: '/api/audio/clean_instrumental',
                with_backing: '/api/audio/with_backing',
                custom: '/api/audio/custom_instrumental'
            };
            return urls[activeAudio] || urls.backing;
        }
        
        function getAudioLabel() {
            const labels = {
                backing: 'Backing Vocals Only',
                clean: 'Clean Instrumental',
                with_backing: 'Instrumental + Backing Vocals',
                custom: 'Custom Instrumental'
            };
            return labels[activeAudio] || 'Audio';
        }
        
        function setActiveAudio(type) {
            activeAudio = type;
            render();
        }
        
        function onTimeUpdate(audio) {
            currentTime = audio.currentTime;
            if (waveformData) {
                const playhead = document.getElementById('playhead');
                const canvas = document.getElementById('waveform-canvas');
                if (playhead && canvas) {
                    const x = (currentTime / waveformData.duration) * canvas.width;
                    playhead.style.left = `${x}px`;
                    playhead.style.height = `${canvas.height}px`;
                    playhead.classList.remove('hidden');
                }
            }
        }
        
        function seekTo(time) {
            const audio = document.getElementById('audio-player');
            if (audio) {
                audio.currentTime = time;
                audio.play();
            }
        }
        
        function toggleSelectionMode() {
            isSelectionMode = !isSelectionMode;
            render();
        }
        
        function addRegion(start, end) {
            muteRegions.push({ start_seconds: start, end_seconds: end });
            muteRegions.sort((a, b) => a.start_seconds - b.start_seconds);
            // Merge overlapping
            mergeOverlappingRegions();
        }
        
        function addSegmentAsRegion(index) {
            const seg = analysisData.analysis.audible_segments[index];
            if (seg) {
                addRegion(seg.start_seconds, seg.end_seconds);
                render();
            }
        }
        
        function removeRegion(index) {
            muteRegions.splice(index, 1);
            render();
        }
        
        function clearAllRegions() {
            muteRegions = [];
            hasCustom = false;
            render();
        }
        
        function mergeOverlappingRegions() {
            if (muteRegions.length < 2) return;
            
            const merged = [muteRegions[0]];
            for (let i = 1; i < muteRegions.length; i++) {
                const last = merged[merged.length - 1];
                const curr = muteRegions[i];
                
                if (curr.start_seconds <= last.end_seconds) {
                    last.end_seconds = Math.max(last.end_seconds, curr.end_seconds);
                } else {
                    merged.push(curr);
                }
            }
            muteRegions = merged;
        }
        
        function setSelection(value) {
            selectedOption = value;
            render();
        }
        
        async function createCustomInstrumental() {
            const btn = document.getElementById('create-custom-btn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Creating...';
            }
            
            try {
                const response = await fetch(`${API_BASE}/create-custom-instrumental`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mute_regions: muteRegions })
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to create custom instrumental');
                }
                
                hasCustom = true;
                selectedOption = 'custom';
                activeAudio = 'custom';
                render();
            } catch (error) {
                showError(error.message);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Create Custom Instrumental';
                }
            }
        }
        
        async function submitSelection() {
            const btn = document.getElementById('submit-btn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Submitting...';
            }
            
            try {
                const response = await fetch(`${API_BASE}/select-instrumental`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ selection: selectedOption })
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to submit selection');
                }
                
                // Show success message
                document.getElementById('main-content').innerHTML = `
                    <div class="alert alert-success" style="max-width: 600px; margin: 4rem auto; text-align: center;">
                        <h2 style="margin-bottom: 1rem;">✓ Selection Submitted!</h2>
                        <p>You selected: <strong>${selectedOption === 'clean' ? 'Clean Instrumental' : selectedOption === 'with_backing' ? 'Instrumental with Backing Vocals' : 'Custom Instrumental'}</strong></p>
                        <p style="margin-top: 1rem; color: var(--text-muted);">You can close this window now.</p>
                    </div>
                `;
            } catch (error) {
                showError(error.message);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '✓ Confirm Selection & Continue';
                }
            }
        }
        
        function showError(message) {
            const container = document.getElementById('error-container');
            if (container) {
                container.innerHTML = `<div class="alert alert-error">${message}</div>`;
            }
        }
        
        // Start
        init();
    </script>
</body>
</html>'''
    
    def start_and_open_browser(self, port: int = 8765) -> str:
        """
        Start server, open browser, and block until selection is submitted.
        
        Args:
            port: Port to run the server on
            
        Returns:
            The user's selection ("clean", "with_backing", or "custom")
        """
        self._app = self._create_app()
        
        # Run uvicorn in a separate thread
        config = uvicorn.Config(
            self._app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        
        def run_server():
            server.run()
        
        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()
        
        # Wait a moment for server to start
        import time
        time.sleep(0.5)
        
        url = f"http://localhost:{port}/"
        logger.info(f"Instrumental review server started at {url}")
        
        # Open browser
        webbrowser.open(url)
        
        # Wait for selection
        logger.info("Waiting for instrumental selection...")
        self._selection_event.wait()
        
        # Give a moment for response to be sent
        time.sleep(0.5)
        
        return self.get_selection()
    
    def stop(self) -> None:
        """Stop the server."""
        self._shutdown_event.set()
    
    def get_selection(self) -> str:
        """Get the user's selection."""
        if self.selection is None:
            raise ValueError("No selection has been made")
        return self.selection
    
    def get_custom_instrumental_path(self) -> Optional[str]:
        """Get the path to the custom instrumental if one was created."""
        return self.custom_instrumental_path
