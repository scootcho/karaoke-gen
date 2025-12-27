import { createTheme, Theme } from '@mui/material/styles';

// Dark theme colors (matching karaoke-gen's globals.css)
const darkColors = {
  background: {
    default: '#0f0f0f',
    paper: '#1a1a1a',
    elevated: '#252525',
  },
  text: {
    primary: '#f8fafc',
    secondary: '#94a3b8',
    disabled: '#64748b',
  },
  divider: '#2a2a2a',
  action: {
    active: '#f8fafc',
    hover: 'rgba(248, 250, 252, 0.08)',
    selected: 'rgba(249, 115, 22, 0.16)',
    disabled: '#64748b',
    disabledBackground: 'rgba(100, 116, 139, 0.12)',
  },
};

// Light theme colors
const lightColors = {
  background: {
    default: '#f8fafc',
    paper: '#ffffff',
    elevated: '#f1f5f9',
  },
  text: {
    primary: '#1e293b',
    secondary: '#64748b',
    disabled: '#94a3b8',
  },
  divider: '#e2e8f0',
  action: {
    active: '#1e293b',
    hover: 'rgba(30, 41, 59, 0.08)',
    selected: 'rgba(249, 115, 22, 0.16)',
    disabled: '#94a3b8',
    disabledBackground: 'rgba(148, 163, 184, 0.12)',
  },
};

// Shared colors
const sharedColors = {
  primary: {
    main: '#f97316',
    light: '#fb923c',
    dark: '#ea580c',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#6366f1',
    light: '#818cf8',
    dark: '#4f46e5',
    contrastText: '#ffffff',
  },
  error: {
    main: '#ef4444',
    light: '#f87171',
    dark: '#dc2626',
  },
  warning: {
    main: '#f59e0b',
    light: '#fbbf24',
    dark: '#d97706',
  },
  success: {
    main: '#22c55e',
    light: '#4ade80',
    dark: '#16a34a',
  },
  info: {
    main: '#3b82f6',
    light: '#60a5fa',
    dark: '#2563eb',
  },
};

// Create theme based on mode
export function createAppTheme(mode: 'dark' | 'light'): Theme {
  const colors = mode === 'dark' ? darkColors : lightColors;

  return createTheme({
    palette: {
      mode,
      background: colors.background,
      text: colors.text,
      primary: sharedColors.primary,
      secondary: sharedColors.secondary,
      error: sharedColors.error,
      warning: sharedColors.warning,
      success: sharedColors.success,
      info: sharedColors.info,
      divider: colors.divider,
      action: colors.action,
    },
    typography: {
      fontFamily: '"Inter", "system-ui", "sans-serif"',
      fontSize: 14,
      h1: { fontSize: '2.5rem', fontWeight: 600, color: colors.text.primary },
      h2: { fontSize: '2rem', fontWeight: 600, color: colors.text.primary },
      h3: { fontSize: '1.5rem', fontWeight: 600, color: colors.text.primary },
      h4: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: colors.text.primary },
      h5: { fontSize: '1rem', fontWeight: 600, color: colors.text.primary },
      h6: { fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem', color: colors.text.primary },
      body1: { fontSize: '0.85rem', color: colors.text.primary },
      body2: { fontSize: '0.75rem', color: colors.text.secondary },
      button: { fontSize: '0.8rem', fontWeight: 500, textTransform: 'none' },
      caption: { fontSize: '0.7rem', color: colors.text.secondary },
    },
    shape: { borderRadius: 8 },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: colors.background.default,
            color: colors.text.primary,
            scrollbarColor: `${colors.background.elevated} ${colors.background.default}`,
            '&::-webkit-scrollbar': { width: '8px', height: '8px' },
            '&::-webkit-scrollbar-track': { background: colors.background.default },
            '&::-webkit-scrollbar-thumb': { background: colors.background.elevated, borderRadius: '4px' },
            '&::-webkit-scrollbar-thumb:hover': { background: mode === 'dark' ? '#475569' : '#94a3b8' },
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: { padding: '3px 10px', minHeight: '30px', borderRadius: '6px' },
          sizeSmall: { padding: '1px 6px', minHeight: '24px' },
          contained: { boxShadow: 'none', '&:hover': { boxShadow: 'none' } },
          containedPrimary: {
            backgroundColor: sharedColors.primary.main,
            '&:hover': { backgroundColor: sharedColors.primary.dark },
          },
          outlined: {
            borderColor: colors.divider,
            '&:hover': {
              borderColor: sharedColors.primary.main,
              backgroundColor: 'rgba(249, 115, 22, 0.08)',
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            padding: '4px',
            color: colors.text.secondary,
            '&:hover': { backgroundColor: colors.action.hover, color: colors.text.primary },
          },
          sizeSmall: { padding: '2px' },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiInputBase-root': { minHeight: '32px', backgroundColor: colors.background.default },
            '& .MuiOutlinedInput-root': {
              '& fieldset': { borderColor: colors.divider },
              '&:hover fieldset': { borderColor: colors.text.secondary },
              '&.Mui-focused fieldset': { borderColor: sharedColors.primary.main },
            },
          },
        },
      },
      MuiInputBase: {
        styleOverrides: {
          root: { color: colors.text.primary },
          input: { '&::placeholder': { color: colors.text.disabled, opacity: 1 } },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            padding: '8px',
            backgroundColor: colors.background.paper,
            backgroundImage: 'none',
            border: `1px solid ${colors.divider}`,
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: { root: { padding: '8px 12px', color: colors.text.primary } },
      },
      MuiDialogContent: {
        styleOverrides: { root: { padding: '6px 12px' } },
      },
      MuiDialogActions: {
        styleOverrides: { root: { padding: '6px 12px' } },
      },
      MuiPaper: {
        styleOverrides: {
          root: { padding: '8px', backgroundColor: colors.background.paper, backgroundImage: 'none' },
          outlined: { borderColor: colors.divider },
        },
      },
      MuiList: {
        styleOverrides: { root: { padding: '2px 0' } },
      },
      MuiListItem: {
        styleOverrides: { root: { padding: '2px 8px' } },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            '&:hover': { backgroundColor: colors.action.hover },
            '&.Mui-selected': {
              backgroundColor: colors.action.selected,
              '&:hover': { backgroundColor: 'rgba(249, 115, 22, 0.24)' },
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { padding: '4px 8px', borderBottomColor: colors.divider },
          head: { backgroundColor: colors.background.elevated, color: colors.text.primary, fontWeight: 600 },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: { '&:hover': { backgroundColor: mode === 'dark' ? 'rgba(248, 250, 252, 0.04)' : 'rgba(30, 41, 59, 0.04)' } },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            padding: '8px',
            backgroundColor: colors.background.paper,
            backgroundImage: 'none',
            border: `1px solid ${colors.divider}`,
          },
        },
      },
      MuiCardContent: {
        styleOverrides: { root: { padding: '8px', '&:last-child': { paddingBottom: '8px' } } },
      },
      MuiCardHeader: {
        styleOverrides: {
          root: { padding: '8px' },
          title: { color: colors.text.primary },
          subheader: { color: colors.text.secondary },
        },
      },
      MuiCardActions: {
        styleOverrides: { root: { padding: '4px 8px' } },
      },
      MuiChip: {
        styleOverrides: {
          root: { backgroundColor: colors.background.elevated, color: colors.text.primary, borderColor: colors.divider },
          filled: {
            '&.MuiChip-colorPrimary': { backgroundColor: sharedColors.primary.main, color: sharedColors.primary.contrastText },
          },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: '8px' },
          standardError: { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: sharedColors.error.light },
          standardWarning: { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: sharedColors.warning.light },
          standardSuccess: { backgroundColor: 'rgba(34, 197, 94, 0.15)', color: sharedColors.success.light },
          standardInfo: { backgroundColor: 'rgba(59, 130, 246, 0.15)', color: sharedColors.info.light },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: colors.background.elevated,
            color: colors.text.primary,
            border: `1px solid ${colors.divider}`,
            fontSize: '0.75rem',
          },
          arrow: { color: colors.background.elevated },
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: { backgroundColor: colors.background.paper, border: `1px solid ${colors.divider}` },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: {
            '&:hover': { backgroundColor: colors.action.hover },
            '&.Mui-selected': {
              backgroundColor: colors.action.selected,
              '&:hover': { backgroundColor: 'rgba(249, 115, 22, 0.24)' },
            },
          },
        },
      },
      MuiDivider: {
        styleOverrides: { root: { borderColor: colors.divider } },
      },
      MuiTabs: {
        styleOverrides: { indicator: { backgroundColor: sharedColors.primary.main } },
      },
      MuiTab: {
        styleOverrides: {
          root: { color: colors.text.secondary, '&.Mui-selected': { color: sharedColors.primary.main } },
        },
      },
      MuiSlider: {
        styleOverrides: {
          root: { color: sharedColors.primary.main },
          track: { backgroundColor: sharedColors.primary.main },
          rail: { backgroundColor: colors.background.elevated },
          thumb: { backgroundColor: sharedColors.primary.main },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .MuiSwitch-switchBase.Mui-checked': {
              color: sharedColors.primary.main,
              '& + .MuiSwitch-track': { backgroundColor: sharedColors.primary.main },
            },
          },
          track: { backgroundColor: colors.background.elevated },
        },
      },
      MuiCheckbox: {
        styleOverrides: {
          root: { color: colors.text.secondary, '&.Mui-checked': { color: sharedColors.primary.main } },
        },
      },
      MuiRadio: {
        styleOverrides: {
          root: { color: colors.text.secondary, '&.Mui-checked': { color: sharedColors.primary.main } },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { backgroundColor: colors.background.elevated, borderRadius: '4px' },
          bar: { backgroundColor: sharedColors.primary.main, borderRadius: '4px' },
        },
      },
      MuiCircularProgress: {
        styleOverrides: { root: { color: sharedColors.primary.main } },
      },
      MuiSelect: {
        styleOverrides: {
          select: { backgroundColor: colors.background.default },
          icon: { color: colors.text.secondary },
        },
      },
      MuiAccordion: {
        styleOverrides: {
          root: { backgroundColor: colors.background.paper, '&:before': { backgroundColor: colors.divider } },
        },
      },
      MuiAccordionSummary: {
        styleOverrides: { root: { '&:hover': { backgroundColor: colors.action.hover } } },
      },
      MuiBadge: {
        styleOverrides: { colorPrimary: { backgroundColor: sharedColors.primary.main } },
      },
      MuiAppBar: {
        styleOverrides: {
          root: { backgroundColor: colors.background.paper, backgroundImage: 'none', borderBottom: `1px solid ${colors.divider}` },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: { backgroundColor: colors.background.paper, backgroundImage: 'none', borderColor: colors.divider },
        },
      },
    },
    spacing: (factor: number) => `${0.6 * factor}rem`,
  });
}

// Default dark theme for backwards compatibility
const theme = createAppTheme('dark');
export default theme;
