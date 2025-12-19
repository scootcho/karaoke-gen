import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    IconButton,
    Box,
    Button,
    Typography,
    Paper
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import ContentPasteIcon from '@mui/icons-material/ContentPaste'
import SyncIcon from '@mui/icons-material/Sync'

interface ModeSelectionModalProps {
    open: boolean
    onClose: () => void
    onSelectReplace: () => void  // Goes to paste phase for replacing all lyrics
    onSelectResync: () => void   // Goes directly to sync view with existing lyrics
    hasExistingLyrics: boolean   // Whether there are existing lyrics to re-sync
}

export default function ModeSelectionModal({
    open,
    onClose,
    onSelectReplace,
    onSelectResync,
    hasExistingLyrics
}: ModeSelectionModalProps) {
    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="sm"
            fullWidth
        >
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ flex: 1 }}>
                    Edit All Lyrics
                </Box>
                <IconButton onClick={onClose} sx={{ ml: 'auto' }}>
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent dividers>
                <Typography variant="body1" sx={{ mb: 3 }}>
                    Choose how you want to edit the lyrics:
                </Typography>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {/* Re-sync Existing option - only show if there are existing lyrics */}
                    {hasExistingLyrics && (
                        <Paper
                            sx={{
                                p: 2,
                                cursor: 'pointer',
                                border: 2,
                                borderColor: 'primary.main',
                                '&:hover': {
                                    bgcolor: 'action.hover',
                                    borderColor: 'primary.dark'
                                }
                            }}
                            onClick={onSelectResync}
                        >
                            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                                <SyncIcon color="primary" sx={{ fontSize: 40, mt: 0.5 }} />
                                <Box>
                                    <Typography variant="h6" color="primary">
                                        Re-sync Existing Lyrics
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Keep the current lyrics text and fix timing issues.
                                        Use this when lyrics are correct but timing has drifted,
                                        especially in the second half of the song.
                                    </Typography>
                                    <Typography variant="caption" color="success.main" sx={{ mt: 1, display: 'block' }}>
                                        Recommended for fixing timing drift
                                    </Typography>
                                </Box>
                            </Box>
                        </Paper>
                    )}

                    {/* Replace All option */}
                    <Paper
                        sx={{
                            p: 2,
                            cursor: 'pointer',
                            border: 1,
                            borderColor: 'divider',
                            '&:hover': {
                                bgcolor: 'action.hover',
                                borderColor: 'text.secondary'
                            }
                        }}
                        onClick={onSelectReplace}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                            <ContentPasteIcon sx={{ fontSize: 40, mt: 0.5, color: 'text.secondary' }} />
                            <Box>
                                <Typography variant="h6">
                                    Replace All Lyrics
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Paste completely new lyrics from clipboard and manually
                                    sync timing for all words from scratch.
                                </Typography>
                                <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: 'block' }}>
                                    All existing timing data will be lost
                                </Typography>
                            </Box>
                        </Box>
                    </Paper>
                </Box>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} color="inherit">
                    Cancel
                </Button>
            </DialogActions>
        </Dialog>
    )
}
