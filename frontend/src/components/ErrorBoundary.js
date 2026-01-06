import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { logger } from '../utils/logger';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error
    logger.error('React Error Boundary caught an error', error, {
      componentStack: errorInfo.componentStack,
      errorBoundary: true,
    });

    this.setState({
      error,
      errorInfo,
    });
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            p: 3,
            bgcolor: '#f5f5f5',
          }}
        >
          <Typography variant="h4" sx={{ mb: 2, color: 'error.main' }}>
            出现错误
          </Typography>
          <Typography variant="body1" sx={{ mb: 2, textAlign: 'center', maxWidth: 600 }}>
            应用程序遇到了意外错误。错误已记录，请刷新页面重试。
          </Typography>
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <Box
              sx={{
                mt: 2,
                p: 2,
                bgcolor: '#fff',
                borderRadius: 1,
                maxWidth: 800,
                maxHeight: 400,
                overflow: 'auto',
              }}
            >
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                错误详情 (仅开发环境):
              </Typography>
              <Typography
                variant="body2"
                component="pre"
                sx={{
                  fontFamily: 'monospace',
                  fontSize: '0.75rem',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack}
              </Typography>
            </Box>
          )}
          <Button
            variant="contained"
            color="primary"
            onClick={this.handleReload}
            sx={{ mt: 3 }}
          >
            刷新页面
          </Button>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
