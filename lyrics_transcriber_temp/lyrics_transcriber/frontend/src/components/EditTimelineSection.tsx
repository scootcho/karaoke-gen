import {
    Box,
    Button,
    Typography,
    IconButton,
    Tooltip,
    Stack,
    useMediaQuery,
    useTheme
} from '@mui/material'
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'
import CancelIcon from '@mui/icons-material/Cancel'
import ZoomInIcon from '@mui/icons-material/ZoomIn'
import ZoomOutIcon from '@mui/icons-material/ZoomOut'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import AutorenewIcon from '@mui/icons-material/Autorenew'
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong'
import TouchAppIcon from '@mui/icons-material/TouchApp'
import TimelineEditor from './TimelineEditor'
import { Word } from '../types'
import { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react'

// Separate TapButton component to properly track local press state
// This prevents issues where onMouseLeave fires before parent state updates
const TapButton = memo(function TapButton({
    isSpacebarPressed,
    onTapStart,
    onTapEnd
}: {
    isSpacebarPressed: boolean
    onTapStart: () => void
    onTapEnd: () => void
}) {
    const isPressedRef = useRef(false)

    const handleTapStart = useCallback(() => {
        isPressedRef.current = true
        onTapStart()
    }, [onTapStart])

    const handleTapEnd = useCallback(() => {
        if (isPressedRef.current) {
            isPressedRef.current = false
            onTapEnd()
        }
    }, [onTapEnd])

    return (
        <Button
            variant="contained"
            color={isSpacebarPressed ? "secondary" : "primary"}
            onTouchStart={(e) => {
                e.preventDefault()
                handleTapStart()
            }}
            onTouchEnd={(e) => {
                e.preventDefault()
                handleTapEnd()
            }}
            onMouseDown={handleTapStart}
            onMouseUp={handleTapEnd}
            onMouseLeave={handleTapEnd}
            startIcon={<TouchAppIcon />}
            sx={{
                py: 2,
                fontSize: '1.1rem',
                fontWeight: 'bold',
                width: '100%',
                minHeight: '56px',
                userSelect: 'none',
                WebkitUserSelect: 'none',
                touchAction: 'manipulation'
            }}
        >
            {isSpacebarPressed ? "HOLD..." : "TAP"}
        </Button>
    )
})

interface EditTimelineSectionProps {
    words: Word[]
    startTime: number
    endTime: number
    originalStartTime: number | null
    originalEndTime: number | null
    currentStartTime: number | null
    currentEndTime: number | null
    currentTime?: number
    isManualSyncing: boolean
    syncWordIndex: number
    isSpacebarPressed: boolean
    onWordUpdate: (index: number, updates: Partial<Word>) => void
    onUnsyncWord?: (index: number) => void
    onPlaySegment?: (time: number) => void
    onStopAudio?: () => void
    startManualSync: () => void
    pauseManualSync?: () => void
    resumeManualSync?: () => void
    isPaused?: boolean
    isGlobal?: boolean
    defaultZoomLevel?: number
    isReplaceAllMode?: boolean
    onTapStart?: () => void
    onTapEnd?: () => void
}

// Memoized control buttons to prevent unnecessary re-renders
const TimelineControls = memo(({
    isGlobal,
    visibleStartTime,
    visibleEndTime,
    startTime,
    endTime,
    zoomLevel,
    autoScrollEnabled,
    currentTime,
    isManualSyncing,
    isReplaceAllMode,
    isPaused,
    onScrollLeft,
    onZoomOut,
    onZoomIn,
    onScrollRight,
    onToggleAutoScroll,
    onJumpToCurrentTime,
    onStartManualSync,
    onPauseResume,
    onStopAudio
}: {
    isGlobal: boolean
    visibleStartTime: number
    visibleEndTime: number
    startTime: number
    endTime: number
    zoomLevel: number
    autoScrollEnabled: boolean
    currentTime?: number
    isManualSyncing: boolean
    isReplaceAllMode: boolean
    isPaused: boolean
    onScrollLeft: () => void
    onZoomOut: () => void
    onZoomIn: () => void
    onScrollRight: () => void
    onToggleAutoScroll: () => void
    onJumpToCurrentTime: () => void
    onStartManualSync: () => void
    onPauseResume: () => void
    onStopAudio?: () => void
}) => {
    return (
        <Stack
            direction="row"
            spacing={0.5}
            alignItems="center"
            sx={{ flexWrap: 'wrap', justifyContent: 'center', gap: 0.5 }}
        >
            {isGlobal && (
                <>
                    <Tooltip title="Scroll Left">
                        <IconButton
                            onClick={onScrollLeft}
                            disabled={visibleStartTime <= startTime}
                            size="small"
                        >
                            <ArrowBackIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Zoom Out (Show More Time)">
                        <IconButton
                            onClick={onZoomOut}
                            disabled={zoomLevel >= (endTime - startTime) || (isReplaceAllMode && isManualSyncing && !isPaused)}
                            size="small"
                        >
                            <ZoomOutIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Zoom In (Show Less Time)">
                        <IconButton
                            onClick={onZoomIn}
                            disabled={zoomLevel <= 2 || (isReplaceAllMode && isManualSyncing && !isPaused)}
                            size="small"
                        >
                            <ZoomInIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Scroll Right">
                        <IconButton
                            onClick={onScrollRight}
                            disabled={visibleEndTime >= endTime}
                            size="small"
                        >
                            <ArrowForwardIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip
                        title={autoScrollEnabled ?
                            "Disable Auto-Page Turn During Playback" :
                            "Enable Auto-Page Turn During Playback"}
                    >
                        <IconButton
                            onClick={onToggleAutoScroll}
                            color={autoScrollEnabled ? "primary" : "default"}
                            size="small"
                        >
                            {autoScrollEnabled ? <AutorenewIcon fontSize="small" /> : <PauseCircleOutlineIcon fontSize="small" />}
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Jump to Current Playback Position">
                        <IconButton
                            onClick={onJumpToCurrentTime}
                            disabled={!currentTime}
                            size="small"
                        >
                            <CenterFocusStrongIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </>
            )}
            {isReplaceAllMode && onStopAudio && (
                <Button
                    variant="outlined"
                    onClick={onStopAudio}
                    startIcon={<StopIcon fontSize="small" />}
                    color="error"
                    size="small"
                >
                    Stop
                </Button>
            )}
            <Button
                variant={isManualSyncing ? "outlined" : "contained"}
                onClick={onStartManualSync}
                startIcon={isManualSyncing ? <CancelIcon fontSize="small" /> : <PlayCircleOutlineIcon fontSize="small" />}
                color={isManualSyncing ? "error" : "primary"}
                size="small"
            >
                {isManualSyncing ? "Cancel" : "Tap To Sync"}
            </Button>
            {isManualSyncing && isReplaceAllMode && (
                <Button
                    variant="outlined"
                    onClick={onPauseResume}
                    startIcon={isPaused ? <PlayArrowIcon fontSize="small" /> : <PauseCircleOutlineIcon fontSize="small" />}
                    color={isPaused ? "success" : "warning"}
                    size="small"
                >
                    {isPaused ? "Resume" : "Pause"}
                </Button>
            )}
        </Stack>
    )
})

export default function EditTimelineSection({
    words,
    startTime,
    endTime,
    originalStartTime,
    originalEndTime,
    currentStartTime,
    currentEndTime,
    currentTime,
    isManualSyncing,
    syncWordIndex,
    isSpacebarPressed,
    onWordUpdate,
    onUnsyncWord,
    onPlaySegment,
    onStopAudio,
    startManualSync,
    pauseManualSync,
    resumeManualSync,
    isPaused = false,
    isGlobal = false,
    defaultZoomLevel = 10,
    isReplaceAllMode = false,
    onTapStart,
    onTapEnd
}: EditTimelineSectionProps) {
    const theme = useTheme()
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'))
    // Add state for zoom level - use larger default for Replace All mode
    const [zoomLevel, setZoomLevel] = useState(defaultZoomLevel)
    const [visibleStartTime, setVisibleStartTime] = useState(startTime)
    const [visibleEndTime, setVisibleEndTime] = useState(Math.min(startTime + zoomLevel, endTime))
    const [autoScrollEnabled, setAutoScrollEnabled] = useState(true) // Default to enabled
    const timelineRef = useRef<HTMLDivElement>(null)

    // Memoize the effective time range to prevent recalculation
    const effectiveTimeRange = useMemo(() => ({
        start: isGlobal ? visibleStartTime : startTime,
        end: isGlobal ? visibleEndTime : endTime
    }), [isGlobal, visibleStartTime, visibleEndTime, startTime, endTime])

    // Auto-enable auto-scroll when manual sync starts or resumes
    useEffect(() => {
        if (isManualSyncing && !isPaused) {
            console.log('EditTimelineSection - Auto-enabling auto-scroll for manual sync')
            setAutoScrollEnabled(true)
        }
    }, [isManualSyncing, isPaused])

    // Initial setup of visible time range
    useEffect(() => {
        if (isGlobal) {
            // For global mode, start at the beginning
            setVisibleStartTime(startTime)
            setVisibleEndTime(Math.min(startTime + zoomLevel, endTime))
        } else {
            // For segment mode, always show the full segment
            setVisibleStartTime(startTime)
            setVisibleEndTime(endTime)
        }
    }, [startTime, endTime, zoomLevel, isGlobal])

    // Throttled auto-scroll to reduce frequent updates during playback
    const lastScrollUpdateRef = useRef<number>(0)
    const SCROLL_THROTTLE_MS = 100 // Only update scroll position every 100ms

    // Handle playback scrolling with "page turning" approach - throttled for performance
    useEffect(() => {
        // Skip if not in global mode, no current time, or auto-scroll is disabled
        if (!isGlobal || !currentTime || !autoScrollEnabled) return

        // Throttle scroll updates for performance
        const now = Date.now()
        if (now - lastScrollUpdateRef.current < SCROLL_THROTTLE_MS) return
        lastScrollUpdateRef.current = now

        // Only scroll when current time is outside or near the edge of the visible window
        if (currentTime < visibleStartTime) {
            // If current time is before visible window, jump to show it at the start
            const newStart = Math.max(startTime, currentTime)
            const newEnd = Math.min(endTime, newStart + zoomLevel)
            setVisibleStartTime(newStart)
            setVisibleEndTime(newEnd)
        } else if (currentTime > visibleEndTime - (zoomLevel * 0.05)) {
            // If current time is near the end of visible window (within 5% of zoom level from the end),
            // jump to the next "page" with current time at 5% from the left
            const pageOffset = zoomLevel * 0.05 // Position current time 5% from the left edge
            const newStart = Math.max(startTime, currentTime - pageOffset)
            const newEnd = Math.min(endTime, newStart + zoomLevel)
            
            // Only update if we're actually moving forward
            if (newStart > visibleStartTime) {
                setVisibleStartTime(newStart)
                setVisibleEndTime(newEnd)
            }
        }
    }, [currentTime, visibleStartTime, visibleEndTime, startTime, endTime, zoomLevel, isGlobal, autoScrollEnabled])

    // Update visible time range when zoom level changes - but don't auto-center on current time
    useEffect(() => {
        if (isGlobal) {
            // Don't auto-center on current time, just adjust the visible window based on zoom level
            // while keeping the left edge fixed (unless it would go out of bounds)
            const newEnd = Math.min(endTime, visibleStartTime + zoomLevel)

            // If the new end would exceed the total range, adjust the start time
            if (newEnd === endTime) {
                const newStart = Math.max(startTime, endTime - zoomLevel)
                setVisibleStartTime(newStart)
            }

            setVisibleEndTime(newEnd)
        } else {
            // For segment mode, always show the full segment
            setVisibleStartTime(startTime)
            setVisibleEndTime(endTime)
        }
    }, [zoomLevel, startTime, endTime, isGlobal, visibleStartTime])

    // Memoized event handlers to prevent unnecessary re-renders
    const handleZoomIn = useCallback(() => {
        if (isReplaceAllMode && isManualSyncing && !isPaused) return // Prevent zoom changes during active sync (but allow when paused)
        if (zoomLevel > 2) { // Minimum zoom level of 2 seconds
            setZoomLevel(zoomLevel - 2)
        }
    }, [isReplaceAllMode, isManualSyncing, isPaused, zoomLevel])

    const handleZoomOut = useCallback(() => {
        if (isReplaceAllMode && isManualSyncing && !isPaused) return // Prevent zoom changes during active sync (but allow when paused)
        if (zoomLevel < (endTime - startTime)) { // Maximum zoom is the full range
            setZoomLevel(zoomLevel + 2)
        }
    }, [isReplaceAllMode, isManualSyncing, isPaused, zoomLevel, endTime, startTime])

    const toggleAutoScroll = useCallback(() => {
        setAutoScrollEnabled(!autoScrollEnabled)
    }, [autoScrollEnabled])

    const jumpToCurrentTime = useCallback(() => {
        if (!isGlobal || !currentTime) return

        // Center the view around the current time
        const halfZoom = zoomLevel / 2
        let newStart = Math.max(startTime, currentTime - halfZoom)
        const newEnd = Math.min(endTime, newStart + zoomLevel)

        // Adjust start time if end time hits the boundary
        if (newEnd === endTime) {
            newStart = Math.max(startTime, endTime - zoomLevel)
        }

        setVisibleStartTime(newStart)
        setVisibleEndTime(newEnd)
    }, [currentTime, zoomLevel, startTime, endTime, isGlobal])

    // Handle horizontal scrolling - throttled for performance
    const handleScroll = useCallback((event: React.WheelEvent<HTMLDivElement>) => {
        if (isGlobal && event.deltaX !== 0) {
            event.preventDefault()

            // Disable auto-scroll when user manually scrolls
            setAutoScrollEnabled(false)

            // Calculate scroll amount in seconds (scale based on zoom level)
            const scrollAmount = (event.deltaX / 100) * (zoomLevel / 10)

            // Update visible time range
            let newStart = visibleStartTime + scrollAmount
            let newEnd = visibleEndTime + scrollAmount

            // Ensure we don't scroll beyond the boundaries
            if (newStart < startTime) {
                newStart = startTime
                newEnd = newStart + zoomLevel
            }

            if (newEnd > endTime) {
                newEnd = endTime
                newStart = Math.max(startTime, newEnd - zoomLevel)
            }

            setVisibleStartTime(newStart)
            setVisibleEndTime(newEnd)
        }
    }, [isGlobal, visibleStartTime, visibleEndTime, startTime, endTime, zoomLevel])

    const handleScrollLeft = useCallback(() => {
        if (!isGlobal) return

        // Disable auto-scroll when user manually scrolls
        setAutoScrollEnabled(false)

        // Scroll left by 25% of the current visible range
        const scrollAmount = zoomLevel * 0.25
        const newStart = Math.max(startTime, visibleStartTime - scrollAmount)
        const newEnd = newStart + zoomLevel

        setVisibleStartTime(newStart)
        setVisibleEndTime(newEnd)
    }, [isGlobal, zoomLevel, startTime, visibleStartTime])

    const handleScrollRight = useCallback(() => {
        if (!isGlobal) return

        // Disable auto-scroll when user manually scrolls
        setAutoScrollEnabled(false)

        // Scroll right by 25% of the current visible range
        const scrollAmount = zoomLevel * 0.25
        const newEnd = Math.min(endTime, visibleEndTime + scrollAmount)
        let newStart = newEnd - zoomLevel

        // Ensure we don't scroll beyond the start boundary
        if (newStart < startTime) {
            newStart = startTime
            const adjustedNewEnd = Math.min(endTime, newStart + zoomLevel)
            setVisibleEndTime(adjustedNewEnd)
        } else {
            setVisibleEndTime(newEnd)
        }

        setVisibleStartTime(newStart)
    }, [isGlobal, zoomLevel, endTime, visibleEndTime, startTime])

    const handlePauseResume = useCallback(() => {
        if (isPaused && resumeManualSync) {
            resumeManualSync()
        } else if (!isPaused && pauseManualSync) {
            pauseManualSync()
        }
    }, [isPaused, resumeManualSync, pauseManualSync])

    // Memoize current word info to prevent recalculation
    const currentWordInfo = useMemo(() => {
        if (!isManualSyncing || syncWordIndex < 0 || syncWordIndex >= words.length) {
            return null
        }
        
        return {
            index: syncWordIndex + 1,
            total: words.length,
            text: words[syncWordIndex]?.text || ''
        }
    }, [isManualSyncing, syncWordIndex, words])

    return (
        <>
            <Box
                sx={{ height: isMobile ? '80px' : '120px', mb: 0 }}
                ref={timelineRef}
                onWheel={handleScroll}
            >
                <TimelineEditor
                    words={words}
                    startTime={effectiveTimeRange.start}
                    endTime={effectiveTimeRange.end}
                    onWordUpdate={onWordUpdate}
                    currentTime={currentTime}
                    onPlaySegment={onPlaySegment}
                    onUnsyncWord={onUnsyncWord}
                />
            </Box>

            <Box sx={{
                display: 'flex',
                flexDirection: isMobile ? 'column' : 'row',
                alignItems: isMobile ? 'stretch' : 'center',
                justifyContent: 'space-between',
                gap: isMobile ? 1 : 0,
                mt: isMobile ? 1.5 : 0,
                mb: isMobile ? 2 : 0
            }}>
                {/* Time range info - hidden on mobile to save space */}
                {!isMobile && (
                    <Typography variant="body2" color="text.secondary">
                        Original Time Range: {originalStartTime?.toFixed(2) ?? 'N/A'} - {originalEndTime?.toFixed(2) ?? 'N/A'}
                        <br />
                        Current Time Range: {currentStartTime?.toFixed(2) ?? 'N/A'} - {currentEndTime?.toFixed(2) ?? 'N/A'}
                    </Typography>
                )}

                <Box sx={{
                    display: 'flex',
                    flexDirection: isMobile ? 'column' : 'row',
                    alignItems: isMobile ? 'stretch' : 'center',
                    gap: isMobile ? 1 : 2
                }}>
                    <TimelineControls
                        isGlobal={isGlobal}
                        visibleStartTime={visibleStartTime}
                        visibleEndTime={visibleEndTime}
                        startTime={startTime}
                        endTime={endTime}
                        zoomLevel={zoomLevel}
                        autoScrollEnabled={autoScrollEnabled}
                        currentTime={currentTime}
                        isManualSyncing={isManualSyncing}
                        isReplaceAllMode={isReplaceAllMode}
                        isPaused={isPaused}
                        onScrollLeft={handleScrollLeft}
                        onZoomOut={handleZoomOut}
                        onZoomIn={handleZoomIn}
                        onScrollRight={handleScrollRight}
                        onToggleAutoScroll={toggleAutoScroll}
                        onJumpToCurrentTime={jumpToCurrentTime}
                        onStartManualSync={startManualSync}
                        onPauseResume={handlePauseResume}
                        onStopAudio={onStopAudio}
                    />
                    {currentWordInfo && (
                        <Box sx={{ textAlign: isMobile ? 'center' : 'left' }}>
                            <Typography variant="body2">
                                Word {currentWordInfo.index} of {currentWordInfo.total}: <strong>{currentWordInfo.text}</strong>
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {isSpacebarPressed ?
                                    "Holding... Release when word ends" :
                                    (isMobile ? "Tap the button when word starts" : "Press spacebar when word starts (tap for short words, hold for long words)")}
                            </Typography>
                        </Box>
                    )}
                    {/* Mobile TAP button for manual sync */}
                    {isMobile && isManualSyncing && onTapStart && onTapEnd && (
                        <TapButton
                            isSpacebarPressed={isSpacebarPressed}
                            onTapStart={onTapStart}
                            onTapEnd={onTapEnd}
                        />
                    )}
                </Box>
            </Box>
        </>
    )
} 