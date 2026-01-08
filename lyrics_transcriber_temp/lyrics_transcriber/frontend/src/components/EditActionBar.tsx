import { Box, Button, useMediaQuery, useTheme } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import RestoreIcon from '@mui/icons-material/RestoreFromTrash'
import HistoryIcon from '@mui/icons-material/History'
import { LyricsSegment } from '../types'

interface EditActionBarProps {
    onReset: () => void
    onRevertToOriginal?: () => void
    onDelete?: () => void
    onClose: () => void
    onSave: () => void
    editedSegment: LyricsSegment | null
    originalTranscribedSegment?: LyricsSegment | null
    isGlobal?: boolean
}

export default function EditActionBar({
    onReset,
    onRevertToOriginal,
    onDelete,
    onClose,
    onSave,
    editedSegment,
    originalTranscribedSegment,
    isGlobal = false
}: EditActionBarProps) {
    const theme = useTheme()
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            alignItems: isMobile ? 'stretch' : 'center',
            gap: 1,
            width: '100%'
        }}>
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                flexWrap: 'wrap',
                justifyContent: isMobile ? 'center' : 'flex-start'
            }}>
                <Button
                    startIcon={<RestoreIcon />}
                    onClick={onReset}
                    color="warning"
                    size={isMobile ? 'small' : 'medium'}
                >
                    Reset
                </Button>
                {originalTranscribedSegment && (
                    <Button
                        onClick={onRevertToOriginal}
                        startIcon={<HistoryIcon />}
                        size={isMobile ? 'small' : 'medium'}
                    >
                        Un-Correct
                    </Button>
                )}
                {!isGlobal && onDelete && (
                    <Button
                        startIcon={<DeleteIcon />}
                        onClick={onDelete}
                        color="error"
                        size={isMobile ? 'small' : 'medium'}
                    >
                        Delete Segment
                    </Button>
                )}
            </Box>
            <Box sx={{
                ml: isMobile ? 0 : 'auto',
                display: 'flex',
                gap: 1,
                justifyContent: isMobile ? 'center' : 'flex-end'
            }}>
                <Button onClick={onClose} size={isMobile ? 'small' : 'medium'}>
                    Cancel
                </Button>
                <Button
                    onClick={onSave}
                    variant="contained"
                    disabled={!editedSegment || editedSegment.words.length === 0}
                    size={isMobile ? 'small' : 'medium'}
                >
                    Save
                </Button>
            </Box>
        </Box>
    )
} 