import { Box, Button, Typography, useMediaQuery, useTheme } from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import MergeIcon from '@mui/icons-material/CallMerge'
import CallSplitIcon from '@mui/icons-material/CallSplit'
import { SxProps, Theme } from '@mui/material/styles'

interface WordDividerProps {
    onAddWord: () => void
    onMergeWords?: () => void
    onAddSegmentBefore?: () => void
    onAddSegmentAfter?: () => void
    onSplitSegment?: () => void
    onMergeSegment?: () => void
    canMerge?: boolean
    isFirst?: boolean
    isLast?: boolean
    sx?: SxProps<Theme>
}

const buttonTextStyle = {
    color: 'text.secondary', // Use theme color for proper light/dark mode support
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    fontWeight: 400,
    fontSize: '0.7rem',
    lineHeight: '1.4375em',
    textTransform: 'none'
}

const mobileButtonTextStyle = {
    ...buttonTextStyle,
    fontSize: '0.6rem'
}

const buttonBaseStyle = {
    minHeight: 0,
    padding: '2px 8px',
    '& .MuiButton-startIcon': {
        marginRight: 0.5
    },
    '& .MuiSvgIcon-root': {
        fontSize: '1.2rem'
    }
}

const mobileButtonBaseStyle = {
    ...buttonBaseStyle,
    padding: '2px 4px',
    '& .MuiButton-startIcon': {
        marginRight: 0.25
    },
    '& .MuiSvgIcon-root': {
        fontSize: '1rem'
    }
}

export default function WordDivider({
    onAddWord,
    onMergeWords,
    onAddSegmentBefore,
    onAddSegmentAfter,
    onSplitSegment,
    onMergeSegment,
    canMerge = false,
    isFirst = false,
    isLast = false,
    sx = {}
}: WordDividerProps) {
    const theme = useTheme()
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

    const activeButtonStyle = isMobile ? mobileButtonBaseStyle : buttonBaseStyle
    const activeTextStyle = isMobile ? mobileButtonTextStyle : buttonTextStyle

    return (
        <Box
            sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: isMobile ? 'flex-end' : 'center',
                height: 'auto',
                minHeight: '20px',
                my: isMobile ? 0 : -0.5,
                width: isMobile ? '100%' : '50%',
                bgcolor: 'background.paper',
                ...sx
            }}
        >
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: isMobile ? 0.5 : 1,
                flexWrap: 'wrap',
                justifyContent: isMobile ? 'flex-end' : 'center',
                bgcolor: 'background.paper',
                padding: isMobile ? '0 4px' : '0 8px',
                zIndex: 1
            }}>
                <Button
                    onClick={onAddWord}
                    title="Add Word"
                    size="small"
                    startIcon={<AddIcon />}
                    sx={{
                        ...activeButtonStyle,
                        color: 'primary.main',
                    }}
                >
                    <Typography sx={activeTextStyle}>
                        {isMobile ? '+Word' : 'Add Word'}
                    </Typography>
                </Button>
                {isFirst && onAddSegmentBefore && onMergeSegment && (
                    <>
                        <Button
                            onClick={onAddSegmentBefore}
                            title="Add Segment"
                            size="small"
                            startIcon={<AddIcon sx={{ transform: 'rotate(90deg)' }} />}
                            sx={{
                                ...activeButtonStyle,
                                color: 'success.main',
                            }}
                        >
                            <Typography sx={activeTextStyle}>
                                {isMobile ? '+Seg' : 'Add Segment'}
                            </Typography>
                        </Button>
                        <Button
                            onClick={onMergeSegment}
                            title="Merge with Previous Segment"
                            size="small"
                            startIcon={<MergeIcon sx={{ transform: 'rotate(90deg)' }} />}
                            sx={{
                                ...activeButtonStyle,
                                color: 'warning.main',
                            }}
                        >
                            <Typography sx={activeTextStyle}>
                                {isMobile ? 'Merge' : 'Merge Segment'}
                            </Typography>
                        </Button>
                    </>
                )}
                {onMergeWords && !isLast && (
                    <Button
                        onClick={onMergeWords}
                        title="Merge Words"
                        size="small"
                        startIcon={<MergeIcon sx={{ transform: 'rotate(90deg)' }} />}
                        disabled={!canMerge}
                        sx={{
                            ...activeButtonStyle,
                            color: 'primary.main',
                        }}
                    >
                        <Typography sx={activeTextStyle}>
                            {isMobile ? 'Merge' : 'Merge Words'}
                        </Typography>
                    </Button>
                )}
                {onSplitSegment && !isLast && (
                    <Button
                        onClick={onSplitSegment}
                        title="Split Segment"
                        size="small"
                        startIcon={<CallSplitIcon sx={{ transform: 'rotate(90deg)' }} />}
                        sx={{
                            ...activeButtonStyle,
                            color: 'warning.main',
                        }}
                    >
                        <Typography sx={activeTextStyle}>
                            {isMobile ? 'Split' : 'Split Segment'}
                        </Typography>
                    </Button>
                )}
                {isLast && onAddSegmentAfter && onMergeSegment && (
                    <>
                        <Button
                            onClick={onAddSegmentAfter}
                            title="Add Segment"
                            size="small"
                            startIcon={<AddIcon sx={{ transform: 'rotate(90deg)' }} />}
                            sx={{
                                ...activeButtonStyle,
                                color: 'success.main',
                            }}
                        >
                            <Typography sx={activeTextStyle}>
                                {isMobile ? '+Seg' : 'Add Segment'}
                            </Typography>
                        </Button>
                        <Button
                            onClick={onMergeSegment}
                            title="Merge with Next Segment"
                            size="small"
                            startIcon={<MergeIcon sx={{ transform: 'rotate(90deg)' }} />}
                            sx={{
                                ...activeButtonStyle,
                                color: 'warning.main',
                            }}
                        >
                            <Typography sx={activeTextStyle}>
                                {isMobile ? 'Merge' : 'Merge Segment'}
                            </Typography>
                        </Button>
                    </>
                )}
            </Box>
        </Box>
    )
} 