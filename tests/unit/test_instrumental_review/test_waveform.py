"""
Unit tests for WaveformGenerator.

Tests cover:
- Waveform image generation
- Segment highlighting
- Mute region highlighting
- Data-only generation
- Error handling
"""

import os
import pytest
from pathlib import Path

from karaoke_gen.instrumental_review import (
    WaveformGenerator,
    AudibleSegment,
    MuteRegion,
)


class TestWaveformGeneratorInit:
    """Tests for WaveformGenerator initialization."""
    
    def test_default_parameters(self):
        """Test generator creates with sensible defaults."""
        generator = WaveformGenerator()
        
        assert generator.width == 1200
        assert generator.height == 200
        assert generator.dpi == 100
        assert generator.background_color == "#1a1a2e"
    
    def test_custom_parameters(self):
        """Test generator accepts custom parameters."""
        generator = WaveformGenerator(
            width=800,
            height=150,
            background_color="#000000",
            waveform_color="#00ff00",
            dpi=150,
        )
        
        assert generator.width == 800
        assert generator.height == 150
        assert generator.background_color == "#000000"
        assert generator.waveform_color == "#00ff00"
        assert generator.dpi == 150


class TestWaveformImageGeneration:
    """Tests for waveform image generation."""
    
    def test_generate_creates_image_file(self, loud_audio_path, temp_dir):
        """Generate should create a PNG image file."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
        )
        
        assert os.path.exists(output_path)
        assert result == output_path
    
    def test_generate_output_is_png(self, loud_audio_path, temp_dir):
        """Generated file should be a valid PNG."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
        )
        
        # Check PNG magic bytes
        with open(output_path, 'rb') as f:
            header = f.read(8)
        
        assert header[:4] == b'\x89PNG'
    
    def test_generate_creates_parent_directories(self, loud_audio_path, temp_dir):
        """Generate should create parent directories if needed."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "subdir", "nested", "waveform.png")
        
        generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
        )
        
        assert os.path.exists(output_path)
    
    def test_generate_silent_audio(self, silent_audio_path, temp_dir):
        """Generate should work with silent audio."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=silent_audio_path,
            output_path=output_path,
        )
        
        assert os.path.exists(output_path)
    
    def test_generate_mixed_audio(self, mixed_audio_path, temp_dir):
        """Generate should work with mixed audio."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=mixed_audio_path,
            output_path=output_path,
        )
        
        assert os.path.exists(output_path)


class TestSegmentHighlighting:
    """Tests for audible segment highlighting."""
    
    def test_generate_with_segments(self, loud_audio_path, temp_dir):
        """Generate with segment highlights should work."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        segments = [
            AudibleSegment(
                start_seconds=2.0,
                end_seconds=4.0,
                duration_seconds=2.0,
                avg_amplitude_db=-15.0,
            ),
            AudibleSegment(
                start_seconds=6.0,
                end_seconds=8.0,
                duration_seconds=2.0,
                avg_amplitude_db=-20.0,
            ),
        ]
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            segments=segments,
        )
        
        assert os.path.exists(output_path)
    
    def test_generate_with_empty_segments(self, loud_audio_path, temp_dir):
        """Generate with empty segment list should work."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            segments=[],
        )
        
        assert os.path.exists(output_path)


class TestMuteRegionHighlighting:
    """Tests for mute region highlighting."""
    
    def test_generate_with_mute_regions(self, loud_audio_path, temp_dir):
        """Generate with mute region highlights should work."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        mute_regions = [
            MuteRegion(start_seconds=3.0, end_seconds=5.0),
            MuteRegion(start_seconds=7.0, end_seconds=8.0),
        ]
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            mute_regions=mute_regions,
        )
        
        assert os.path.exists(output_path)
    
    def test_generate_with_segments_and_mute_regions(
        self, loud_audio_path, temp_dir
    ):
        """Generate with both segments and mute regions should work."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        segments = [
            AudibleSegment(
                start_seconds=2.0,
                end_seconds=6.0,
                duration_seconds=4.0,
                avg_amplitude_db=-15.0,
            ),
        ]
        
        mute_regions = [
            MuteRegion(start_seconds=3.0, end_seconds=5.0),
        ]
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            segments=segments,
            mute_regions=mute_regions,
        )
        
        assert os.path.exists(output_path)


class TestTimeAxis:
    """Tests for time axis rendering."""
    
    def test_generate_with_time_axis(self, loud_audio_path, temp_dir):
        """Generate with time axis should work."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            show_time_axis=True,
        )
        
        assert os.path.exists(output_path)
    
    def test_generate_without_time_axis(self, loud_audio_path, temp_dir):
        """Generate without time axis should work."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            show_time_axis=False,
        )
        
        assert os.path.exists(output_path)


class TestDataOnlyGeneration:
    """Tests for data-only waveform generation."""
    
    def test_generate_data_only_returns_tuple(self, loud_audio_path):
        """generate_data_only should return (amplitudes, duration) tuple."""
        generator = WaveformGenerator()
        
        result = generator.generate_data_only(loud_audio_path)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
    
    def test_generate_data_only_amplitudes_are_list(self, loud_audio_path):
        """Amplitudes should be a list of floats."""
        generator = WaveformGenerator()
        
        amplitudes, duration = generator.generate_data_only(loud_audio_path)
        
        assert isinstance(amplitudes, list)
        assert all(isinstance(v, float) for v in amplitudes)
    
    def test_generate_data_only_duration_is_float(self, loud_audio_path):
        """Duration should be a float."""
        generator = WaveformGenerator()
        
        amplitudes, duration = generator.generate_data_only(loud_audio_path)
        
        assert isinstance(duration, float)
        # 10 second audio
        assert abs(duration - 10.0) < 0.5
    
    def test_generate_data_only_respects_num_points(self, loud_audio_path):
        """num_points should control number of data points."""
        generator = WaveformGenerator()
        
        amplitudes_100, _ = generator.generate_data_only(
            loud_audio_path, num_points=100
        )
        amplitudes_500, _ = generator.generate_data_only(
            loud_audio_path, num_points=500
        )
        
        # Should be close to requested (may vary slightly due to rounding)
        assert len(amplitudes_100) >= 90
        assert len(amplitudes_100) <= 110
        assert len(amplitudes_500) >= 450
        assert len(amplitudes_500) <= 550
    
    def test_generate_data_only_normalized(self, loud_audio_path):
        """Amplitudes should be normalized to 0-1 range."""
        generator = WaveformGenerator()
        
        amplitudes, _ = generator.generate_data_only(loud_audio_path)
        
        assert all(0.0 <= v <= 1.0 for v in amplitudes)


class TestStereoHandling:
    """Tests for stereo audio handling."""
    
    def test_generate_handles_stereo(self, stereo_audio_path, temp_dir):
        """Generate should handle stereo audio correctly."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        result = generator.generate(
            audio_path=stereo_audio_path,
            output_path=output_path,
        )
        
        assert os.path.exists(output_path)
    
    def test_generate_data_only_handles_stereo(self, stereo_audio_path):
        """generate_data_only should handle stereo audio."""
        generator = WaveformGenerator()
        
        amplitudes, duration = generator.generate_data_only(stereo_audio_path)
        
        assert len(amplitudes) > 0
        assert duration > 0


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_nonexistent_file_raises_error(self, temp_dir):
        """Non-existent audio file should raise FileNotFoundError."""
        generator = WaveformGenerator()
        output_path = os.path.join(temp_dir, "waveform.png")
        
        with pytest.raises(FileNotFoundError):
            generator.generate(
                audio_path="/nonexistent/audio.flac",
                output_path=output_path,
            )
    
    def test_generate_data_only_nonexistent_raises_error(self):
        """generate_data_only with non-existent file should raise."""
        generator = WaveformGenerator()
        
        with pytest.raises(FileNotFoundError):
            generator.generate_data_only("/nonexistent/audio.flac")


class TestCustomColors:
    """Tests for custom color configuration."""
    
    def test_custom_colors_applied(self, loud_audio_path, temp_dir):
        """Custom colors should be applied without error."""
        generator = WaveformGenerator(
            background_color="#ffffff",
            waveform_color="#ff0000",
            segment_color="#00ff00",
            mute_color="#0000ff",
            time_axis_color="#000000",
        )
        output_path = os.path.join(temp_dir, "waveform.png")
        
        segments = [
            AudibleSegment(
                start_seconds=2.0,
                end_seconds=4.0,
                duration_seconds=2.0,
                avg_amplitude_db=-15.0,
            ),
        ]
        
        mute_regions = [
            MuteRegion(start_seconds=6.0, end_seconds=8.0),
        ]
        
        result = generator.generate(
            audio_path=loud_audio_path,
            output_path=output_path,
            segments=segments,
            mute_regions=mute_regions,
        )
        
        assert os.path.exists(output_path)


class TestCustomDimensions:
    """Tests for custom image dimensions."""
    
    def test_different_widths(self, loud_audio_path, temp_dir):
        """Different widths should work."""
        for width in [600, 1200, 1920]:
            generator = WaveformGenerator(width=width)
            output_path = os.path.join(temp_dir, f"waveform_{width}.png")
            
            generator.generate(
                audio_path=loud_audio_path,
                output_path=output_path,
            )
            
            assert os.path.exists(output_path)
    
    def test_different_heights(self, loud_audio_path, temp_dir):
        """Different heights should work."""
        for height in [100, 200, 300]:
            generator = WaveformGenerator(height=height)
            output_path = os.path.join(temp_dir, f"waveform_{height}.png")
            
            generator.generate(
                audio_path=loud_audio_path,
                output_path=output_path,
            )
            
            assert os.path.exists(output_path)
