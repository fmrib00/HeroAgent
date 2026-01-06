# Frontend Application Structure

This React application has been refactored into a modular, component-based architecture for better maintainability and code organization.

## Directory Structure

```
src/
├── components/          # React components
│   ├── Login.js         # Authentication component
│   ├── AccountList.js   # Account management sidebar
│   ├── OutputWindow.js  # Main output display area
│   ├── AddAccountDialog.js # Add new account dialog
│   ├── SettingsDialog.js   # Account settings dialog
│   ├── LogViewerDialog.js  # Log file viewer dialog
│   └── InfoDialogs.js      # Information dialogs (missing settings, etc.)
├── hooks/              # Custom React hooks
│   └── useStreaming.js # Streaming functionality hook
├── utils/              # Utility functions and constants
│   ├── api.js          # API configuration and functions
│   ├── constants.js    # Application constants
│   └── cookieUtils.js  # Cookie parsing utilities
├── App.js              # Main application component
└── index.js            # Application entry point
```

## Components

### Login.js
Handles user authentication and registration functionality.

### AccountList.js
Manages the account selection sidebar with checkboxes and action buttons.

### OutputWindow.js
Displays the main output area and action buttons for various operations.

### AddAccountDialog.js
Dialog for adding new accounts with cookie input and validation.

### SettingsDialog.js
Dialog for configuring account settings and hall preferences.

### LogViewerDialog.js
Dialog for viewing and managing log files.

### InfoDialogs.js
Collection of information dialogs for displaying warnings and errors.

## Hooks

### useStreaming.js
Custom hook that manages streaming functionality for real-time data updates, including:
- EventSource cleanup
- Resume streaming (active sessions or latest logs)
- Hall combat streaming

## Utils

### api.js
Centralized API configuration and functions:
- API URL and key configuration
- Axios instance with API key
- All API endpoint functions

### constants.js
Application constants:
- Hall names
- Cookie help text

### cookieUtils.js
Cookie-related utility functions:
- Parse cookie strings
- Compose cookie strings
- Clean cookie values

## Benefits of This Structure

1. **Separation of Concerns**: Each component has a single responsibility
2. **Reusability**: Components can be easily reused and tested
3. **Maintainability**: Smaller files are easier to understand and modify
4. **Testability**: Individual components can be tested in isolation
5. **Scalability**: New features can be added as new components
6. **Code Organization**: Related functionality is grouped together

## Usage

The main `App.js` component orchestrates all the other components and manages the overall application state. It passes down props to child components and handles the communication between them. 