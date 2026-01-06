// Cache for IP address (fetch once and reuse)
let cachedIpAddress = null;
let ipFetchPromise = null;

/**
 * Get user email from localStorage
 */
const getUserEmail = () => {
  try {
    return localStorage.getItem('hero_email') || null;
  } catch (e) {
    return null;
  }
};

/**
 * Fetch IP address from a service (cached after first fetch)
 */
const getIpAddress = async () => {
  // Return cached IP if available
  if (cachedIpAddress) {
    return cachedIpAddress;
  }

  // Return existing promise if fetch is in progress
  if (ipFetchPromise) {
    return ipFetchPromise;
  }

  // Fetch IP address
  ipFetchPromise = fetch('https://api.ipify.org?format=json')
    .then(response => response.json())
    .then(data => {
      cachedIpAddress = data.ip;
      return cachedIpAddress;
    })
    .catch(error => {
      console.warn('[Logger] Failed to fetch IP address:', error);
      cachedIpAddress = 'unknown';
      return 'unknown';
    })
    .finally(() => {
      ipFetchPromise = null;
    });

  return ipFetchPromise;
};

/**
 * Get common log metadata (user email, IP, etc.)
 * IP is fetched asynchronously and cached, so we use cached value or 'fetching'
 */
const getCommonLogData = () => {
  const userEmail = getUserEmail();

  // Start IP fetch if not already cached (non-blocking)
  if (!cachedIpAddress && !ipFetchPromise) {
    getIpAddress().catch(() => {
      // Silently handle errors, IP will be 'unknown' if fetch fails
    });
  }

  return {
    userEmail,
    ipAddress: cachedIpAddress || 'fetching',
  };
};

/**
 * Console-based logger utility
 */
export const logger = {
  /**
   * Log info messages
   */
  info: (message, context = {}) => {
    const commonData = getCommonLogData();
    // Extract username from context or commonData
    const username = context.userId || context.userEmail || commonData.userEmail || 'unknown';
    const ipAddress = commonData.ipAddress !== 'fetching' ? commonData.ipAddress : 'unknown';

    // Check if message already contains username (email pattern or username at start)
    const emailPattern = /^[^\s:]+@[^\s:]+/;
    const messageHasUsername = emailPattern.test(message) || message.startsWith(username + ':');

    // Format message: if username already in message, just add IP; otherwise add both
    let enhancedMessage;
    if (messageHasUsername) {
      // Message already has username, just add IP address after it
      enhancedMessage = message.replace(/^([^\s:]+@[^\s:]+|[\w.]+):\s*/, `$1 [${ipAddress}]: `);
    } else {
      // Add both username and IP address
      enhancedMessage = `${username} [${ipAddress}]: ${message}`;
    }

    console.info('[INFO]', enhancedMessage, context);
  },

  /**
   * Log warning messages
   */
  warn: (message, context = {}) => {
    const commonData = getCommonLogData();
    // Extract username from context or commonData
    const username = context.userId || context.userEmail || commonData.userEmail || 'unknown';
    const ipAddress = commonData.ipAddress !== 'fetching' ? commonData.ipAddress : 'unknown';

    // Check if message already contains username (email pattern or username at start)
    const emailPattern = /^[^\s:]+@[^\s:]+/;
    const messageHasUsername = emailPattern.test(message) || message.startsWith(username + ':');

    // Format message: if username already in message, just add IP; otherwise add both
    let enhancedMessage;
    if (messageHasUsername) {
      // Message already has username, just add IP address after it
      enhancedMessage = message.replace(/^([^\s:]+@[^\s:]+|[\w.]+):\s*/, `$1 [${ipAddress}]: `);
    } else {
      // Add both username and IP address
      enhancedMessage = `${username} [${ipAddress}]: ${message}`;
    }

    console.warn('[WARN]', enhancedMessage, context);
  },

  /**
   * Log error messages
   */
  error: (message, error = null, context = {}) => {
    const commonData = getCommonLogData();
    // Extract username from context or commonData
    const username = context.userId || context.userEmail || commonData.userEmail || 'unknown';
    const ipAddress = commonData.ipAddress !== 'fetching' ? commonData.ipAddress : 'unknown';

    // Check if message already contains username (email pattern or username at start)
    const emailPattern = /^[^\s:]+@[^\s:]+/;
    const messageHasUsername = emailPattern.test(message) || message.startsWith(username + ':');

    // Format message: if username already in message, just add IP; otherwise add both
    let enhancedMessage;
    if (messageHasUsername) {
      // Message already has username, just add IP address after it
      enhancedMessage = message.replace(/^([^\s:]+@[^\s:]+|[\w.]+):\s*/, `$1 [${ipAddress}]: `);
    } else {
      // Add both username and IP address
      enhancedMessage = `${username} [${ipAddress}]: ${message}`;
    }

    // Add error details if provided
    const errorDetails = error ? {
      name: error?.name,
      message: error?.message,
      stack: error?.stack,
      ...(error?.response && {
        response: {
          status: error.response.status,
          statusText: error.response.statusText,
          data: error.response.data,
        },
      }),
    } : {};

    console.error('[ERROR]', enhancedMessage, errorDetails, context);
  },

  /**
   * Log debug messages (only in development)
   */
  debug: (message, context = {}) => {
    if (process.env.NODE_ENV === 'development') {
      const commonData = getCommonLogData();
      // Extract username from context or commonData
      const username = context.userId || context.userEmail || commonData.userEmail || 'unknown';
      const ipAddress = commonData.ipAddress !== 'fetching' ? commonData.ipAddress : 'unknown';

      // Check if message already contains username (email pattern or username at start)
      const emailPattern = /^[^\s:]+@[^\s:]+/;
      const messageHasUsername = emailPattern.test(message) || message.startsWith(username + ':');

      // Format message: if username already in message, just add IP; otherwise add both
      let enhancedMessage;
      if (messageHasUsername) {
        // Message already has username, just add IP address after it
        enhancedMessage = message.replace(/^([^\s:]+@[^\s:]+|[\w.]+):\s*/, `$1 [${ipAddress}]: `);
      } else {
        // Add both username and IP address
        enhancedMessage = `${username} [${ipAddress}]: ${message}`;
      }

      console.debug('[DEBUG]', enhancedMessage, context);
    }
  },
};

// Initialize IP address fetch on module load (non-blocking)
if (typeof window !== 'undefined') {
  getIpAddress().catch(() => {
    // Silently handle errors
  });
}

// Log app initialization
logger.info('Console logger initialized', {
  environment: process.env.NODE_ENV,
  apiUrl: process.env.REACT_APP_API_URL,
  timestamp: new Date().toISOString(),
  userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
  url: typeof window !== 'undefined' ? window.location.href : 'unknown',
});

export default logger;
