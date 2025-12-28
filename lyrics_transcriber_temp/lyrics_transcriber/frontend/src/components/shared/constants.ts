import { keyframes } from '@mui/system'

// Dark theme colors matching karaoke-gen globals.css
export const COLORS = {
    anchor: 'rgba(59, 130, 246, 0.25)', // Blue tint for dark mode
    corrected: 'rgba(34, 197, 94, 0.25)', // Green tint for dark mode
    uncorrectedGap: 'rgba(249, 115, 22, 0.25)', // Orange tint for dark mode
    highlighted: 'rgba(251, 191, 36, 0.4)',  // Amber highlight for dark mode
    playing: '#3b82f6', // Blue-500
    // Text colors (matching karaoke-gen)
    textPrimary: '#e5e5e5', // matches karaoke-gen --text
    textSecondary: '#888888', // matches karaoke-gen --text-muted
    textMuted: '#666666',
    // Background colors (matching karaoke-gen globals.css)
    background: '#0f0f0f', // matches karaoke-gen --bg
    backgroundPaper: '#1a1a1a', // matches karaoke-gen --card
    backgroundElevated: '#252525', // matches karaoke-gen --secondary
    border: '#2a2a2a', // matches karaoke-gen --card-border
} as const

export const flashAnimation = keyframes`
  0%, 100% { 
    opacity: 1;
    background-color: inherit;
  }
  50% { 
    opacity: 0.6;
    background-color: ${COLORS.highlighted};
  }
` 