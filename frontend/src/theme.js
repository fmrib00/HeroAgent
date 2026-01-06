import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  typography: {
    // Reduce all font sizes by approximately 20%
    fontSize: 12, // Base font size
    h1: {
      fontSize: '1.8rem', // Reduced from 2.125rem
    },
    h2: {
      fontSize: '1.5rem', // Reduced from 1.5rem
    },
    h3: {
      fontSize: '1.3rem', // Reduced from 1.25rem
    },
    h4: {
      fontSize: '1.1rem', // Reduced from 1.125rem
    },
    h5: {
      fontSize: '1rem', // Reduced from 1rem
    },
    h6: {
      fontSize: '0.9rem', // Reduced from 1rem
    },
    subtitle1: {
      fontSize: '0.9rem', // Reduced from 1rem
    },
    subtitle2: {
      fontSize: '0.8rem', // Reduced from 0.875rem
    },
    body1: {
      fontSize: '0.85rem', // Reduced from 1rem
    },
    body2: {
      fontSize: '0.8rem', // Reduced from 0.875rem
    },
    button: {
      fontSize: '0.8rem', // Reduced from 0.875rem
    },
    caption: {
      fontSize: '0.7rem', // Reduced from 0.75rem
    },
    overline: {
      fontSize: '0.65rem', // Reduced from 0.75rem
    },
  },
  components: {
    // Override MUI component default font sizes
    MuiButton: {
      styleOverrides: {
        root: {
          fontSize: '0.8rem',
        },
      },
    },
    MuiTypography: {
      styleOverrides: {
        root: {
          fontSize: 'inherit',
        },
      },
    },
    MuiListItemText: {
      styleOverrides: {
        primary: {
          fontSize: '0.85rem',
        },
        secondary: {
          fontSize: '0.75rem',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          fontSize: '0.75rem',
        },
      },
    },
  },
});

export default theme;
