import { Box, Typography, CircularProgress, Alert, Button, FormControlLabel, Checkbox } from '@mui/material'
import { useState, useEffect, useCallback } from 'react'
import { ApiClient } from '../api'
import { CorrectionData } from '../types'
import { applyOffsetToCorrectionData } from './shared/utils/timingUtils'

interface PreviewVideoSectionProps {
    apiClient: ApiClient | null
    isModalOpen: boolean
    updatedData: CorrectionData
    videoRef?: React.RefObject<HTMLVideoElement>
    timingOffsetMs?: number
}

export default function PreviewVideoSection({
    apiClient,
    isModalOpen,
    updatedData,
    videoRef,
    timingOffsetMs = 0
}: PreviewVideoSectionProps) {
    const [previewState, setPreviewState] = useState<{
        status: 'loading' | 'ready' | 'error';
        videoUrl?: string;
        error?: string;
    }>({ status: 'loading' });

    // Toggle for rendering with theme background image (slower) vs black background (faster)
    const [useBackgroundImage, setUseBackgroundImage] = useState(false);

    // Memoized function to generate preview
    const generatePreview = useCallback(async () => {
        if (!apiClient) return;

        setPreviewState({ status: 'loading' });
        try {
            // Debug logging for timing offset
            console.log(`[TIMING] PreviewVideoSection - Current timing offset: ${timingOffsetMs}ms`);
            console.log(`[PREVIEW] Using background image: ${useBackgroundImage}`);

            // Apply timing offset if needed
            const dataToPreview = timingOffsetMs !== 0
                ? applyOffsetToCorrectionData(updatedData, timingOffsetMs)
                : updatedData;

            // Log some example timestamps after potential offset application
            if (dataToPreview.corrected_segments.length > 0) {
                const firstSegment = dataToPreview.corrected_segments[0];
                console.log(`[TIMING] Preview - First segment id: ${firstSegment.id}`);
                console.log(`[TIMING] - start_time: ${firstSegment.start_time}, end_time: ${firstSegment.end_time}`);

                if (firstSegment.words.length > 0) {
                    const firstWord = firstSegment.words[0];
                    console.log(`[TIMING] - first word "${firstWord.text}" time: ${firstWord.start_time} -> ${firstWord.end_time}`);
                }
            }

            const response = await apiClient.generatePreviewVideo(dataToPreview, {
                use_background_image: useBackgroundImage
            });

            if (response.status === 'error') {
                setPreviewState({
                    status: 'error',
                    error: response.message || 'Failed to generate preview video'
                });
                return;
            }

            if (!response.preview_hash) {
                setPreviewState({
                    status: 'error',
                    error: 'No preview hash received from server'
                });
                return;
            }

            const videoUrl = apiClient.getPreviewVideoUrl(response.preview_hash);
            setPreviewState({
                status: 'ready',
                videoUrl
            });
        } catch (error) {
            setPreviewState({
                status: 'error',
                error: (error as Error).message || 'Failed to generate preview video'
            });
        }
    }, [apiClient, updatedData, timingOffsetMs, useBackgroundImage]);

    // Generate preview when modal opens or when background toggle changes
    useEffect(() => {
        if (isModalOpen && apiClient) {
            generatePreview();
        }
    }, [isModalOpen, apiClient, generatePreview]);

    if (!apiClient) return null;

    return (
        <Box sx={{ mb: 2 }}>
            {/* Background image toggle */}
            <Box sx={{ px: 2, pt: 2, pb: 1 }}>
                <FormControlLabel
                    control={
                        <Checkbox
                            checked={useBackgroundImage}
                            onChange={(e) => setUseBackgroundImage(e.target.checked)}
                            disabled={previewState.status === 'loading'}
                            size="small"
                        />
                    }
                    label={
                        <Box>
                            <Typography variant="body2" component="span">
                                Render with theme background
                            </Typography>
                            <Typography variant="caption" color="text.secondary" display="block">
                                Preview uses black background for speed (~10s). Enable for theme background (~30-60s).
                            </Typography>
                        </Box>
                    }
                />
            </Box>

            {previewState.status === 'loading' && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2 }}>
                    <CircularProgress size={24} />
                    <Typography>Generating preview video{useBackgroundImage ? ' with theme background' : ''}...</Typography>
                </Box>
            )}

            {previewState.status === 'error' && (
                <Box sx={{ mb: 2 }}>
                    <Alert
                        severity="error"
                        action={
                            <Button
                                color="inherit"
                                size="small"
                                onClick={() => {
                                    // Re-trigger the effect by toggling isModalOpen
                                    setPreviewState({ status: 'loading' });
                                }}
                            >
                                Retry
                            </Button>
                        }
                    >
                        {previewState.error}
                    </Alert>
                </Box>
            )}

            {previewState.status === 'ready' && previewState.videoUrl && (
                <Box sx={{
                    width: '100%',
                    margin: '0',
                }}>
                    <video
                        ref={videoRef}
                        controls
                        autoPlay
                        src={previewState.videoUrl}
                        style={{
                            display: 'block',
                            width: '100%',
                            height: 'auto',
                        }}
                    >
                        Your browser does not support the video tag.
                    </video>
                </Box>
            )}
        </Box>
    );
} 