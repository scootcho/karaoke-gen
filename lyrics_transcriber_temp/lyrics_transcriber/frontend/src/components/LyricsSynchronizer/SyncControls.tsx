import { memo } from 'react'
import {
    Box,
    Button,
    Divider,
    Stack
} from '@mui/material'
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'
import StopIcon from '@mui/icons-material/Stop'
import PauseIcon from '@mui/icons-material/Pause'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import ClearAllIcon from '@mui/icons-material/ClearAll'
import EditNoteIcon from '@mui/icons-material/EditNote'
import BlockIcon from '@mui/icons-material/Block'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'

interface SyncControlsProps {
    // Main buttons
    isManualSyncing: boolean
    isPaused: boolean
    onStartSync: () => void
    onPauseSync: () => void
    onResumeSync: () => void
    onClearSync: () => void
    onEditLyrics: () => void
    
    // Playback controls
    onPlay: () => void
    onStop: () => void
    isPlaying: boolean
    
    // Word action buttons
    hasSelectedWords: boolean
    selectedWordCount: number
    onUnsyncFromCursor: () => void
    onEditSelectedWord: () => void
    onDeleteSelected: () => void
    
    // Additional state
    canUnsyncFromCursor: boolean
}

const SyncControls = memo(function SyncControls({
    isManualSyncing,
    isPaused,
    onStartSync,
    onPauseSync,
    onResumeSync,
    onClearSync,
    onEditLyrics,
    onPlay,
    onStop,
    isPlaying,
    hasSelectedWords,
    selectedWordCount,
    onUnsyncFromCursor,
    onEditSelectedWord,
    onDeleteSelected,
    canUnsyncFromCursor
}: SyncControlsProps) {
    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {/* Row 1: Playback & Sync Mode Controls */}
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                {/* Playback controls */}
                <Button
                    variant="outlined"
                    color="primary"
                    onClick={onPlay}
                    startIcon={<PlayArrowIcon />}
                    size="small"
                    disabled={isPlaying}
                >
                    Play
                </Button>
                <Button
                    variant="outlined"
                    color="error"
                    onClick={onStop}
                    startIcon={<StopIcon />}
                    size="small"
                    disabled={!isPlaying}
                >
                    Stop
                </Button>

                <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

                {/* Sync Mode controls */}
                {isManualSyncing ? (
                    <>
                        <Button
                            variant="contained"
                            color="error"
                            onClick={onStartSync}
                            startIcon={<StopIcon />}
                            size="small"
                        >
                            Stop Sync
                        </Button>
                        <Button
                            variant="outlined"
                            color={isPaused ? 'success' : 'warning'}
                            onClick={isPaused ? onResumeSync : onPauseSync}
                            startIcon={isPaused ? <PlayArrowIcon /> : <PauseIcon />}
                            size="small"
                        >
                            {isPaused ? 'Resume' : 'Pause'}
                        </Button>
                    </>
                ) : (
                    <Button
                        variant="contained"
                        color="primary"
                        onClick={onStartSync}
                        startIcon={<PlayCircleOutlineIcon />}
                        size="small"
                    >
                        Start Sync
                    </Button>
                )}
            </Stack>

            {/* Row 2: Editing & Word Actions */}
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <Button
                    variant="outlined"
                    color="warning"
                    onClick={onClearSync}
                    startIcon={<ClearAllIcon />}
                    size="small"
                    disabled={isManualSyncing && !isPaused}
                >
                    Clear Sync
                </Button>

                <Button
                    variant="outlined"
                    onClick={onEditLyrics}
                    startIcon={<EditNoteIcon />}
                    size="small"
                    disabled={isManualSyncing && !isPaused}
                >
                    Edit Lyrics
                </Button>

                <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

                <Button
                    variant="outlined"
                    onClick={onUnsyncFromCursor}
                    startIcon={<BlockIcon />}
                    size="small"
                    disabled={!canUnsyncFromCursor || (isManualSyncing && !isPaused)}
                >
                    Unsync from Cursor
                </Button>

                <Button
                    variant="outlined"
                    onClick={onEditSelectedWord}
                    startIcon={<EditIcon />}
                    size="small"
                    disabled={!hasSelectedWords || selectedWordCount !== 1}
                >
                    Edit Word
                </Button>

                <Button
                    variant="outlined"
                    color="error"
                    onClick={onDeleteSelected}
                    startIcon={<DeleteIcon />}
                    size="small"
                    disabled={!hasSelectedWords || (isManualSyncing && !isPaused)}
                >
                    Delete{hasSelectedWords && selectedWordCount > 0 ? ` (${selectedWordCount})` : ''}
                </Button>
            </Stack>
        </Box>
    )
})

export default SyncControls
