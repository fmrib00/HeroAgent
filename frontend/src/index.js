import React from 'react';
import ReactDOM from 'react-dom/client';
import { GoogleOAuthProvider } from '@react-oauth/google';
import './index.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { logger } from './utils/logger';

// Get Google OAuth Client ID from environment variable
// Use a placeholder if not configured - the Login component will hide the button if not configured
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || '';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <ErrorBoundary>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID || 'placeholder'}>
      <App />
    </GoogleOAuthProvider>
  </ErrorBoundary>
);

// Log app initialization
logger.info('Application started', {
  environment: process.env.NODE_ENV,
  apiUrl: process.env.REACT_APP_API_URL,
  timestamp: new Date().toISOString(),
});

