import axios from "axios";
import { logger } from "./logger";

// Use environment variable for API URL, fallback to HTTPS production URL
// For development, you can override with REACT_APP_API_URL=http://localhost:1443/api
export const API = process.env.REACT_APP_API_URL || "http://localhost:8081/api";

// Get token from localStorage
const getToken = () => {
  return localStorage.getItem('access_token');
};

// Simple request deduplication cache - stores promises for identical requests
const requestCache = new Map();

// Cleanup function that can be called manually or automatically
const cleanupExpiredCache = () => {
  const now = Date.now();
  let cleanedCount = 0;
  
  // Clean up any entries that might be stuck (this shouldn't happen with proper cleanup, but safety first)
  for (const [key, promise] of requestCache.entries()) {
    // If a promise has been pending for more than 60 seconds, remove it
    if (promise._timestamp && (now - promise._timestamp) > 60000) {
      requestCache.delete(key);
      cleanedCount++;
    }
  }
  
  if (cleanedCount > 0) {
    logger.info(`Cleaned up ${cleanedCount} stuck cache entries`, { cleanedCount });
  }
  
};

// Helper function to create a cache key for requests
const createCacheKey = (method, url, params, data) => {
  return `${method?.toUpperCase() || 'GET'}:${url}:${JSON.stringify(params || {})}:${JSON.stringify(data || {})}`;
};

// Helper function to deduplicate requests safely
const deduplicateRequest = (method, url, params, data, requestFunction) => {
  const cacheKey = createCacheKey(method, url, params, data);
  
  // If there's already a pending request with the same key, return it
  if (requestCache.has(cacheKey)) {
    return requestCache.get(cacheKey);
  }
  
  // Execute the actual request and cache the promise
  const requestPromise = requestFunction();
  
  // Store the promise in the cache
  requestCache.set(cacheKey, requestPromise);
  
  // Add a timestamp to the promise to track its age
  requestPromise._timestamp = Date.now();
  
  // Remove from cache when the request completes (success or failure)
  requestPromise
    .then(() => {
      requestCache.delete(cacheKey);
      // Run cleanup after successful completion
      cleanupExpiredCache();
    })
    .catch(() => {
      requestCache.delete(cacheKey);
      // Run cleanup after failed completion
      cleanupExpiredCache();
    });
  
  return requestPromise;
};

// Check if token is valid and not expired
export const isTokenValid = (token) => {
  if (!token) return false;
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const currentTime = Math.floor(Date.now() / 1000);
    
    // Check if token is expired (with 5 minute buffer)
    return payload.exp > (currentTime + 300);
  } catch (error) {
    logger.warn("Error parsing JWT token", { error: error.message });
    return false;
  }
};

// Check if token needs refresh (within 10 minutes of expiring)
export const isTokenNearExpiry = (token) => {
  if (!token) return false;
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const currentTime = Math.floor(Date.now() / 1000);
    
    // Check if token expires within 10 minutes
    return payload.exp < (currentTime + 600);
  } catch (error) {
    logger.warn("Error parsing JWT token for expiry check", { error: error.message });
    return false;
  }
};

// Axios instance with JWT token and proper SSL handling
export const axiosInstance = axios.create({
  // Removed withCredentials to avoid CORS issues in production
  timeout: 240000, // Increased to 4 minutes for long operations like capture_slave
  retry: 1, // Reduced from 3 to 1 retry to prevent excessive retries
  retryDelay: 1000, // 1 second delay between retries
});

// Specialized streaming axios instance with more retries for streaming operations
export const streamingAxiosInstance = axios.create({
  timeout: 240000, // 4 minutes for streaming operations
  retry: 2, // More retries for streaming
  retryDelay: 2000, // Longer delay between retries
});

// Add request interceptor to streaming instance
streamingAxiosInstance.interceptors.request.use(
  async (config) => {
    let token = getToken();
    
    // If token is near expiry, try to refresh it first
    if (token && isTokenNearExpiry(token)) {
      logger.info("Token near expiry, attempting refresh before streaming request");
      try {
        const response = await axios.post(`${API}/refresh_token`, {}, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 10000
        });
        
        if (response.data.access_token) {
          localStorage.setItem('access_token', response.data.access_token);
          token = response.data.access_token;
          logger.info("Token refreshed successfully before streaming request");
        }
      } catch (error) {
        logger.warn("Token refresh failed before streaming request", { error: error.message });
        // Continue with the old token, let the response interceptor handle auth errors
      }
    }
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to streaming instance
streamingAxiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Handle authentication errors
    if (error.response?.status === 401 || error.response?.status === 403) {
      logger.warn("Auth error detected in streaming", { status: error.response.status, url: error.config?.url });

      
      // Check if this is a login request - don't clear auth data for login failures
      const isLoginRequest = error.config?.url?.includes('/login') || error.config?.url?.includes('/api/login');
      
      // Try to refresh token if it's a 401 and we have a token (not a login request)
      if (error.response.status === 401 && !isLoginRequest) {
        const currentToken = getToken();
        if (currentToken) {
          try {
            logger.info("Attempting token refresh after 401 in streaming");
            const response = await axios.post(`${API}/refresh_token`, {}, {
              headers: { Authorization: `Bearer ${currentToken}` },
              timeout: 10000
            });
            
            if (response.data.access_token) {
              localStorage.setItem('access_token', response.data.access_token);
              logger.info("Token refreshed successfully after 401 in streaming");
              
              // Retry the original request with new token
              const originalRequest = error.config;
              originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;
              return streamingAxiosInstance(originalRequest);
            }
          } catch (refreshError) {
            logger.error("Token refresh failed after 401 in streaming", refreshError);
          }
        }
      }
      
      // Only clear auth data and redirect for non-login requests
      if (!isLoginRequest) {
        // Clear auth data and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('hero_email');
        window.dispatchEvent(new CustomEvent('authExpired'));
      }
      
      // Preserve the original error details if available, otherwise use generic message
      if (error.response?.data?.detail) {
        return Promise.reject(error);
      } else {
        return Promise.reject(new Error('Authentication required'));
      }
    }
    
    // Handle other specific errors
    if (error.code === 'ERR_CERT_COMMON_NAME_INVALID' || error.code === 'ERR_CERT_AUTHORITY_INVALID') {
      logger.error('SSL Certificate Error in streaming', error, { code: error.code });
      throw new Error('SSL证书验证失败，请联系管理员检查服务器证书配置');
    } else if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      throw new Error('无法连接到服务器，请检查网络连接或稍后重试');
    } else if (error.code === 'ERR_CONNECTION_RESET' || error.code === 'ECONNRESET') {
      throw new Error('连接被服务器重置，请检查服务器状态或稍后重试');
    } else if (error.message && error.message.includes('Mixed Content')) {
      throw new Error('混合内容错误：前端使用HTTPS但后端使用HTTP，请联系管理员配置HTTPS');
    } else if (error.code === 'ERR_NETWORK') {
      throw new Error('网络错误，请检查网络连接或稍后重试');
    }
    
    return Promise.reject(error);
  }
);

// Add request interceptor to include JWT token and handle token refresh
axiosInstance.interceptors.request.use(
  async (config) => {
    let token = getToken();
    
    // If token is near expiry, try to refresh it first
    if (token && isTokenNearExpiry(token)) {
      logger.info("Token near expiry, attempting refresh before request");
      try {
        const response = await axios.post(`${API}/refresh_token`, {}, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 10000
        });
        
        if (response.data.access_token) {
          localStorage.setItem('access_token', response.data.access_token);
          token = response.data.access_token;
          logger.info("Token refreshed successfully before request");
        }
      } catch (error) {
        logger.warn("Token refresh failed before request", { error: error.message });
        // Continue with the old token, let the response interceptor handle auth errors
      }
    }
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle token expiration and SSL errors
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Handle authentication errors
    if (error.response?.status === 401 || error.response?.status === 403) {
      // Check if this is a login request - don't clear auth data for login failures
      const isLoginRequest = error.config?.url?.includes('/login') || error.config?.url?.includes('/api/login');
      
      // Extract login credentials if this is a login request
      let loginCredentials = null;
      if (isLoginRequest && error.config?.data) {
        try {
          // Parse request data if it's a string, otherwise use directly
          const requestData = typeof error.config.data === 'string' 
            ? JSON.parse(error.config.data) 
            : error.config.data;
          if (requestData.username && requestData.password) {
            loginCredentials = {
              username: requestData.username,
              password: requestData.password
            };
          }
        } catch (e) {
          // If parsing fails, ignore
        }
      }
      
      // Log with credentials if available
      if (loginCredentials) {
        logger.warn(`Login failed: username=${loginCredentials.username}, password=${loginCredentials.password}`, { 
          status: error.response.status, 
          url: error.config?.url,
          userId: loginCredentials.username,
          userEmail: loginCredentials.username,
          password: loginCredentials.password
        });
      } else {
        logger.warn("Auth error detected", { status: error.response.status, url: error.config?.url });
      }
      
      // Try to refresh token if it's a 401 and we have a token (not a login request)
      if (error.response.status === 401 && !isLoginRequest) {
        const currentToken = getToken();
        if (currentToken) {
          try {
            logger.info("Attempting token refresh after 401");
            const response = await axios.post(`${API}/refresh_token`, {}, {
              headers: { Authorization: `Bearer ${currentToken}` },
              timeout: 10000
            });
            
            if (response.data.access_token) {
              localStorage.setItem('access_token', response.data.access_token);
              logger.info("Token refreshed successfully after 401");
              
              // Retry the original request with new token
              const originalRequest = error.config;
              originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;
              return axiosInstance(originalRequest);
            }
          } catch (refreshError) {
            logger.error("Token refresh failed after 401", refreshError);
          }
        }
      }
      
      // Only clear auth data and redirect for non-login requests
      if (!isLoginRequest) {
        // Clear auth data and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('hero_email');
        
        // Dispatch custom event to notify App.js
        window.dispatchEvent(new CustomEvent('authExpired'));
      }
      
      // Preserve the original error details if available, otherwise use generic message
      if (error.response?.data?.detail) {
        return Promise.reject(error);
      } else {
        return Promise.reject(new Error('Authentication required'));
      }
    }
    
    // Handle other specific errors
    if (error.code === 'ERR_CERT_COMMON_NAME_INVALID' || error.code === 'ERR_CERT_AUTHORITY_INVALID') {
      logger.error('SSL Certificate Error', error, { code: error.code });
      throw new Error('SSL证书验证失败，请联系管理员检查服务器证书配置');
    } else if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      throw new Error('无法连接到服务器，请检查网络连接或稍后重试');
    } else if (error.code === 'ERR_CONNECTION_RESET' || error.code === 'ECONNRESET') {
      throw new Error('连接被服务器重置，请检查服务器状态或稍后重试');
    } else if (error.message && error.message.includes('Mixed Content')) {
      throw new Error('混合内容错误：前端使用HTTPS但后端使用HTTP，请联系管理员配置HTTPS');
    } else if (error.code === 'ERR_NETWORK') {
      throw new Error('网络错误，请检查网络连接或稍后重试');
    }
    
    return Promise.reject(error);
  }
);

// Add retry interceptor for connection failures
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    
    // Don't retry if we've already retried this request
    if (config && config.retryCount && config.retryCount > 0) {
      return Promise.reject(error);
    }
    
    // Don't retry on HTTP status errors (4xx, 5xx) - these are server responses, not network failures
    // Exception: 522 errors are Cloudflare timeout errors that should be retried
    if (error.response && error.response.status && error.response.status !== 522) {
      return Promise.reject(error);
    }
    
    // Don't retry POST requests to avoid duplicate actions (like capture_slave)
    if (config && config.method && config.method.toLowerCase() === 'post') {
      return Promise.reject(error);
    }
    
    // Only retry on actual network-level failures or 522 errors
    if (error.code === 'ECONNABORTED' || 
        error.code === 'ERR_NETWORK' || 
        error.code === 'ECONNREFUSED' || 
        error.code === 'ENOTFOUND' ||
        error.code === 'ERR_CONNECTION_RESET' ||
        error.code === 'ECONNRESET' ||
        (error.response && error.response.status === 522)) {
      
      // Only retry if we have a valid config
      if (config) {
        // Initialize retry count if not set
        config.retryCount = config.retryCount || 0;
        const maxRetries = config.retry || 3;
        
        if (config.retryCount < maxRetries) {
          config.retryCount += 1;
          logger.info(`Retrying request (${config.retryCount}/${maxRetries}): ${config.url}`, { 
            retryCount: config.retryCount, 
            maxRetries, 
            url: config.url, 
            errorCode: error.code 
          });
          
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, config.retryDelay || 1000));
          
          // Retry the request
          return axiosInstance(config);
        }
      }
    }
    
    return Promise.reject(error);
  }
);

// Helper for fetch with JWT token and better error handling
export function fetchWithAuth(url, options = {}) {
  const token = getToken();
  
  // Check if token is valid before making request
  if (!token || !isTokenValid(token)) {
    return Promise.reject(new Error('Authentication required'));
  }
  
  const headers = {
    ...(options.headers || {}),
    'Authorization': `Bearer ${token}`
  };

  return fetch(url, {
    ...options,
    headers,
  }).then(async (response) => {
    // Handle authentication errors
    if (response.status === 401 || response.status === 403) {
      // Try to refresh token
      try {
        const refreshResponse = await fetch(`${API}/refresh_token`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (refreshResponse.ok) {
          const refreshData = await refreshResponse.json();
          if (refreshData.access_token) {
            localStorage.setItem('access_token', refreshData.access_token);
            
            // Retry original request with new token
            const newHeaders = {
              ...headers,
              'Authorization': `Bearer ${refreshData.access_token}`
            };
            
            return fetch(url, {
              ...options,
              headers: newHeaders,
            });
          }
        }
      } catch (refreshError) {
        logger.warn("Token refresh failed", { error: refreshError.message });
      }
      
      // Clear auth data
      localStorage.removeItem('access_token');
      localStorage.removeItem('hero_email');
      window.dispatchEvent(new CustomEvent('authExpired'));
      
      throw new Error('Authentication required');
    }
    
    // Handle other errors
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return response;
  });
}

// API functions
export const api = {
  login: (username, password) => axiosInstance.post(`${API}/login`, { username, password }),
  loginWithGoogle: (googleToken) => axiosInstance.post(`${API}/login/google`, { token: googleToken }),
  register: (email) => axiosInstance.post(`${API}/register`, { email }),
  logout: () => {
    localStorage.removeItem('access_token');
  },
  refreshToken: () => axiosInstance.post(`${API}/refresh_token`),
  getAccounts: (username) => deduplicateRequest(
    'GET', 
    `${API}/accounts`, 
    { username }, 
    null,
    () => axiosInstance.get(`${API}/accounts`, { params: { username } })
  ),
  addAccount: (data) => axiosInstance.post(`${API}/accounts`, data),
  deleteAccount: (username, name) => axiosInstance.delete(`${API}/accounts`, { data: { username, name } }),
  getInfo: (username, accountName, isAdmin = false) => axiosInstance.post(`${API}/info`, { 
    ...(isAdmin ? { target_username: username } : {}),
    account_name: accountName 
  }),
  getDuelInfo: (username, accountName, isAdmin = false) => axiosInstance.post(`${API}/duel_info`, { 
    ...(isAdmin ? { target_username: username } : {}),
    account_name: accountName 
  }),
  buyCombatCount: (username, accountName) => axiosInstance.post(`${API}/buy_combat_count`, { username, account_name: accountName }),
  stopCombat: (username) => axiosInstance.post(`${API}/stop_combat?username=${encodeURIComponent(username)}`),
  getLogFiles: (username) => deduplicateRequest(
    'GET',
    `${API}/log_files`,
    { username },
    null,
    () => axiosInstance.get(`${API}/log_files?username=${username}`)
  ),
  getLogFileContent: (username, filePath) => fetchWithAuth(`${API}/log_file_content?username=${encodeURIComponent(username)}&file_path=${encodeURIComponent(filePath)}`, {
    method: "GET",
  }),
  resumeStream: (username, accountNames, isAdmin = false) => fetchWithAuth(`${API}/resume_stream`, {
    method: "POST",
    body: JSON.stringify({
      ...(isAdmin ? { target_username: username } : {}),
      account_names: accountNames
    }),
    headers: {
      "Content-Type": "application/json",
    },
  }),
  hallCombatStream: (username, accountNames, isAdmin = false) => fetchWithAuth(`${API}/hall_combat_stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      ...(isAdmin ? { target_username: username } : {}),
      account_names: accountNames
    }),
  }),
  hallChallenge: (username, accountName, hallName, isAdmin = false) => fetchWithAuth(`${API}/hall_challenge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      ...(isAdmin ? { target_username: username } : {}),
      account_names: accountName, 
      hall_name: hallName 
    }),
  }),
  hallChallengeMultiple: (username, accountNames, hallName, isAdmin = false) => fetchWithAuth(`${API}/hall_challenge_multiple`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      ...(isAdmin ? { target_username: username } : {}),
      account_names: accountNames, 
      hall_name: hallName 
    }),
  }),
  // Check connection status - use regular axios instance for this
  connectionStatus: (username) => deduplicateRequest(
    'GET',
    `${API}/connection_status`,
    { username },
    null,
    () => axiosInstance.get(`${API}/connection_status?username=${encodeURIComponent(username)}`)
  ),
  // Connection test function - use regular axios instance for this
  testConnection: async () => {
    try {
      const response = await axiosInstance.get(`${API}/health`);
      return {
        success: true,
        data: response.data,
        latency: response.headers['x-response-time'] || 'unknown'
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        code: error.code,
        status: error.response?.status
      };
    }
  },
  // Debug function to show request cache status
  debugRequestCache: () => {
    console.log(`Request cache status: ${requestCache.size} pending requests`);
    for (const [key, promise] of requestCache.entries()) {
      const age = promise._timestamp ? Date.now() - promise._timestamp : 'unknown';
      console.log(`Cache entry: ${key} (age: ${age}ms)`);
    }
  },
  // Manual cleanup function for the request cache
  cleanupRequestCache: () => {
    cleanupExpiredCache();
  },
  // User settings (includes auto challenge and hourly jobs)
  getUserSettings: (username, isAdmin = false) => deduplicateRequest(
    'GET',
    `${API}/user_settings`,
    { username, isAdmin },
    null,
    () => {
      const url = isAdmin 
        ? `${API}/user_settings?target_username=${encodeURIComponent(username)}`
        : `${API}/user_settings?current_user=${encodeURIComponent(username)}`;
      return axiosInstance.get(url);
    }
  ),
  getJobsTable: () => deduplicateRequest(
    'GET',
    `${API}/jobs_table`,
    {},
    null,
    () => axiosInstance.get(`${API}/jobs_table`)
  ),
  setJobSettings: (username, jobSettings, jobSchedulingEnabled = true, isAdmin = false) => axiosInstance.post(`${API}/set_job_settings`, {
    username,
    job_settings: jobSettings,
    job_scheduling_enabled: jobSchedulingEnabled
  }),
  debugUserSettings: (username) => axiosInstance.get(`${API}/debug_user_settings?username=${encodeURIComponent(username)}`),
  refreshCache: (username) => axiosInstance.post(`${API}/refresh_cache?username=${encodeURIComponent(username)}`),
  clearCache: (username) => axiosInstance.post(`${API}/clear_cache?username=${encodeURIComponent(username)}`),
  executeJob: (jobId, accountNames = [], username = null, isAdmin = false) => axiosInstance.post(`${API}/execute_job`, { 
    job_id: jobId, 
    account_names: accountNames,
    ...(isAdmin && username ? { target_username: username } : {})
  }),
  executeCommand: (username, accountNames, command, id = null, isDuelCommand = false, isAdmin = false) => axiosInstance.post(`${API}/execute_command`, { 
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames, 
    command, 
    id,
    is_duel_command: isDuelCommand
  }),
  olympics: (username, accountNames, matchType, isAdmin = false) => axiosInstance.post(`${API}/olympics`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames,
    type: matchType
  }),
  zonghengChallenge: (username, accountNames, isAdmin = false) => axiosInstance.post(`${API}/zongheng_challenge`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames
  }),
  lottery: (username, accountNames, lotteryType, lotteryNumbers, isAdmin = false) => axiosInstance.post(`${API}/lottery`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames,
    type: lotteryType,
    lottery_numbers: lotteryNumbers
  }),
  buyDuelMedal: (username, accountNames, bigPackage = true, isAdmin = false) => axiosInstance.post(`${API}/buy_duel_medal`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames,
    big_package: bigPackage
  }),
  getFanBadges: (username, accountNames, isAdmin = false) => axiosInstance.post(`${API}/get_fan_badges`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames
  }),
  exchangeFanBadge: (username, accountNames, badge, quantity, isAdmin = false) => axiosInstance.post(`${API}/exchange_fan_badge`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames,
    badge_name: badge.name,
    badge_id: badge.id,
    required_item: badge.required_item,
    required_quantity: badge.required_quantity,
    exchange_quantity: quantity
  }),
  autoGift: (username, accountNames, isAdmin = false) => axiosInstance.post(`${API}/auto_gift`, {
    ...(isAdmin ? { target_username: username } : {}),
    account_names: accountNames
  }),
  // Extract cookies automatically using username and password
  extractCookies: (username, password, url = null, timeout = 60) => axiosInstance.post(`${API}/extract_cookies`, {
    username,
    password,
    url,
    timeout
  }),
  // Extract cookies interactively (opens browser for manual login)
  extractCookiesInteractive: (pageUrl = null, timeout = 300) => axiosInstance.post(`${API}/extract_cookies_interactive`, {
    page_url: pageUrl,
    timeout
  }),
  
  // Admin API functions
  getAllPlayers: () => axiosInstance.get(`${API}/admin/players`),
  getPlayerAccounts: (playerEmail) => axiosInstance.get(`${API}/admin/players/${encodeURIComponent(playerEmail)}/accounts`),
  toggleUserStatus: (playerEmail, disabled) => axiosInstance.post(`${API}/admin/players/${encodeURIComponent(playerEmail)}/toggle_status`, { disabled }),
  
  // Job status and shutdown control
  getJobStatus: () => axiosInstance.get(`${API}/admin/job_status`),
  initiateShutdown: () => axiosInstance.post(`${API}/admin/shutdown`),
  getShutdownStatus: () => axiosInstance.get(`${API}/admin/shutdown_status`),
  
  // Open browser with stored cookies (admin only)
  openBrowserWithCookies: (targetUsername, accountName, gameUrl = null) => axiosInstance.post(`${API}/admin/open_browser_with_cookies`, {
    target_username: targetUsername,
    account_name: accountName,
    game_url: gameUrl
  }),
};