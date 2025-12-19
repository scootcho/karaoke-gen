import { useState, useCallback, useEffect, useRef, useMemo, memo } from 'react'
import {
    Box,
    Typography,
    Slider,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    Paper,
    Alert
} from '@mui/material'
import ZoomInIcon from '@mui/icons-material/ZoomIn'
import ZoomOutIcon from '@mui/icons-material/ZoomOut'
import { Word, LyricsSegment } from '../../types'
import TimelineCanvas from './TimelineCanvas'
import UpcomingWordsBar from './UpcomingWordsBar'
import SyncControls from './SyncControls'

// Augment window type for audio functions
declare global {
    interface Window {
        getAudioDuration?: () => number
        toggleAudioPlayback?: () => void
        isAudioPlaying?: boolean
    }
}

interface LyricsSynchronizerProps {
    segments: LyricsSegment[]
    currentTime: number
    onPlaySegment?: (startTime: number) => void
    onSave: (segments: LyricsSegment[]) => void
    onCancel: () => void
    setModalSpacebarHandler: (handler: (() => (e: KeyboardEvent) => void) | undefined) => void
}

// Constants for zoom
const MIN_ZOOM_SECONDS = 4.5   // Most zoomed in - 4.5 seconds visible
const MAX_ZOOM_SECONDS = 24    // Most zoomed out - 24 seconds visible
const ZOOM_STEPS = 50          // Number of zoom levels

// Get all words from segments
function getAllWords(segments: LyricsSegment[]): Word[] {
    return segments.flatMap(s => s.words)
}

// Deep clone segments
function cloneSegments(segments: LyricsSegment[]): LyricsSegment[] {
    return JSON.parse(JSON.stringify(segments))
}

const LyricsSynchronizer = memo(function LyricsSynchronizer({
    segments: initialSegments,
    currentTime,
    onPlaySegment,
    onSave,
    onCancel,
    setModalSpacebarHandler
}: LyricsSynchronizerProps) {
    // Working copy of segments
    const [workingSegments, setWorkingSegments] = useState<LyricsSegment[]>(() => 
        cloneSegments(initialSegments)
    )
    
    // Get all words flattened
    const allWords = useMemo(() => getAllWords(workingSegments), [workingSegments])
    
    // Audio duration
    const audioDuration = useMemo(() => {
        if (typeof window.getAudioDuration === 'function') {
            const duration = window.getAudioDuration()
            return duration > 0 ? duration : 300
        }
        return 300 // 5 minute fallback
    }, [])

    // Zoom state (value is the visible time window in seconds)
    const [zoomSeconds, setZoomSeconds] = useState(12) // Default ~12 seconds visible
    
    // Visible time range
    const [visibleStartTime, setVisibleStartTime] = useState(0)
    const visibleEndTime = useMemo(() => 
        Math.min(visibleStartTime + zoomSeconds, audioDuration),
        [visibleStartTime, zoomSeconds, audioDuration]
    )

    // Manual sync state
    const [isManualSyncing, setIsManualSyncing] = useState(false)
    const [isPaused, setIsPaused] = useState(false)
    const [syncWordIndex, setSyncWordIndex] = useState(-1)
    const [isSpacebarPressed, setIsSpacebarPressed] = useState(false)
    const wordStartTimeRef = useRef<number | null>(null)
    const spacebarPressTimeRef = useRef<number | null>(null)
    const currentTimeRef = useRef(currentTime)

    // Selection state
    const [selectedWordIds, setSelectedWordIds] = useState<Set<string>>(new Set())

    // Edit lyrics modal state
    const [showEditLyricsModal, setShowEditLyricsModal] = useState(false)
    const [editLyricsText, setEditLyricsText] = useState('')

    // Edit word modal state
    const [showEditWordModal, setShowEditWordModal] = useState(false)
    const [editWordText, setEditWordText] = useState('')
    const [editWordId, setEditWordId] = useState<string | null>(null)

    // Keep currentTimeRef up to date
    useEffect(() => {
        currentTimeRef.current = currentTime
    }, [currentTime])

    // Auto-scroll to follow playhead during sync
    useEffect(() => {
        if (isManualSyncing && !isPaused && currentTime > 0) {
            // If playhead is near the end of visible area, scroll forward
            if (currentTime > visibleEndTime - (zoomSeconds * 0.1)) {
                const newStart = Math.max(0, currentTime - zoomSeconds * 0.1)
                setVisibleStartTime(newStart)
            }
            // If playhead is before visible area, scroll back
            else if (currentTime < visibleStartTime) {
                setVisibleStartTime(Math.max(0, currentTime - 1))
            }
        }
    }, [currentTime, isManualSyncing, isPaused, visibleStartTime, visibleEndTime, zoomSeconds])

    // Handle zoom slider change
    const handleZoomChange = useCallback((_: Event, value: number | number[]) => {
        const zoomValue = value as number
        // Map slider value (0-50) to zoom range (4.5-24 seconds)
        const newZoomSeconds = MIN_ZOOM_SECONDS + (zoomValue / ZOOM_STEPS) * (MAX_ZOOM_SECONDS - MIN_ZOOM_SECONDS)
        setZoomSeconds(newZoomSeconds)
    }, [])

    // Get slider value from zoom seconds
    const sliderValue = useMemo(() => {
        return ((zoomSeconds - MIN_ZOOM_SECONDS) / (MAX_ZOOM_SECONDS - MIN_ZOOM_SECONDS)) * ZOOM_STEPS
    }, [zoomSeconds])

    // Handle scroll change from timeline
    const handleScrollChange = useCallback((newStartTime: number) => {
        setVisibleStartTime(newStartTime)
    }, [])

    // Update words in segments
    const updateWords = useCallback((newWords: Word[]) => {
        setWorkingSegments(prevSegments => {
            const newSegments = cloneSegments(prevSegments)
            
            // Create a map of word id to word for quick lookup
            const wordMap = new Map(newWords.map(w => [w.id, w]))
            
            // Update each segment's words
            for (const segment of newSegments) {
                segment.words = segment.words.map(w => wordMap.get(w.id) || w)
                
                // Recalculate segment timing
                const timedWords = segment.words.filter(w => 
                    w.start_time !== null && w.end_time !== null
                )
                
                if (timedWords.length > 0) {
                    segment.start_time = Math.min(...timedWords.map(w => w.start_time!))
                    segment.end_time = Math.max(...timedWords.map(w => w.end_time!))
                } else {
                    segment.start_time = null
                    segment.end_time = null
                }
            }
            
            return newSegments
        })
    }, [])

    // Check if audio is playing
    const [isPlaying, setIsPlaying] = useState(false)
    
    // Update isPlaying state periodically
    useEffect(() => {
        const checkPlaying = () => {
            setIsPlaying(typeof window.isAudioPlaying === 'boolean' ? window.isAudioPlaying : false)
        }
        checkPlaying()
        const interval = setInterval(checkPlaying, 100)
        return () => clearInterval(interval)
    }, [])

    // Play audio from current position
    const handlePlayAudio = useCallback(() => {
        if (onPlaySegment) {
            onPlaySegment(currentTimeRef.current)
        }
    }, [onPlaySegment])

    // Stop audio playback - also exits sync mode
    const handleStopAudio = useCallback(() => {
        if (typeof window.toggleAudioPlayback === 'function' && window.isAudioPlaying) {
            window.toggleAudioPlayback()
        }
        // Also exit sync mode when stopping
        if (isManualSyncing) {
            setIsManualSyncing(false)
            setIsPaused(false)
            setIsSpacebarPressed(false)
        }
    }, [isManualSyncing])

    // Start manual sync
    const handleStartSync = useCallback(() => {
        if (isManualSyncing) {
            // Stop sync
            setIsManualSyncing(false)
            setIsPaused(false)
            setSyncWordIndex(-1)
            setIsSpacebarPressed(false)
            
            // Stop audio
            handleStopAudio()
            return
        }

        // Find first unsynced word
        const firstUnsyncedIndex = allWords.findIndex(w => 
            w.start_time === null || w.end_time === null
        )
        
        const startIndex = firstUnsyncedIndex !== -1 ? firstUnsyncedIndex : 0
        
        setIsManualSyncing(true)
        setIsPaused(false)
        setSyncWordIndex(startIndex)
        setIsSpacebarPressed(false)
        
        // Start playback
        if (onPlaySegment) {
            onPlaySegment(Math.max(0, currentTimeRef.current - 1))
        }
    }, [isManualSyncing, allWords, onPlaySegment, handleStopAudio])

    // Pause sync
    const handlePauseSync = useCallback(() => {
        setIsPaused(true)
        handleStopAudio()
    }, [handleStopAudio])

    // Resume sync
    const handleResumeSync = useCallback(() => {
        setIsPaused(false)
        
        // Find first unsynced word from current position
        const firstUnsyncedIndex = allWords.findIndex(w => 
            w.start_time === null || w.end_time === null
        )
        
        if (firstUnsyncedIndex !== -1 && firstUnsyncedIndex !== syncWordIndex) {
            setSyncWordIndex(firstUnsyncedIndex)
        }
        
        // Resume playback
        if (onPlaySegment) {
            onPlaySegment(currentTimeRef.current)
        }
    }, [allWords, syncWordIndex, onPlaySegment])

    // Clear all sync data
    const handleClearSync = useCallback(() => {
        setWorkingSegments(prevSegments => {
            const newSegments = cloneSegments(prevSegments)
            
            for (const segment of newSegments) {
                for (const word of segment.words) {
                    word.start_time = null
                    word.end_time = null
                }
                segment.start_time = null
                segment.end_time = null
            }
            
            return newSegments
        })
        
        setSyncWordIndex(-1)
    }, [])

    // Unsync from cursor position
    const handleUnsyncFromCursor = useCallback(() => {
        const cursorTime = currentTimeRef.current
        
        setWorkingSegments(prevSegments => {
            const newSegments = cloneSegments(prevSegments)
            
            for (const segment of newSegments) {
                for (const word of segment.words) {
                    // Reset words that start after cursor position
                    if (word.start_time !== null && word.start_time > cursorTime) {
                        word.start_time = null
                        word.end_time = null
                    }
                }
                
                // Recalculate segment timing
                const timedWords = segment.words.filter(w => 
                    w.start_time !== null && w.end_time !== null
                )
                
                if (timedWords.length > 0) {
                    segment.start_time = Math.min(...timedWords.map(w => w.start_time!))
                    segment.end_time = Math.max(...timedWords.map(w => w.end_time!))
                } else {
                    segment.start_time = null
                    segment.end_time = null
                }
            }
            
            return newSegments
        })
    }, [])

    // Check if there are words after cursor that can be unsynced
    const canUnsyncFromCursor = useMemo(() => {
        const cursorTime = currentTimeRef.current
        return allWords.some(w => 
            w.start_time !== null && w.start_time > cursorTime
        )
    }, [allWords, currentTime])

    // Open edit lyrics modal
    const handleEditLyrics = useCallback(() => {
        const text = workingSegments.map(s => s.text).join('\n')
        setEditLyricsText(text)
        setShowEditLyricsModal(true)
    }, [workingSegments])

    // Save edited lyrics (warning: resets timing)
    const handleSaveEditedLyrics = useCallback(() => {
        const lines = editLyricsText.split('\n').filter(l => l.trim())
        
        const newSegments: LyricsSegment[] = lines.map((line, idx) => {
            const words = line.trim().split(/\s+/).map((text, wIdx) => ({
                id: `word-${idx}-${wIdx}-${Date.now()}`,
                text,
                start_time: null,
                end_time: null,
                confidence: 1.0
            }))
            
            return {
                id: `segment-${idx}-${Date.now()}`,
                text: line.trim(),
                words,
                start_time: null,
                end_time: null
            }
        })
        
        setWorkingSegments(newSegments)
        setShowEditLyricsModal(false)
        setSyncWordIndex(-1)
    }, [editLyricsText])

    // Open edit word modal
    const handleEditSelectedWord = useCallback(() => {
        if (selectedWordIds.size !== 1) return
        
        const wordId = Array.from(selectedWordIds)[0]
        const word = allWords.find(w => w.id === wordId)
        
        if (word) {
            setEditWordId(wordId)
            setEditWordText(word.text)
            setShowEditWordModal(true)
        }
    }, [selectedWordIds, allWords])

    // Save edited word
    const handleSaveEditedWord = useCallback(() => {
        if (!editWordId) return
        
        const newText = editWordText.trim()
        if (!newText) return
        
        // Check if we're splitting into multiple words
        const newWords = newText.split(/\s+/)
        
        if (newWords.length === 1) {
            // Simple rename
            const updatedWords = allWords.map(w => 
                w.id === editWordId ? { ...w, text: newWords[0] } : w
            )
            updateWords(updatedWords)
        } else {
            // Split word - preserve timing for first word, null for rest
            const originalWord = allWords.find(w => w.id === editWordId)
            if (!originalWord) return
            
            setWorkingSegments(prevSegments => {
                const newSegments = cloneSegments(prevSegments)
                
                for (const segment of newSegments) {
                    const wordIndex = segment.words.findIndex(w => w.id === editWordId)
                    if (wordIndex !== -1) {
                        const newWordObjects = newWords.map((text, idx) => ({
                            id: idx === 0 ? editWordId : `${editWordId}-split-${idx}`,
                            text,
                            start_time: idx === 0 ? originalWord.start_time : null,
                            end_time: idx === 0 ? originalWord.end_time : null,
                            confidence: 1.0
                        }))
                        
                        segment.words.splice(wordIndex, 1, ...newWordObjects)
                        segment.text = segment.words.map(w => w.text).join(' ')
                        break
                    }
                }
                
                return newSegments
            })
        }
        
        setShowEditWordModal(false)
        setEditWordId(null)
        setEditWordText('')
        setSelectedWordIds(new Set())
    }, [editWordId, editWordText, allWords, updateWords])

    // Delete selected words
    const handleDeleteSelected = useCallback(() => {
        if (selectedWordIds.size === 0) return
        
        setWorkingSegments(prevSegments => {
            const newSegments = cloneSegments(prevSegments)
            
            for (const segment of newSegments) {
                segment.words = segment.words.filter(w => !selectedWordIds.has(w.id))
                segment.text = segment.words.map(w => w.text).join(' ')
                
                // Recalculate segment timing
                const timedWords = segment.words.filter(w => 
                    w.start_time !== null && w.end_time !== null
                )
                
                if (timedWords.length > 0) {
                    segment.start_time = Math.min(...timedWords.map(w => w.start_time!))
                    segment.end_time = Math.max(...timedWords.map(w => w.end_time!))
                } else {
                    segment.start_time = null
                    segment.end_time = null
                }
            }
            
            // Remove empty segments
            return newSegments.filter(s => s.words.length > 0)
        })
        
        setSelectedWordIds(new Set())
    }, [selectedWordIds])

    // Handle word click (selection)
    const handleWordClick = useCallback((wordId: string, event: React.MouseEvent) => {
        if (event.shiftKey || event.ctrlKey || event.metaKey) {
            // Add to selection
            setSelectedWordIds(prev => {
                const newSet = new Set(prev)
                if (newSet.has(wordId)) {
                    newSet.delete(wordId)
                } else {
                    newSet.add(wordId)
                }
                return newSet
            })
        } else {
            // Single selection
            setSelectedWordIds(new Set([wordId]))
        }
    }, [])

    // Handle background click (deselect)
    const handleBackgroundClick = useCallback(() => {
        setSelectedWordIds(new Set())
    }, [])

    // Handle single word timing change (from resize)
    const handleWordTimingChange = useCallback((wordId: string, newStartTime: number, newEndTime: number) => {
        setWorkingSegments(prevSegments => {
            const newSegments = cloneSegments(prevSegments)
            
            for (const segment of newSegments) {
                const word = segment.words.find(w => w.id === wordId)
                if (word) {
                    word.start_time = Math.max(0, newStartTime)
                    word.end_time = Math.max(word.start_time + 0.05, newEndTime)
                    
                    // Recalculate segment timing
                    const timedWords = segment.words.filter(w => 
                        w.start_time !== null && w.end_time !== null
                    )
                    if (timedWords.length > 0) {
                        segment.start_time = Math.min(...timedWords.map(w => w.start_time!))
                        segment.end_time = Math.max(...timedWords.map(w => w.end_time!))
                    }
                    break
                }
            }
            
            return newSegments
        })
    }, [])

    // Handle moving multiple words (from drag)
    const handleWordsMove = useCallback((updates: Array<{ wordId: string; newStartTime: number; newEndTime: number }>) => {
        setWorkingSegments(prevSegments => {
            const newSegments = cloneSegments(prevSegments)
            
            // Create a map for quick lookup
            const updateMap = new Map(updates.map(u => [u.wordId, u]))
            
            for (const segment of newSegments) {
                for (const word of segment.words) {
                    const update = updateMap.get(word.id)
                    if (update) {
                        word.start_time = update.newStartTime
                        word.end_time = update.newEndTime
                    }
                }
                
                // Recalculate segment timing
                const timedWords = segment.words.filter(w => 
                    w.start_time !== null && w.end_time !== null
                )
                if (timedWords.length > 0) {
                    segment.start_time = Math.min(...timedWords.map(w => w.start_time!))
                    segment.end_time = Math.max(...timedWords.map(w => w.end_time!))
                }
            }
            
            return newSegments
        })
    }, [])

    // Handle time bar click (seek to position without playing)
    const handleTimeBarClick = useCallback((time: number) => {
        // Scroll the timeline to show this time centered
        const newStart = Math.max(0, time - zoomSeconds / 2)
        setVisibleStartTime(Math.min(newStart, Math.max(0, audioDuration - zoomSeconds)))
        
        // Seek to the position (this will briefly start playback)
        if (onPlaySegment) {
            onPlaySegment(time)
            // Immediately stop playback after seeking
            setTimeout(() => {
                if (typeof window.toggleAudioPlayback === 'function' && window.isAudioPlaying) {
                    window.toggleAudioPlayback()
                }
            }, 50)
        }
    }, [zoomSeconds, audioDuration, onPlaySegment])

    // Handle selection complete from drag
    const handleSelectionComplete = useCallback((wordIds: string[]) => {
        setSelectedWordIds(new Set(wordIds))
    }, [])

    // Handle spacebar for manual sync
    const handleKeyDown = useCallback((e: KeyboardEvent) => {
        if (e.code !== 'Space') return
        if (!isManualSyncing || isPaused) return
        if (syncWordIndex < 0 || syncWordIndex >= allWords.length) return
        
        e.preventDefault()
        e.stopPropagation()
        
        if (isSpacebarPressed) return
        
        setIsSpacebarPressed(true)
        wordStartTimeRef.current = currentTimeRef.current
        spacebarPressTimeRef.current = Date.now()
        
        // Set start time for current word
        const newWords = [...allWords]
        const currentWord = newWords[syncWordIndex]
        currentWord.start_time = currentTimeRef.current
        
        // Handle previous word's end time
        if (syncWordIndex > 0) {
            const prevWord = newWords[syncWordIndex - 1]
            if (prevWord.start_time !== null && prevWord.end_time === null) {
                const gap = currentTimeRef.current - prevWord.start_time
                if (gap > 1.0) {
                    prevWord.end_time = prevWord.start_time + 0.5
                } else {
                    prevWord.end_time = currentTimeRef.current - 0.005
                }
            }
        }
        
        updateWords(newWords)
    }, [isManualSyncing, isPaused, syncWordIndex, allWords, isSpacebarPressed, updateWords])

    const handleKeyUp = useCallback((e: KeyboardEvent) => {
        if (e.code !== 'Space') return
        if (!isManualSyncing || isPaused) return
        if (!isSpacebarPressed) return
        
        e.preventDefault()
        e.stopPropagation()
        
        setIsSpacebarPressed(false)
        
        const pressDuration = spacebarPressTimeRef.current 
            ? Date.now() - spacebarPressTimeRef.current 
            : 0
        const isTap = pressDuration < 200 // 200ms threshold
        
        const newWords = [...allWords]
        const currentWord = newWords[syncWordIndex]
        
        if (isTap) {
            // Short tap: default 500ms duration
            currentWord.end_time = (wordStartTimeRef.current || currentTimeRef.current) + 0.5
        } else {
            // Hold: use actual timing
            currentWord.end_time = currentTimeRef.current
        }
        
        updateWords(newWords)
        
        // Move to next word
        if (syncWordIndex < allWords.length - 1) {
            setSyncWordIndex(syncWordIndex + 1)
        } else {
            // All words synced
            setIsManualSyncing(false)
            setSyncWordIndex(-1)
            handleStopAudio()
        }
        
        wordStartTimeRef.current = null
        spacebarPressTimeRef.current = null
    }, [isManualSyncing, isPaused, isSpacebarPressed, syncWordIndex, allWords, updateWords, handleStopAudio])

    // Combined spacebar handler
    const handleSpacebar = useCallback((e: KeyboardEvent) => {
        if (e.type === 'keydown') {
            handleKeyDown(e)
        } else if (e.type === 'keyup') {
            handleKeyUp(e)
        }
    }, [handleKeyDown, handleKeyUp])

    // Keep ref for handler
    const spacebarHandlerRef = useRef(handleSpacebar)
    spacebarHandlerRef.current = handleSpacebar

    // Set up spacebar handler
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.code === 'Space') {
                e.preventDefault()
                e.stopPropagation()
                spacebarHandlerRef.current(e)
            }
        }
        
        setModalSpacebarHandler(() => handler)
        
        return () => {
            setModalSpacebarHandler(undefined)
        }
    }, [setModalSpacebarHandler])

    // Handle save
    const handleSave = useCallback(() => {
        onSave(workingSegments)
    }, [workingSegments, onSave])

    // Progress stats
    const stats = useMemo(() => {
        const total = allWords.length
        const synced = allWords.filter(w => 
            w.start_time !== null && w.end_time !== null
        ).length
        return { total, synced, remaining: total - synced }
    }, [allWords])

    // Get instruction text based on state
    const getInstructionText = useCallback(() => {
        if (isManualSyncing) {
            if (isSpacebarPressed) {
                // Always include secondary text to prevent layout shift
                return { primary: '⏱️ Holding... release when word ends', secondary: 'Release spacebar when the word finishes' }
            }
            if (stats.remaining === 0) {
                return { primary: '✅ All words synced!', secondary: 'Click "Stop Sync" then "Apply" to save' }
            }
            return { primary: '👆 Press SPACEBAR when you hear each word', secondary: 'Tap for short words, hold for longer words' }
        }
        if (stats.synced === 0) {
            return { primary: 'Click "Start Sync" to begin timing words', secondary: 'Audio will play and you\'ll tap spacebar for each word' }
        }
        if (stats.remaining > 0) {
            return { primary: `${stats.remaining} words remaining to sync`, secondary: 'Click "Start Sync" to continue, or "Unsync from Cursor" to re-sync from a point' }
        }
        return { primary: '✅ All words synced!', secondary: 'Click "Apply" to save changes, or make adjustments first' }
    }, [isManualSyncing, isSpacebarPressed, stats.synced, stats.remaining])

    const instruction = getInstructionText()

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 1 }}>
            {/* Stats bar - fixed height */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', height: 24 }}>
                <Typography variant="body2" color="text.secondary">
                    {stats.synced} / {stats.total} words synced
                    {stats.remaining > 0 && ` (${stats.remaining} remaining)`}
                </Typography>
            </Box>

            {/* Instruction banner - fixed height to prevent layout shifts */}
            <Box 
                sx={{ 
                    height: 56,
                    flexShrink: 0
                }}
            >
                <Paper 
                    sx={{ 
                        p: 1.5, 
                        height: '100%',
                        bgcolor: isManualSyncing ? 'info.main' : 'grey.100',
                        color: isManualSyncing ? 'info.contrastText' : 'text.primary',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center',
                        overflow: 'hidden',
                        boxSizing: 'border-box'
                    }}
                >
                    <Typography variant="body2" sx={{ fontWeight: 500, lineHeight: 1.3 }}>
                        {instruction.primary}
                    </Typography>
                    <Typography variant="caption" sx={{ opacity: 0.85, display: 'block', lineHeight: 1.3 }}>
                        {instruction.secondary}
                    </Typography>
                </Paper>
            </Box>

            {/* Controls - fixed height section */}
            <Box sx={{ height: 88, flexShrink: 0 }}>
                <SyncControls
                isManualSyncing={isManualSyncing}
                isPaused={isPaused}
                onStartSync={handleStartSync}
                onPauseSync={handlePauseSync}
                onResumeSync={handleResumeSync}
                onClearSync={handleClearSync}
                onEditLyrics={handleEditLyrics}
                onPlay={handlePlayAudio}
                onStop={handleStopAudio}
                isPlaying={isPlaying}
                hasSelectedWords={selectedWordIds.size > 0}
                selectedWordCount={selectedWordIds.size}
                onUnsyncFromCursor={handleUnsyncFromCursor}
                onEditSelectedWord={handleEditSelectedWord}
                onDeleteSelected={handleDeleteSelected}
                canUnsyncFromCursor={canUnsyncFromCursor}
            />
            </Box>

            {/* Upcoming words bar - fixed height, immediately above timeline */}
            <Box sx={{ height: 44, flexShrink: 0 }}>
                {isManualSyncing && (
                    <UpcomingWordsBar
                        words={allWords}
                        syncWordIndex={syncWordIndex}
                        isManualSyncing={isManualSyncing}
                    />
                )}
            </Box>

            {/* Timeline canvas */}
            <Box sx={{ flexGrow: 1, minHeight: 200 }}>
                <TimelineCanvas
                    words={allWords}
                    segments={workingSegments}
                    visibleStartTime={visibleStartTime}
                    visibleEndTime={visibleEndTime}
                    currentTime={currentTime}
                    selectedWordIds={selectedWordIds}
                    onWordClick={handleWordClick}
                    onBackgroundClick={handleBackgroundClick}
                    onTimeBarClick={handleTimeBarClick}
                    onSelectionComplete={handleSelectionComplete}
                    onWordTimingChange={handleWordTimingChange}
                    onWordsMove={handleWordsMove}
                    syncWordIndex={syncWordIndex}
                    isManualSyncing={isManualSyncing}
                    onScrollChange={handleScrollChange}
                    audioDuration={audioDuration}
                    zoomSeconds={zoomSeconds}
                    height={200}
                />
            </Box>

            {/* Zoom slider */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 2 }}>
                <ZoomInIcon color="action" fontSize="small" />
                <Slider
                    value={sliderValue}
                    onChange={handleZoomChange}
                    min={0}
                    max={ZOOM_STEPS}
                    step={1}
                    sx={{ flexGrow: 1 }}
                    disabled={isManualSyncing && !isPaused}
                />
                <ZoomOutIcon color="action" fontSize="small" />
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 60 }}>
                    {zoomSeconds.toFixed(1)}s view
                </Typography>
            </Box>

            {/* Action buttons */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                <Button onClick={onCancel} color="inherit">
                    Cancel
                </Button>
                <Button 
                    onClick={handleSave} 
                    variant="contained" 
                    color="primary"
                    disabled={isManualSyncing && !isPaused}
                >
                    Apply
                </Button>
            </Box>

            {/* Edit Lyrics Modal */}
            <Dialog
                open={showEditLyricsModal}
                onClose={() => setShowEditLyricsModal(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Edit Lyrics</DialogTitle>
                <DialogContent>
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Editing lyrics will reset all timing data. You will need to re-sync the entire song.
                    </Alert>
                    <TextField
                        multiline
                        rows={15}
                        fullWidth
                        value={editLyricsText}
                        onChange={(e) => setEditLyricsText(e.target.value)}
                        placeholder="Enter lyrics, one line per segment..."
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowEditLyricsModal(false)}>Cancel</Button>
                    <Button onClick={handleSaveEditedLyrics} variant="contained" color="warning">
                        Save & Reset Timing
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Edit Word Modal */}
            <Dialog
                open={showEditWordModal}
                onClose={() => setShowEditWordModal(false)}
                maxWidth="xs"
                fullWidth
            >
                <DialogTitle>Edit Word</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Edit the word text. Enter multiple words separated by spaces to split.
                    </Typography>
                    <TextField
                        fullWidth
                        value={editWordText}
                        onChange={(e) => setEditWordText(e.target.value)}
                        autoFocus
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                handleSaveEditedWord()
                            }
                        }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowEditWordModal(false)}>Cancel</Button>
                    <Button onClick={handleSaveEditedWord} variant="contained">
                        Save
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    )
})

export default LyricsSynchronizer
