import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    IconButton,
    Box,
    Button,
    Typography,
    TextField
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import ContentPasteIcon from '@mui/icons-material/ContentPaste'
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import { LyricsSegment, Word } from '../types'
import { useState, useEffect, useCallback, useMemo } from 'react'
import { nanoid } from 'nanoid'
import ModeSelectionModal from './ModeSelectionModal'
import LyricsSynchronizer from './LyricsSynchronizer'

// Augment window type for audio functions
declare global {
    interface Window {
        getAudioDuration?: () => number;
        toggleAudioPlayback?: () => void;
        isAudioPlaying?: boolean;
    }
}

type ModalMode = 'selection' | 'replace' | 'resync'

interface ReplaceAllLyricsModalProps {
    open: boolean
    onClose: () => void
    onSave: (newSegments: LyricsSegment[]) => void
    onPlaySegment?: (startTime: number) => void
    currentTime?: number
    setModalSpacebarHandler: (handler: (() => (e: KeyboardEvent) => void) | undefined) => void
    existingSegments?: LyricsSegment[]  // Current segments for re-sync mode
}

export default function ReplaceAllLyricsModal({
    open,
    onClose,
    onSave,
    onPlaySegment,
    currentTime = 0,
    setModalSpacebarHandler,
    existingSegments = []
}: ReplaceAllLyricsModalProps) {
    const [mode, setMode] = useState<ModalMode>('selection')
    const [inputText, setInputText] = useState('')
    const [newSegments, setNewSegments] = useState<LyricsSegment[]>([])

    // Reset state when modal opens
    useEffect(() => {
        if (open) {
            setMode('selection')
            setInputText('')
            setNewSegments([])
        }
    }, [open])

    // Parse the input text to get line and word counts
    const parseInfo = useMemo(() => {
        if (!inputText.trim()) return { lines: 0, words: 0 }
        
        const lines = inputText.trim().split('\n').filter(line => line.trim().length > 0)
        const totalWords = lines.reduce((count, line) => {
            return count + line.trim().split(/\s+/).length
        }, 0)
        
        return { lines: lines.length, words: totalWords }
    }, [inputText])

    // Process the input text into segments and words
    const processLyrics = useCallback(() => {
        if (!inputText.trim()) return

        const lines = inputText.trim().split('\n').filter(line => line.trim().length > 0)
        const segments: LyricsSegment[] = []

        lines.forEach((line) => {
            const words = line.trim().split(/\s+/).filter(word => word.length > 0)
            const segmentWords: Word[] = words.map((wordText) => ({
                id: nanoid(),
                text: wordText,
                start_time: null,
                end_time: null,
                confidence: 1.0,
                created_during_correction: true
            }))

            segments.push({
                id: nanoid(),
                text: line.trim(),
                words: segmentWords,
                start_time: null,
                end_time: null
            })
        })

        setNewSegments(segments)
        setMode('resync')  // Go to synchronizer with the new segments
    }, [inputText])

    // Handle paste from clipboard
    const handlePasteFromClipboard = useCallback(async () => {
        try {
            const text = await navigator.clipboard.readText()
            setInputText(text)
        } catch (error) {
            console.error('Failed to read from clipboard:', error)
            alert('Failed to read from clipboard. Please paste manually.')
        }
    }, [])

    // Handle modal close
    const handleClose = useCallback(() => {
        setMode('selection')
        setInputText('')
        setNewSegments([])
        onClose()
    }, [onClose])

    // Handle save from synchronizer
    const handleSave = useCallback((segments: LyricsSegment[]) => {
        onSave(segments)
        handleClose()
    }, [onSave, handleClose])

    // Handle mode selection
    const handleSelectReplace = useCallback(() => {
        setMode('replace')
    }, [])

    const handleSelectResync = useCallback(() => {
        setMode('resync')
    }, [])

    // Handle back to selection
    const handleBackToSelection = useCallback(() => {
        setMode('selection')
        setInputText('')
        setNewSegments([])
    }, [])

    // Determine which segments to use for synchronizer
    const segmentsForSync = mode === 'resync' && newSegments.length > 0 
        ? newSegments 
        : existingSegments

    // Check if we have existing lyrics
    const hasExistingLyrics = existingSegments.length > 0 && 
        existingSegments.some(s => s.words.length > 0)

    return (
        <>
            {/* Mode Selection Modal */}
            <ModeSelectionModal
                open={open && mode === 'selection'}
                onClose={handleClose}
                onSelectReplace={handleSelectReplace}
                onSelectResync={handleSelectResync}
                hasExistingLyrics={hasExistingLyrics}
            />

            {/* Replace All Lyrics Modal (Paste Phase) */}
            <Dialog
                open={open && mode === 'replace'}
                onClose={handleClose}
                maxWidth="md"
                fullWidth
                PaperProps={{
                    sx: {
                        height: '80vh',
                        maxHeight: '80vh'
                    }
                }}
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <IconButton onClick={handleBackToSelection} size="small">
                        <ArrowBackIcon />
                    </IconButton>
                    <Box sx={{ flex: 1 }}>
                        Replace All Lyrics
                    </Box>
                    <IconButton onClick={handleClose} sx={{ ml: 'auto' }}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>

                <DialogContent
                    dividers
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        flexGrow: 1,
                        overflow: 'hidden'
                    }}
                >
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, height: '100%' }}>
                        <Typography variant="h6" gutterBottom>
                            Paste your new lyrics below:
                        </Typography>
                        
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            Each line will become a separate segment. Words will be separated by spaces.
                        </Typography>

                        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                            <Button
                                variant="outlined"
                                onClick={handlePasteFromClipboard}
                                startIcon={<ContentPasteIcon />}
                                size="small"
                            >
                                Paste from Clipboard
                            </Button>
                            <Typography variant="body2" sx={{ 
                                alignSelf: 'center', 
                                color: 'text.secondary',
                                fontWeight: 'medium'
                            }}>
                                {parseInfo.lines} lines, {parseInfo.words} words
                            </Typography>
                        </Box>

                        <TextField
                            multiline
                            rows={15}
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            placeholder="Paste your lyrics here...&#10;Each line will become a segment&#10;Words will be separated by spaces"
                            sx={{ 
                                flexGrow: 1,
                                '& .MuiInputBase-root': {
                                    height: '100%',
                                    alignItems: 'flex-start'
                                }
                            }}
                        />
                    </Box>
                </DialogContent>

                <DialogActions>
                    <Button onClick={handleClose} color="inherit">
                        Cancel
                    </Button>
                    <Button
                        variant="contained"
                        onClick={processLyrics}
                        disabled={!inputText.trim()}
                        startIcon={<AutoFixHighIcon />}
                    >
                        Continue to Sync
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Synchronizer Modal */}
            <Dialog
                open={open && mode === 'resync'}
                onClose={handleClose}
                maxWidth={false}
                fullWidth
                PaperProps={{
                    sx: {
                        height: '90vh',
                        margin: '5vh 2vw',
                        maxWidth: 'calc(100vw - 4vw)',
                        width: 'calc(100vw - 4vw)'
                    }
                }}
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <IconButton onClick={handleBackToSelection} size="small">
                        <ArrowBackIcon />
                    </IconButton>
                    <Box sx={{ flex: 1 }}>
                        {newSegments.length > 0 ? 'Sync New Lyrics' : 'Re-sync Existing Lyrics'}
                    </Box>
                    <IconButton onClick={handleClose} sx={{ ml: 'auto' }}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>

                <DialogContent
                    dividers
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        flexGrow: 1,
                        overflow: 'hidden',
                        p: 2
                    }}
                >
                    {segmentsForSync.length > 0 ? (
                        <LyricsSynchronizer
                            segments={segmentsForSync}
                            currentTime={currentTime}
                            onPlaySegment={onPlaySegment}
                            onSave={handleSave}
                            onCancel={handleClose}
                            setModalSpacebarHandler={setModalSpacebarHandler}
                        />
                    ) : (
                        <Box sx={{ 
                            display: 'flex', 
                            flexDirection: 'column', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            height: '100%',
                            gap: 2
                        }}>
                            <Typography variant="h6" color="text.secondary">
                                No lyrics to sync
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Go back and paste new lyrics, or close this modal.
                            </Typography>
                            <Button 
                                variant="outlined" 
                                onClick={handleBackToSelection}
                                startIcon={<ArrowBackIcon />}
                            >
                                Back to Selection
                            </Button>
                        </Box>
                    )}
                </DialogContent>
            </Dialog>
        </>
    )
}
