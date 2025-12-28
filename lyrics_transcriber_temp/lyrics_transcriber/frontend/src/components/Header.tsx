import { Box, Button, Typography, useMediaQuery, useTheme, Switch, FormControlLabel, Tooltip, Paper, IconButton } from '@mui/material'
import LockIcon from '@mui/icons-material/Lock'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import FindReplaceIcon from '@mui/icons-material/FindReplace'
import EditIcon from '@mui/icons-material/Edit'
import UndoIcon from '@mui/icons-material/Undo'
import RedoIcon from '@mui/icons-material/Redo'
import TimerIcon from '@mui/icons-material/Timer'
import RestoreIcon from '@mui/icons-material/Restore'
import RateReviewIcon from '@mui/icons-material/RateReview'
import { CorrectionData, InteractionMode } from '../types'
import CorrectionMetrics from './CorrectionMetrics'
import AgenticCorrectionMetrics from './AgenticCorrectionMetrics'
import ModeSelector from './ModeSelector'
import AudioPlayer from './AudioPlayer'
import { ApiClient } from '../api'
import { findWordById } from './shared/utils/wordUtils'

interface HeaderProps {
    isReadOnly: boolean
    onFileLoad: () => void
    data: CorrectionData
    onMetricClick: {
        anchor: () => void
        corrected: () => void
        uncorrected: () => void
    }
    effectiveMode: InteractionMode
    onModeChange: (mode: InteractionMode) => void
    apiClient: ApiClient | null
    audioHash: string
    onTimeUpdate: (time: number) => void
    onHandlerToggle: (handler: string, enabled: boolean) => void
    isUpdatingHandlers: boolean
    onHandlerClick?: (handler: string) => void
    onFindReplace?: () => void
    onEditAll?: () => void
    onUnCorrectAll?: () => void
    onTimingOffset?: () => void
    timingOffsetMs?: number
    onUndo: () => void
    onRedo: () => void
    canUndo: boolean
    canRedo: boolean
    annotationsEnabled?: boolean
    onAnnotationsToggle?: (enabled: boolean) => void
}

export default function Header({
    isReadOnly,
    onFileLoad,
    data,
    onMetricClick,
    effectiveMode,
    onModeChange,
    apiClient,
    audioHash,
    onTimeUpdate,
    onHandlerToggle,
    isUpdatingHandlers,
    onHandlerClick,
    onFindReplace,
    onEditAll,
    onUnCorrectAll,
    onTimingOffset,
    timingOffsetMs = 0,
    onUndo,
    onRedo,
    canUndo,
    canRedo,
    annotationsEnabled = true,
    onAnnotationsToggle,
}: HeaderProps) {
    const theme = useTheme()
    const isMobile = useMediaQuery(theme.breakpoints.down('md'))

    // Get handlers with their correction counts
    const handlerCounts = data.corrections?.reduce((counts: Record<string, number>, correction) => {
        counts[correction.handler] = (counts[correction.handler] || 0) + 1
        return counts
    }, {}) || {}

    // Get available handlers from metadata
    const availableHandlers = data.metadata.available_handlers || []
    const enabledHandlers = new Set(data.metadata.enabled_handlers || [])
    
    // Check if agentic mode is active
    const isAgenticMode = availableHandlers.some((h: { id: string }) => h.id === 'AgenticCorrector')

    // Create a map of gap IDs to their corrections
    const gapCorrections = data.corrections.reduce((map: Record<string, number>, correction) => {
        // Find the gap that contains this correction's word_id
        const gap = data.gap_sequences.find(g =>
            g.transcribed_word_ids.includes(correction.word_id)
        )
        if (gap) {
            map[gap.id] = (map[gap.id] || 0) + 1
        }
        return map
    }, {})

    // Calculate metrics
    const correctedGapCount = Object.keys(gapCorrections).length
    const uncorrectedGapCount = data.gap_sequences.length - correctedGapCount

    const uncorrectedGaps = data.gap_sequences
        .filter(gap => !gapCorrections[gap.id] && gap.transcribed_word_ids.length > 0)
        .map(gap => {
            const firstWord = findWordById(data.corrected_segments, gap.transcribed_word_ids[0])
            return {
                position: firstWord?.id ?? '',
                length: gap.transcribed_word_ids.length
            }
        })

    // Calculate correction type counts
    const replacedCount = data.corrections.filter(c => !c.is_deletion && !c.split_total).length
    const addedCount = data.corrections.filter(c => c.split_total).length
    const deletedCount = data.corrections.filter(c => c.is_deletion).length

    return (
        <>
            {isReadOnly && (
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.8, color: 'text.secondary' }}>
                    <LockIcon sx={{ mr: 0.5 }} fontSize="small" />
                    <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
                        View Only Mode
                    </Typography>
                </Box>
            )}

            {isReadOnly && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                    <Button
                        variant="outlined"
                        size="small"
                        startIcon={<UploadFileIcon />}
                        onClick={onFileLoad}
                        fullWidth={isMobile}
                    >
                        Load File
                    </Button>
                </Box>
            )}

            <Box sx={{
                display: 'flex',
                gap: 1,
                mb: 1,
                flexDirection: isMobile ? 'column' : 'row',
                height: isMobile ? 'auto' : '140px',
                minHeight: isMobile ? 'auto' : '140px'
            }}>
                <Box sx={{
                    width: isMobile ? '100%' : '280px',
                    minWidth: isMobile ? '100%' : '280px',
                    position: 'relative',
                    height: isMobile ? 'auto' : '100%'
                }}>
                    {isAgenticMode ? (
                        <AgenticCorrectionMetrics
                            corrections={data.corrections || []}
                            onCategoryClick={(category) => {
                                // TODO: Implement category filtering/highlighting
                                console.log('Filter by category:', category)
                            }}
                            onConfidenceFilterClick={(filter) => {
                                // TODO: Implement confidence filtering
                                console.log('Filter by confidence:', filter)
                            }}
                        />
                    ) : (
                    <Paper sx={{
                        p: 0.8,
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column'
                    }}>
                        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5, fontSize: '0.7rem' }}>
                            Correction Handlers
                        </Typography>

                        <Box sx={{
                            flex: 1,
                            overflow: 'auto',
                            display: 'flex',
                            flexDirection: 'column'
                        }}>
                            {availableHandlers.map(handler => (
                                <Box key={handler.id} sx={{ mb: 0.5 }}>
                                    <Tooltip
                                        title={handler.description}
                                        placement="right"
                                    >
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={enabledHandlers.has(handler.id)}
                                                    onChange={(e) => onHandlerToggle(handler.id, e.target.checked)}
                                                    size="small"
                                                    disabled={isUpdatingHandlers}
                                                />
                                            }
                                            label={`${handler.name} (${handlerCounts[handler.id] || 0})`}
                                            onClick={(e) => {
                                                if ((e.target as HTMLElement).tagName !== 'INPUT') {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    onHandlerClick?.(handler.id);
                                                }
                                            }}
                                            sx={{
                                                ml: 0,
                                                py: 0,
                                                my: 0,
                                                minHeight: '24px',
                                                '& .MuiFormControlLabel-label': {
                                                    fontSize: '0.7rem',
                                                    cursor: 'pointer',
                                                    lineHeight: 1.2
                                                }
                                            }}
                                        />
                                    </Tooltip>
                                </Box>
                            ))}
                        </Box>
                    </Paper>
                    )}
                </Box>
                <Box sx={{ flex: 1, height: '100%' }}>
                    <CorrectionMetrics
                        // Anchor metrics
                        anchorCount={data.metadata.anchor_sequences_count}
                        multiSourceAnchors={data.anchor_sequences?.filter(anchor =>
                            anchor?.reference_word_ids &&
                            Object.keys(anchor.reference_word_ids).length > 1
                        ).length ?? 0}
                        anchorWordCount={data.anchor_sequences?.reduce((sum, anchor) =>
                            sum + (anchor.transcribed_word_ids?.length || 0), 0) ?? 0}
                        // Updated gap metrics
                        correctedGapCount={correctedGapCount}
                        uncorrectedGapCount={uncorrectedGapCount}
                        uncorrectedGaps={uncorrectedGaps}
                        // Updated correction type counts
                        replacedCount={replacedCount}
                        addedCount={addedCount}
                        deletedCount={deletedCount}
                        onMetricClick={onMetricClick}
                        totalWords={data.metadata.total_words}
                    />
                </Box>
            </Box>

            <Paper sx={{ p: 0.8, mb: 1 }}>
                <Box sx={{
                    display: 'flex',
                    flexDirection: isMobile ? 'column' : 'row',
                    gap: 1,
                    alignItems: isMobile ? 'flex-start' : 'center',
                    justifyContent: 'space-between',
                    width: '100%'
                }}>
                    <Box sx={{
                        display: 'flex',
                        gap: 0.5,
                        flexDirection: 'row',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        minHeight: '44px'
                    }}>
                        <ModeSelector
                            effectiveMode={effectiveMode}
                            onChange={onModeChange}
                        />
                        {!isReadOnly && (
                            <Box sx={{ display: 'flex', height: '44px', alignItems: 'center' }}>
                                <Tooltip title="Undo">
                                    <span>
                                        <IconButton
                                            size="small"
                                            onClick={onUndo}
                                            disabled={!canUndo}
                                            sx={{
                                                border: `1px solid ${theme.palette.divider}`,
                                                borderRadius: '4px',
                                                mx: 0.25,
                                                height: '44px',
                                                width: '44px'
                                            }}
                                        >
                                            <UndoIcon fontSize="small" />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title="Redo">
                                    <span>
                                        <IconButton
                                            size="small"
                                            onClick={onRedo}
                                            disabled={!canRedo}
                                            sx={{
                                                border: `1px solid ${theme.palette.divider}`,
                                                borderRadius: '4px',
                                                mx: 0.25,
                                                height: '44px',
                                                width: '44px'
                                            }}
                                        >
                                            <RedoIcon fontSize="small" />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Box>
                        )}
                        {!isReadOnly && (
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={onFindReplace}
                                startIcon={<FindReplaceIcon />}
                                sx={{ minWidth: 'fit-content', height: '32px' }}
                            >
                                Find/Replace
                            </Button>
                        )}
                        {!isReadOnly && onEditAll && (
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={onEditAll}
                                startIcon={<EditIcon />}
                                sx={{ minWidth: 'fit-content', height: '32px' }}
                            >
                                Edit All
                            </Button>
                        )}
                        {!isReadOnly && onUnCorrectAll && (
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={onUnCorrectAll}
                                startIcon={<RestoreIcon />}
                                sx={{ minWidth: 'fit-content', height: '32px' }}
                            >
                                Un-Correct All
                            </Button>
                        )}
                        {!isReadOnly && onTimingOffset && (
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={onTimingOffset}
                                    startIcon={<TimerIcon />}
                                    color={timingOffsetMs !== 0 ? "secondary" : "primary"}
                                    sx={{ minWidth: 'fit-content', height: '32px' }}
                                >
                                    Timing Offset
                                </Button>
                                {timingOffsetMs !== 0 && (
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            ml: 1,
                                            fontWeight: 'bold',
                                            color: theme.palette.secondary.main
                                        }}
                                    >
                                        {timingOffsetMs > 0 ? '+' : ''}{timingOffsetMs}ms
                                    </Typography>
                                )}
                            </Box>
                        )}
                        {!isReadOnly && onAnnotationsToggle && (
                            <Tooltip title={annotationsEnabled
                                ? "Click to disable annotation prompts when editing"
                                : "Click to enable annotation prompts when editing"
                            }>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => onAnnotationsToggle(!annotationsEnabled)}
                                    startIcon={<RateReviewIcon />}
                                    color={annotationsEnabled ? "primary" : "inherit"}
                                    sx={{ minWidth: 'fit-content', height: '32px' }}
                                >
                                    {annotationsEnabled ? "Feedback On" : "Feedback Off"}
                                </Button>
                            </Tooltip>
                        )}
                        <AudioPlayer
                            apiClient={apiClient}
                            onTimeUpdate={onTimeUpdate}
                            audioHash={audioHash}
                        />
                    </Box>
                </Box>
            </Paper>
        </>
    )
} 