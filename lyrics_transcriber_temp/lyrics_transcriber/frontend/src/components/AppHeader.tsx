import { Box, IconButton, Tooltip, Typography, useTheme } from '@mui/material'
import { Sun, Moon } from 'lucide-react'

interface AppHeaderProps {
    isDarkMode?: boolean
    onToggleTheme?: () => void
}

export default function AppHeader({ isDarkMode = true, onToggleTheme }: AppHeaderProps) {
    const theme = useTheme()

    return (
        <Box
            component="header"
            sx={{
                borderBottom: `1px solid ${theme.palette.divider}`,
                backgroundColor: theme.palette.background.paper,
                backdropFilter: 'blur(8px)',
                position: 'sticky',
                top: 0,
                zIndex: 1100,
                px: 2,
                py: 1.5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}
        >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <img src="/nomad-karaoke-logo.svg" alt="Nomad Karaoke" style={{ height: 40 }} />
                <Typography
                    variant="h6"
                    sx={{
                        fontWeight: 'bold',
                        color: theme.palette.text.primary,
                        fontSize: '1.1rem',
                        lineHeight: 1,
                        m: 0,
                    }}
                >
                    Lyrics Transcription Review
                </Typography>
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {onToggleTheme && (
                    <Tooltip title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
                        <IconButton
                            onClick={onToggleTheme}
                            sx={{
                                color: theme.palette.text.secondary,
                                '&:hover': {
                                    color: theme.palette.text.primary,
                                    backgroundColor: theme.palette.action.hover,
                                },
                            }}
                        >
                            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                        </IconButton>
                    </Tooltip>
                )}
            </Box>
        </Box>
    )
}
