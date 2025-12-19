import { memo, useMemo } from 'react'
import { Box, Typography } from '@mui/material'
import { Word } from '../../types'

interface UpcomingWordsBarProps {
    words: Word[]
    syncWordIndex: number
    isManualSyncing: boolean
    maxWordsToShow?: number
}

const UpcomingWordsBar = memo(function UpcomingWordsBar({
    words,
    syncWordIndex,
    isManualSyncing,
    maxWordsToShow = 20
}: UpcomingWordsBarProps) {
    // Get upcoming unsynced words
    const upcomingWords = useMemo(() => {
        if (!isManualSyncing || syncWordIndex < 0) return []
        
        return words
            .slice(syncWordIndex)
            .filter(w => w.start_time === null)
            .slice(0, maxWordsToShow)
    }, [words, syncWordIndex, isManualSyncing, maxWordsToShow])

    const totalRemaining = useMemo(() => {
        if (!isManualSyncing || syncWordIndex < 0) return 0
        return words.slice(syncWordIndex).filter(w => w.start_time === null).length
    }, [words, syncWordIndex, isManualSyncing])

    // Show empty placeholder when no upcoming words
    if (upcomingWords.length === 0) {
        return null
    }

    return (
        <Box sx={{ 
            height: 44, 
            bgcolor: 'grey.100',
            borderRadius: 1,
            display: 'flex',
            alignItems: 'center',
            px: 1,
            gap: 0.5,
            overflow: 'hidden',
            boxSizing: 'border-box'
        }}>
            {upcomingWords.map((word, index) => (
                <Box
                    key={word.id}
                    sx={{
                        px: 1,
                        py: 0.5,
                        borderRadius: 0.5,
                        bgcolor: index === 0 ? 'error.main' : 'grey.300',
                        color: index === 0 ? 'white' : 'text.primary',
                        fontWeight: index === 0 ? 'bold' : 'normal',
                        fontSize: '13px',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                        whiteSpace: 'nowrap',
                        border: index === 0 ? '2px solid' : 'none',
                        borderColor: 'error.dark'
                    }}
                >
                    {word.text}
                </Box>
            ))}
            
            {totalRemaining > maxWordsToShow && (
                <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                    +{totalRemaining - maxWordsToShow} more
                </Typography>
            )}
        </Box>
    )
})

export default UpcomingWordsBar
