import React, { useState, useEffect, useCallback } from "react";
import { AppBar, Toolbar, Typography, Button, Box, Tooltip, IconButton, ThemeProvider, Tabs, Tab } from "@mui/material";
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import SettingsIcon from '@mui/icons-material/Settings';
import InfoIcon from '@mui/icons-material/Info';
import theme from './theme';
import { api } from "./utils/api";
import { useStreaming } from "./hooks/useStreaming";
import { logger } from "./utils/logger";

// Components
import Login from "./components/Login";
import AccountList from "./components/AccountList";
import OutputWindow from "./components/OutputWindow";
import AddAccountDialog from "./components/AddAccountDialog";
import SettingsDialog from "./components/SettingsDialog";
import GlobalSettingsDialog from "./components/GlobalSettingsDialog";
import LogViewerDialog from "./components/LogViewerDialog";
import InfoDialogs from "./components/InfoDialogs";
import ExecuteCommandDialog from "./components/ExecuteCommandDialog";
import FanBadgeDialog from "./components/FanBadgeDialog";
import LotteryDialog from "./components/LotteryDialog";
import AdminPanel from "./components/AdminPanel";
import ShutdownControl from "./components/ShutdownControl";
import FeatureGuide from "./components/FeatureGuide";

function App() {
  // Authentication state
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [userType, setUserType] = useState("player"); // 'player' or 'admin'
  const [advanced, setAdvanced] = useState(false); // Advanced user flag
  const [isLoading, setIsLoading] = useState(true);
  
  // Account management state
  const [accounts, setAccounts] = useState([]);
  const [selected, setSelected] = useState([]);
  
  // Admin state
  const [selectedPlayerEmail, setSelectedPlayerEmail] = useState(null);
  const [playerAccounts, setPlayerAccounts] = useState([]);
  const [selectedPlayerAccounts, setSelectedPlayerAccounts] = useState([]);
  
  // UI state
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsAcc, setSettingsAcc] = useState(null);
  const [globalSettingsOpen, setGlobalSettingsOpen] = useState(false);
  const [logViewerOpen, setLogViewerOpen] = useState(false);
  const [executeCommandOpen, setExecuteCommandOpen] = useState(false);
  const [fanBadgeDialogOpen, setFanBadgeDialogOpen] = useState(false);
  const [lotteryDialogOpen, setLotteryDialogOpen] = useState(false);
  const [selectedLotteryType, setSelectedLotteryType] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('unknown');
  const [connectionError, setConnectionError] = useState('');
  // Note: Removed auto-reconnection state variables
  const [hallCombatInfo, setHallCombatInfo] = useState(null);
  const [activeConnections, setActiveConnections] = useState(0);
  const [featureGuideOpen, setFeatureGuideOpen] = useState(false);
  const [adminTab, setAdminTab] = useState(0); // 0 = players, 1 = shutdown control

  // Test connection function
  const testConnection = useCallback(async () => {
    setConnectionStatus('testing');
    setConnectionError('');
    try {
      const result = await api.testConnection();
      if (result.success) {
        setConnectionStatus('connected');
        setConnectionError('');
        
        // Also fetch connection status to get hall combat info
        if (username) {
          try {
            const statusRes = await api.connectionStatus(username);
            // Only set hall combat info if there's actually active combat
            if (statusRes.data.hall_combat_info && statusRes.data.hall_combat_info.active_threads > 0) {
              setHallCombatInfo(statusRes.data.hall_combat_info);
            } else {
              setHallCombatInfo(null);
            }
            setActiveConnections(statusRes.data.active_connections);
          } catch (statusError) {
            logger.warn("Could not fetch connection status", { error: statusError.message });
          }
        }
      } else {
        setConnectionStatus('error');
        setConnectionError(result.error || 'Connection failed');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionError(error.message || 'Connection test failed');
    }
  }, [username]);

  // Test connection on component mount
  useEffect(() => {
    if (loggedIn) {
      testConnection();
    }
  }, [loggedIn, testConnection]);


  // Note: Removed periodic token refresh - only check connection once on startup

  // Local JWT token validation
  const isTokenValid = (token) => {
    if (!token) return false;
    
    try {
      // Decode the JWT token to check expiration
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
  const isTokenNearExpiry = (token) => {
    if (!token) return false;
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Math.floor(Date.now() / 1000);
      
      // Check if token expires within 10 minutes
      return payload.exp < (currentTime + 600);
    } catch (error) {
      console.log("Error parsing JWT token for expiry check:", error);
      return false;
    }
  };

  // Refresh token function
  const refreshToken = async () => {
    try {
      const response = await api.refreshToken();
      if (response.data.access_token) {
        localStorage.setItem('access_token', response.data.access_token);
        logger.info(username + ": Token refreshed successfully");
        return true;
      }
    } catch (error) {
      logger.error("Token refresh failed", error);
      return false;
    }
    return false;
  };
  
  // Dialog states
  const [missingHallDialogOpen, setMissingHallDialogOpen] = useState(false);
  const [missingHallAccounts, setMissingHallAccounts] = useState([]);
  const [missingAccountsDialogOpen, setMissingAccountsDialogOpen] = useState(false);
  const [missingAccounts, setMissingAccounts] = useState([]);

  // Custom hooks
  const { streamResumeStream, streamHallCombat, streamHallChallenge, stopAllStreams } = useStreaming();

  // Note: Removed auto-reconnection check - only check connection status on startup

  // Define fetchAccounts function before useEffect
  const fetchAccounts = useCallback(async (user = username) => {
    if (!user) {
      logger.error("No username provided to fetchAccounts");
      return;
    }
    try {
      const res = await api.getAccounts(user);
      setAccounts(res.data);
      setError(""); // Clear any previous errors
    } catch (e) {
      console.error("Failed to fetch accounts", e);
      
      // Handle different types of errors
      if (e.response?.status === 401 || e.response?.status === 403) {
        // Auth error - this will be handled by the axios interceptor
        console.log("Auth error in fetchAccounts, will be handled by interceptor");
      } else if (!e.response) {
        // Network error
        setError("无法连接到服务器，请检查网络连接");
        // Don't clear accounts on network error, keep existing data
      } else if (e.response.status === 500) {
        setError("服务器内部错误，请稍后重试");
        // Don't clear accounts on server error
      } else {
        setError("获取账号列表失败: " + (e.response?.data?.detail || e.message));
        // Don't clear accounts on other errors
      }
    }
  }, [username]);

  // On mount, check localStorage for username and token validity
  useEffect(() => {
    let isMounted = true;
    
    const savedUser = localStorage.getItem("hero_email");
    const token = localStorage.getItem("access_token");
    
    if (savedUser && token) {
      // Verify token is still valid by making a test API call
      const verifyAuth = async () => {
        const token = localStorage.getItem('access_token');
        
        // First check if token exists and is valid locally
        if (!token || !isTokenValid(token)) {
          logger.warn("Token is missing or expired locally");
          if (isMounted) {
            localStorage.removeItem("hero_email");
            localStorage.removeItem("access_token");
            setLoggedIn(false);
            setUsername("");
            setIsLoading(false);
          }
          return;
        }
        
        // Check if token needs refresh
        if (isTokenNearExpiry(token)) {
          logger.info(savedUser + ": Token is near expiry, attempting refresh");
          const refreshSuccess = await refreshToken();
          if (!refreshSuccess) {
            logger.warn(savedUser + ": Token refresh failed, logging out");
            if (isMounted) {
              localStorage.removeItem("hero_email");
              localStorage.removeItem("access_token");
              setLoggedIn(false);
              setUsername("");
              setIsLoading(false);
            }
            return;
          }
        }
        
        try {
          await api.getAccounts(savedUser);
          if (isMounted) {
            setUsername(savedUser);
            setLoggedIn(true);
            // Get user_type from localStorage if available
            const savedUserType = localStorage.getItem("user_type") || "player";
            setUserType(savedUserType);
            // Get advanced field from localStorage if available
            const savedAdvanced = localStorage.getItem("advanced") === "true";
            setAdvanced(savedAdvanced);
            if (savedUserType === "admin") {
              // Admin doesn't need to fetch their own accounts
            } else {
              fetchAccounts(savedUser);
            }
          }
        } catch (error) {
          logger.error(savedUser + ": Auth verification failed", error, { savedUser });
          
          // Only clear auth data if it's actually an auth error (401/403)
          // Don't clear on network errors to avoid logging out on temporary connection issues
          if (error.response?.status === 401 || error.response?.status === 403) {
            logger.warn("Token validation failed, clearing auth data", { status: error.response?.status });
            if (isMounted) {
              localStorage.removeItem("hero_email");
              localStorage.removeItem("access_token");
              setLoggedIn(false);
              setUsername("");
            }
          } else if (!error.response) {
            // Network error - don't log out, just show connection status
            logger.warn("Network error during auth verification, keeping current state", { error: error.message });
            if (isMounted) {
              setLoggedIn(true);
              setUsername(savedUser);
              const savedUserType = localStorage.getItem("user_type") || "player";
              setUserType(savedUserType);
              const savedAdvanced = localStorage.getItem("advanced") === "true";
              setAdvanced(savedAdvanced);
              // Try to fetch accounts anyway
              fetchAccounts(savedUser);
            }
          } else {
            // Other server errors - don't log out
            logger.warn("Server error during auth verification, keeping current state", { status: error.response?.status });
            if (isMounted) {
              setLoggedIn(true);
              setUsername(savedUser);
              const savedUserType = localStorage.getItem("user_type") || "player";
              setUserType(savedUserType);
              const savedAdvanced = localStorage.getItem("advanced") === "true";
              setAdvanced(savedAdvanced);
              fetchAccounts(savedUser);
            }
          }
        } finally {
          if (isMounted) {
            setIsLoading(false);
          }
        }
      };
      verifyAuth();
    } else {
      // Clear any stale data
      localStorage.removeItem("hero_email");
      localStorage.removeItem("access_token");
      if (isMounted) {
        setLoggedIn(false);
        setUsername("");
        setIsLoading(false);
      }
    }
    
    return () => {
      isMounted = false;
    };
  }, [fetchAccounts]);

  // Listen for auth expired events from API interceptors
  useEffect(() => {
    const handleAuthExpired = () => {
      logger.warn("Auth expired event received, logging out user", { username });
      setLoggedIn(false);
      setUsername("");
      setError("登录已过期，请重新登录");
    };

    window.addEventListener('authExpired', handleAuthExpired);
    
    return () => {
      window.removeEventListener('authExpired', handleAuthExpired);
    };
  }, []);

  const handleLogin = async (user, userTypeFromLogin = "player", advancedFromLogin = false) => {
    try {
      // The login component already handles token storage
      // We just need to set the logged in state
      logger.info(user + ": User logged in", { 
        userId: user,
        userEmail: user,
        userType: userTypeFromLogin, 
        advanced: advancedFromLogin,
        timestamp: new Date().toISOString()
      });
      setLoggedIn(true);
      setUsername(user);
      setUserType(userTypeFromLogin);
      setAdvanced(advancedFromLogin);
      localStorage.setItem("hero_email", user);
      localStorage.setItem("user_type", userTypeFromLogin);
      localStorage.setItem("advanced", advancedFromLogin.toString());
      if (userTypeFromLogin === "admin") {
        // Admin doesn't need to fetch their own accounts
      } else {
        fetchAccounts(user);
      }
    } catch (error) {
      logger.error("Login error", error, { userId: user, userEmail: user });
      setError("登录失败，请检查用户名和密码");
    }
  };

  const handleLogout = () => {
    logger.info(username + ": User logged out", { 
      userId: username,
      userEmail: username,
      timestamp: new Date().toISOString()
    });
    setLoggedIn(false);
    setUsername("");
    setUserType("player");
    setAdvanced(false);
    setSelectedPlayerEmail(null);
    setPlayerAccounts([]);
    setSelectedPlayerAccounts([]);
    localStorage.removeItem("hero_email");
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_type");
    localStorage.removeItem("advanced");
  };

  const handleSelect = (name) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const handleSelectAll = (all) => {
    setSelected(all ? accounts.map((a) => a.name) : []);
  };

  const handleGetInfo = async () => {
    setOutput("");
    let failedAccounts = [];
    for (let accName of selected) {
      try {
        const res = await api.getInfo(username, accName);
        setOutput((prev) => prev + `[${accName}]\n` + JSON.stringify(res.data.info, null, 2) + "\n\n");
      } catch (e) {
        failedAccounts.push(accName);
        let errorMsg = "";
        if (!e.response) {
          errorMsg = "无法连接到服务器";
        } else if (e.response.status === 404) {
          errorMsg = "账号不存在或Cookie已过期";
        } else if (e.response.status === 500) {
          errorMsg = "服务器内部错误";
        } else {
          errorMsg = e.response?.data?.detail || e.message;
        }
        setOutput((prev) => prev + `[${accName}] 获取信息失败: ${errorMsg}\n\n`);
      }
    }
    if (failedAccounts.length > 0) {
      setMissingAccounts(failedAccounts);
      setMissingAccountsDialogOpen(true);
    }
  };

  const handleGetDuelInfo = async () => {
    setOutput("");
    let failedAccounts = [];
    for (let accName of selected) {
      try {
        const res = await api.getDuelInfo(username, accName);
        setOutput((prev) => prev + `[${accName}] 跨服竞技场信息\n` + JSON.stringify(res.data.info, null, 2) + "\n\n");
      } catch (e) {
        failedAccounts.push(accName);
        let errorMsg = "";
        if (!e.response) {
          errorMsg = "无法连接到服务器";
        } else if (e.response.status === 404) {
          errorMsg = "账号不存在或Cookie已过期";
        } else if (e.response.status === 500) {
          errorMsg = "服务器内部错误";
        } else {
          errorMsg = e.response?.data?.detail || e.message;
        }
        setOutput((prev) => prev + `[${accName}] 跨服信息获取失败: ${errorMsg}\n\n`);
      }
    }
    if (failedAccounts.length > 0) {
      setMissingAccounts(failedAccounts);
      setMissingAccountsDialogOpen(true);
    }
  };

  const handleStopCombat = async () => {
    // Stop all streaming connections first
    stopAllStreams();
    
    try {
      const res = await api.stopCombat(username);
      if (res.data.success) {
        // Show success message for all selected accounts
        for (let accName of selected) {
          setOutput((prev) => prev + `[${accName}] 停止挑战: {\n  "success": true,\n  "message": "Combat stopped successfully"\n}\n\n`);
        }
        // Also show the detailed backend response
        setOutput((prev) => prev + `停止挑战详情: ` + JSON.stringify(res.data, null, 2) + "\n\n");
      } else {
        // Show failure message for all selected accounts
        for (let accName of selected) {
          setOutput((prev) => prev + `[${accName}] 停止挑战: ` + JSON.stringify(res.data, null, 2) + "\n\n");
        }
      }
    } catch (e) {
      let errorMsg = "";
      if (!e.response) {
        errorMsg = "无法连接到服务器";
      } else if (e.response.status === 500) {
        errorMsg = "服务器内部错误";
      } else {
        errorMsg = e.response?.data?.detail || e.message;
      }
      // Show error message for all selected accounts
      for (let accName of selected) {
        setOutput((prev) => prev + `[${accName}] 停止挑战失败: ${errorMsg}\n\n`);
      }
    }
  };

  const handleViewLastRun = () => {
    // For resume stream, we need to pass account names. If none selected, use all accounts
    const accountsToUse = selected.length > 0 ? selected : accounts.map(acc => acc.name);
    streamResumeStream(username, accountsToUse, setOutput, setError);
  };

  const handleHallCombat = () => {
    streamHallCombat(username, selected, setOutput, setMissingHallDialogOpen, setMissingHallAccounts, accounts);
  };

  const handleHallChallenge = (hallName) => {
    if (selected.length === 0) {
      setError("请先选择一个账号进行幻境挑战");
      return;
    }
    
    setOutput("");
    
    // Use the streaming hook for individual hall challenge with multiple accounts
    streamHallChallenge(username, selected, hallName, setOutput, setError);
  };

  const handleAddAccount = () => {
    setAddOpen(true);
  };

  const handleSaveAccount = async (accountData) => {
    try {
      await api.addAccount({ username, ...accountData });
      const accountJson = JSON.stringify(accountData, null, 2);
      logger.info(username + `: Game account ${accountData.account_name || accountData.name} added: ${JSON.stringify(accountData)}`, {
        userId: username,
        userEmail: username,
        accountName: accountData.account_name || accountData.name,
        accountUrl: accountData.url || null,
        hasCookie: !!accountData.cookie,
        hasWeeCookie: !!accountData.weeCookie,
        hasHeroSession: !!accountData.heroSession,
        accountData: accountJson,
        timestamp: new Date().toISOString(),
      });
      fetchAccounts();
    } catch (error) {
      logger.error("Failed to add game account", error, {
        userId: username,
        userEmail: username,
        accountName: accountData.account_name || accountData.name,
        accountData: JSON.stringify(accountData),
      });
      throw error;
    }
  };

  const handleDeleteAccounts = async () => {
    const accountsToDelete = [...selected]; // Create a copy to avoid state issues
    
    if (accountsToDelete.length === 0) {
      return;
    }
    
    // Log deletion start
    logger.info(username + `: Deleting game accounts: ${accountsToDelete.join(', ')}`, {
      userId: username,
      userEmail: username,
      accountsToDelete: accountsToDelete,
      accountCount: accountsToDelete.length,
      action: 'delete_accounts_start'
    });
    
    // Immediately remove deleted accounts from UI for better UX
    setAccounts(prevAccounts => prevAccounts.filter(acc => !accountsToDelete.includes(acc.name)));
    setSelected([]);
    
    const deletedAccounts = [];
    const failedAccounts = [];
    
    try {
      // Delete all accounts in parallel
      await Promise.all(
        accountsToDelete.map(accName => 
          api.deleteAccount(username, accName)
            .then(() => {
              deletedAccounts.push(accName);
              return accName;
            })
            .catch(e => {
              failedAccounts.push(accName);
              logger.error(`Failed to delete account ${accName}`, e, { accountName: accName, username });
              // Don't re-throw, just log the error
              return null;
            })
        )
      );
      
      // Log success for successfully deleted accounts
      if (deletedAccounts.length > 0) {
        logger.info(username + `: Game accounts deleted successfully: ${deletedAccounts.join(', ')}`, {
          userId: username,
          userEmail: username,
          deletedAccounts: deletedAccounts,
          accountCount: deletedAccounts.length,
          action: 'delete_accounts_success'
        });
      }
      
      // Log failure summary if any failed
      if (failedAccounts.length > 0) {
        logger.error(`Some account deletions failed: ${failedAccounts.join(', ')}`, null, {
          userId: username,
          userEmail: username,
          failedAccounts: failedAccounts,
          accountCount: failedAccounts.length,
          action: 'delete_accounts_partial_failure'
        });
      }
    } catch (e) {
      // Some deletions may have failed
      logger.error("Account deletion operation failed", e, { 
        accountsToDelete, 
        username,
        deletedAccounts,
        failedAccounts,
        action: 'delete_accounts_error'
      });
    }
    
    // Always refresh accounts list to ensure consistency with backend
    await fetchAccounts();
  };

  const handleOpenSettings = (acc) => {
    setSettingsAcc(acc);
    setSettingsOpen(true);
  };

  const handleOpenGlobalSettings = () => {
    setGlobalSettingsOpen(true);
  };

  const handleRefreshCache = async () => {
    try {
      await api.refreshCache(username);
      setOutput((prev) => prev + `缓存刷新成功！\n\n`);
      // Refresh accounts to get updated data
      fetchAccounts();
    } catch (e) {
      let errorMsg = "";
      if (!e.response) {
        errorMsg = "无法连接到服务器";
      } else if (e.response.status === 500) {
        errorMsg = "服务器内部错误";
      } else {
        errorMsg = e.response?.data?.detail || e.message;
      }
      setOutput((prev) => prev + `缓存刷新失败: ${errorMsg}\n\n`);
    }
  };

  const handleSaveSettings = async (accountData) => {
    try {
      await api.addAccount({ username, ...accountData });
      const settingsJson = JSON.stringify(accountData, null, 2);
      logger.info(username + `: Game account updated: ${JSON.stringify(accountData)}`, {
        userId: username,
        userEmail: username,
        accountName: accountData.name,
        accountUrl: accountData.url || null,
        hasCookie: !!accountData.cookie,
        hasWeeCookie: !!accountData.weeCookie,
        hasHeroSession: !!accountData.heroSession,
        accountData: settingsJson,
        timestamp: new Date().toISOString(),
      });
      fetchAccounts();
    } catch (error) {
      logger.error("Failed to update game account", error, {
        userId: username,
        userEmail: username,
        accountName: accountData.name,
      });
      throw error;
    }
  };

  const handleOpenLogViewer = () => {
    setLogViewerOpen(true);
  };

  const handleOpenExecuteCommand = () => {
    setExecuteCommandOpen(true);
  };

  const formatCommandResults = (results) => {
    let output = "";
    
    for (const [accountName, result] of Object.entries(results)) {
      output += `\n【${accountName}】\n`;
      
      if (result.success) {
        let message = result.message;
        
        // Try to parse the message as JSON if it's a string
        if (typeof message === 'string') {
          try {
            const parsed = JSON.parse(message);
            // If successfully parsed, format it nicely
            message = JSON.stringify(parsed, null, 2);
          } catch {
            // If not JSON, keep as is
          }
        } else if (typeof message === 'object') {
          // If already an object, format it
          message = JSON.stringify(message, null, 2);
        }
        
        output += `${message}\n`;
      } else {
        // Check for error message in either 'error' or 'message' field
        const errorMsg = result.error || result.message || "未知错误";
        output += `❌ 错误: ${errorMsg}\n`;
      }
    }
    
    return output;
  };

  const handleExecuteCommand = async (command, id, isDuelCommand = false) => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      const commandPrefix = isDuelCommand ? '[跨服] ' : '';
      setOutput((prev) => prev + `${commandPrefix}执行命令 "${command}"${id ? ` (ID: ${id})` : ''} 对 ${selected.length} 个账号...\n`);
      
      const response = await api.executeCommand(username, selected, command, id, isDuelCommand);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "命令执行失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  const handleOlympics = async (matchType) => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      setOutput((prev) => prev + `报名比赛 "${matchType}" 对 ${selected.length} 个账号...\n`);
      
      const response = await api.olympics(username, selected, matchType);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "报名比赛失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  const handleZonghengChallenge = async () => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      setOutput((prev) => prev + `执行纵横天下挑战对 ${selected.length} 个账号...\n`);
      
      const response = await api.zonghengChallenge(username, selected);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "纵横天下挑战失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  const handleLottery = (lotteryType) => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }
    setSelectedLotteryType(lotteryType);
    setLotteryDialogOpen(true);
  };

  const handleLotterySubmit = async (lotteryNumbers) => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      setOutput((prev) => prev + `联赛竞猜 "${selectedLotteryType}" 号码 "${lotteryNumbers}" 对 ${selected.length} 个账号...\n`);
      
      const response = await api.lottery(username, selected, selectedLotteryType, lotteryNumbers);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "联赛竞猜失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  const handleBuyDuelMedal = async (bigPackage = true) => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      const packageType = bigPackage ? "大" : "单个";
      setOutput((prev) => prev + `买通用徽章礼包(${packageType}) 对 ${selected.length} 个账号...\n`);
      
      const response = await api.buyDuelMedal(username, selected, bigPackage);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "买通用徽章失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  const handleOpenFanBadgeDialog = () => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }
    setFanBadgeDialogOpen(true);
  };

  const handleFanBadgeSubmit = async (badge, quantity) => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      setOutput((prev) => prev + `粉丝章兑换: ${badge.name} x${quantity} 对 ${selected.length} 个账号...\n`);
      
      const response = await api.exchangeFanBadge(username, selected, badge, quantity);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "粉丝章兑换失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  const handleAutoGift = async () => {
    if (selected.length === 0) {
      setError("请先选择账号");
      return;
    }

    try {
      setOutput((prev) => prev + `领取礼包 对 ${selected.length} 个账号...\n`);
      
      const response = await api.autoGift(username, selected);
      const result = response.data;
      
      const formattedOutput = formatCommandResults(result.results);
      setOutput((prev) => prev + formattedOutput + "\n");
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "领取礼包失败";
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
      setError(errorMsg);
    }
  };

  // Admin panel handlers
  const handleSelectPlayer = async (playerEmail) => {
    setSelectedPlayerEmail(playerEmail);
    setSelectedPlayerAccounts([]);
    try {
      const response = await api.getPlayerAccounts(playerEmail);
      setPlayerAccounts(response.data || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "获取玩家账号失败");
      setPlayerAccounts([]);
    }
  };

  const handleSelectPlayerAccount = (accountName) => {
    setSelectedPlayerAccounts((prev) =>
      prev.includes(accountName) ? prev.filter((n) => n !== accountName) : [...prev, accountName]
    );
  };

  const handleSelectAllPlayerAccounts = (all) => {
    setSelectedPlayerAccounts(all ? playerAccounts.map((a) => a.name) : []);
  };

  const handleRefreshPlayerAccounts = async () => {
    if (selectedPlayerEmail) {
      try {
        const response = await api.getPlayerAccounts(selectedPlayerEmail);
        setPlayerAccounts(response.data || []);
      } catch (e) {
        setError(e.response?.data?.detail || e.message || "刷新账号列表失败");
      }
    }
  };

  // Admin handlers for account management
  const handleAdminAddAccount = () => {
    if (!selectedPlayerEmail) {
      setError("请先选择一个玩家");
      return;
    }
    setAddOpen(true);
  };

  const handleAdminSaveAccount = async (accountData) => {
    if (!selectedPlayerEmail) {
      setError("请先选择一个玩家");
      return;
    }
    try {
      await api.addAccount({ username: selectedPlayerEmail, ...accountData });
      const accountJson = JSON.stringify(accountData, null, 2);
      logger.info(username + `: Game account added by admin for ${selectedPlayerEmail}: ${JSON.stringify(accountData)}`, {
        adminUserId: username,
        adminUserEmail: username,
        targetUserId: selectedPlayerEmail,
        targetUserEmail: selectedPlayerEmail,
        accountName: accountData.account_name || accountData.name,
        accountUrl: accountData.url || null,
        hasCookie: !!accountData.cookie,
        hasWeeCookie: !!accountData.weeCookie,
        hasHeroSession: !!accountData.heroSession,
        accountData: accountJson,
        timestamp: new Date().toISOString(),
      });
      handleRefreshPlayerAccounts();
    } catch (error) {
      logger.error("Failed to add game account (admin)", error, {
        adminUserId: username,
        adminUserEmail: username,
        targetUserId: selectedPlayerEmail,
        accountName: accountData.account_name || accountData.name,
        accountData: JSON.stringify(accountData),
      });
      throw error;
    }
  };

  const handleAdminOpenSettings = (acc) => {
    if (!selectedPlayerEmail) {
      setError("请先选择一个玩家");
      return;
    }
    setSettingsAcc(acc);
    setSettingsOpen(true);
  };

  const handleAdminSaveSettings = async (accountData) => {
    if (!selectedPlayerEmail) {
      setError("请先选择一个玩家");
      return;
    }
    try {
      await api.addAccount({ username: selectedPlayerEmail, ...accountData });
      const settingsJson = JSON.stringify(accountData, null, 2);
      logger.info(username + `: Game account updated by admin for ${selectedPlayerEmail}: ${JSON.stringify(accountData)}`, {
        adminUserId: username,
        adminUserEmail: username,
        targetUserId: selectedPlayerEmail,
        targetUserEmail: selectedPlayerEmail,
        accountName: accountData.name,
        accountUrl: accountData.url || null,
        hasCookie: !!accountData.cookie,
        hasWeeCookie: !!accountData.weeCookie,
        hasHeroSession: !!accountData.heroSession,
        accountData: settingsJson,
        timestamp: new Date().toISOString(),
      });
      handleRefreshPlayerAccounts();
    } catch (error) {
      logger.error("Failed to update game account (admin)", error, {
        adminUserId: username,
        adminUserEmail: username,
        targetUserId: selectedPlayerEmail,
        accountName: accountData.name,
      });
      throw error;
    }
  };

  const handleAdminDeleteAccounts = async () => {
    if (!selectedPlayerEmail) {
      setError("请先选择一个玩家");
      return;
    }
    const accountsToDelete = [...selectedPlayerAccounts];
    
    if (accountsToDelete.length === 0) {
      return;
    }
    
    // Log deletion start
    logger.info(username + `: Admin deleting game accounts for ${selectedPlayerEmail}: ${accountsToDelete.join(', ')}`, {
      adminUserId: username,
      adminUserEmail: username,
      targetUserId: selectedPlayerEmail,
      targetUserEmail: selectedPlayerEmail,
      accountsToDelete: accountsToDelete,
      accountCount: accountsToDelete.length,
      action: 'admin_delete_accounts_start'
    });
    
    // Immediately remove deleted accounts from UI for better UX
    setPlayerAccounts(prevAccounts => prevAccounts.filter(acc => !accountsToDelete.includes(acc.name)));
    setSelectedPlayerAccounts([]);
    
    const deletedAccounts = [];
    const failedAccounts = [];
    
    try {
      // Delete all accounts in parallel
      await Promise.all(
        accountsToDelete.map(accName => 
          api.deleteAccount(selectedPlayerEmail, accName)
            .then(() => {
              deletedAccounts.push(accName);
              return accName;
            })
            .catch(e => {
              failedAccounts.push(accName);
              logger.error(`Failed to delete account ${accName}`, e, { accountName: accName, playerEmail: selectedPlayerEmail });
              return null;
            })
        )
      );
      
      // Log success for successfully deleted accounts
      if (deletedAccounts.length > 0) {
        logger.info(username + `: Admin deleted game accounts for ${selectedPlayerEmail}: ${deletedAccounts.join(', ')}`, {
          adminUserId: username,
          adminUserEmail: username,
          targetUserId: selectedPlayerEmail,
          targetUserEmail: selectedPlayerEmail,
          deletedAccounts: deletedAccounts,
          accountCount: deletedAccounts.length,
          action: 'admin_delete_accounts_success'
        });
      }
      
      // Log failure summary if any failed
      if (failedAccounts.length > 0) {
        logger.error(`Admin: Some account deletions failed for ${selectedPlayerEmail}: ${failedAccounts.join(', ')}`, null, {
          adminUserId: username,
          adminUserEmail: username,
          targetUserId: selectedPlayerEmail,
          failedAccounts: failedAccounts,
          accountCount: failedAccounts.length,
          action: 'admin_delete_accounts_partial_failure'
        });
      }
    } catch (e) {
      // Some deletions may have failed
      logger.error("Admin account deletion operation failed", e, { 
        accountsToDelete, 
        playerEmail: selectedPlayerEmail,
        adminUserId: username,
        deletedAccounts,
        failedAccounts,
        action: 'admin_delete_accounts_error'
      });
    }
    
    // Always refresh accounts list to ensure consistency with backend
    await handleRefreshPlayerAccounts();
  };

  const handleAdminOpenBrowser = async (acc) => {
    if (!selectedPlayerEmail) {
      setError("请先选择一个玩家");
      return;
    }
    try {
      setOutput((prev) => prev + `正在为账号 ${acc.name} 打开浏览器...\n`);
      const response = await api.openBrowserWithCookies(selectedPlayerEmail, acc.name);
      if (response.data.success) {
        setOutput((prev) => prev + `浏览器已打开，URL: ${response.data.url || '未知'}\n\n`);
      } else {
        setError(response.data.message || "打开浏览器失败");
        setOutput((prev) => prev + `错误: ${response.data.message || "打开浏览器失败"}\n\n`);
      }
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "打开浏览器失败";
      setError(errorMsg);
      setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "#f5f5f5" }}>
        <Typography variant="body1">Loading...</Typography>
      </Box>
    );
  }

  if (!loggedIn) {
    return <Login onLogin={handleLogin} />;
  }

  // Admin UI
  if (userType === "admin") {
    return (
      <ThemeProvider theme={theme}>
        <Box sx={{ bgcolor: "#f5f5f5", minHeight: "100vh" }}>
          <AppBar position="static" sx={{ bgcolor: "#1976d2" }}>
            <Toolbar>
              <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
                <Typography variant="subtitle1" component="div">
                  管理员面板（{username}）
                </Typography>
                <Tooltip title="功能说明">
                  <IconButton 
                    color="inherit" 
                    onClick={() => setFeatureGuideOpen(true)}
                    sx={{ ml: 1 }}
                  >
                    <InfoIcon />
                  </IconButton>
                </Tooltip>
              </Box>
              <Button color="inherit" onClick={handleLogout}>
                退出登录
              </Button>
            </Toolbar>
          </AppBar>
          
          <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
            <Tabs value={adminTab} onChange={(e, newValue) => setAdminTab(newValue)}>
              <Tab label="玩家管理" />
              <Tab label="系统控制" />
            </Tabs>
          </Box>
          
          {adminTab === 0 && (
            <Box sx={{ display: "flex", p: 2 }}>
              <AdminPanel
              username={username}
              onSelectPlayer={handleSelectPlayer}
              selectedPlayerEmail={selectedPlayerEmail}
              selectedAccounts={playerAccounts}
              selected={selectedPlayerAccounts}
              onSelectAccount={handleSelectPlayerAccount}
              onSelectAllAccounts={handleSelectAllPlayerAccounts}
              onRefreshPlayerAccounts={handleRefreshPlayerAccounts}
              onAddAccount={handleAdminAddAccount}
              onOpenSettings={handleAdminOpenSettings}
              onDeleteAccounts={handleAdminDeleteAccounts}
              onOpenBrowser={handleAdminOpenBrowser}
              onOpenGlobalSettings={() => {
                if (!selectedPlayerEmail) {
                  setError("请先选择一个玩家");
                  return;
                }
                setGlobalSettingsOpen(true);
              }}
            />
            
            {selectedPlayerEmail && (
              <OutputWindow
                output={output}
                advanced={advanced}
                onGetInfo={async () => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  setOutput("");
                  let failedAccounts = [];
                  for (let accName of selectedPlayerAccounts) {
                    try {
                      const res = await api.getInfo(selectedPlayerEmail, accName, true);
                      setOutput((prev) => prev + `[${accName}]\n` + JSON.stringify(res.data.info, null, 2) + "\n\n");
                    } catch (e) {
                      failedAccounts.push(accName);
                      let errorMsg = "";
                      if (!e.response) {
                        errorMsg = "无法连接到服务器";
                      } else if (e.response.status === 404) {
                        errorMsg = "账号不存在或Cookie已过期";
                      } else if (e.response.status === 500) {
                        errorMsg = "服务器内部错误";
                      } else {
                        errorMsg = e.response?.data?.detail || e.message;
                      }
                      setOutput((prev) => prev + `[${accName}] 获取信息失败: ${errorMsg}\n\n`);
                    }
                  }
                }}
                onGetDuelInfo={async () => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  setOutput("");
                  let failedAccounts = [];
                  for (let accName of selectedPlayerAccounts) {
                    try {
                      const res = await api.getDuelInfo(selectedPlayerEmail, accName, true);
                      setOutput((prev) => prev + `[${accName}] 跨服竞技场信息\n` + JSON.stringify(res.data.info, null, 2) + "\n\n");
                    } catch (e) {
                      failedAccounts.push(accName);
                      let errorMsg = "";
                      if (!e.response) {
                        errorMsg = "无法连接到服务器";
                      } else if (e.response.status === 404) {
                        errorMsg = "账号不存在或Cookie已过期";
                      } else if (e.response.status === 500) {
                        errorMsg = "服务器内部错误";
                      } else {
                        errorMsg = e.response?.data?.detail || e.message;
                      }
                      setOutput((prev) => prev + `[${accName}] 跨服信息获取失败: ${errorMsg}\n\n`);
                    }
                  }
                }}
                onHallCombat={() => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  streamHallCombat(selectedPlayerEmail, selectedPlayerAccounts, setOutput, setMissingHallDialogOpen, setMissingHallAccounts, playerAccounts, true);
                }}
                onStopCombat={async () => {
                  stopAllStreams();
                  try {
                    const res = await api.stopCombat(selectedPlayerEmail);
                    if (res.data.success) {
                      for (let accName of selectedPlayerAccounts) {
                        setOutput((prev) => prev + `[${accName}] 停止挑战: {\n  "success": true,\n  "message": "Combat stopped successfully"\n}\n\n`);
                      }
                      setOutput((prev) => prev + `停止挑战详情: ` + JSON.stringify(res.data, null, 2) + "\n\n");
                    }
                  } catch (e) {
                    const errorMsg = e.response?.data?.detail || e.message || "停止挑战失败";
                    for (let accName of selectedPlayerAccounts) {
                      setOutput((prev) => prev + `[${accName}] 停止挑战失败: ${errorMsg}\n\n`);
                    }
                  }
                }}
                onViewLastRun={() => {
                  if (!selectedPlayerEmail) {
                    setError("请先选择一个玩家");
                    return;
                  }
                  const accountsToUse = selectedPlayerAccounts.length > 0 ? selectedPlayerAccounts : playerAccounts.map(acc => acc.name);
                  streamResumeStream(selectedPlayerEmail, accountsToUse, setOutput, setError, true);
                }}
                onHallChallenge={(hallName) => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择一个账号进行幻境挑战");
                    return;
                  }
                  setOutput("");
                  streamHallChallenge(selectedPlayerEmail, selectedPlayerAccounts, hallName, setOutput, setError, true);
                }}
                onOpenLogViewer={() => {
                  if (!selectedPlayerEmail) {
                    setError("请先选择一个玩家");
                    return;
                  }
                  setLogViewerOpen(true);
                }}
                selectedCount={selectedPlayerAccounts.length}
                username={selectedPlayerEmail}
                selected={selectedPlayerAccounts}
                onOpenExecuteCommand={() => {
                  setExecuteCommandOpen(true);
                }}
                onExecuteCommand={async (command, id, isDuelCommand = false) => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  try {
                    const commandPrefix = isDuelCommand ? '[跨服] ' : '';
                    setOutput((prev) => prev + `${commandPrefix}执行命令 "${command}"${id ? ` (ID: ${id})` : ''} 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                    const response = await api.executeCommand(selectedPlayerEmail, selectedPlayerAccounts, command, id, isDuelCommand, true);
                    const result = response.data;
                    const formattedOutput = formatCommandResults(result.results);
                    setOutput((prev) => prev + formattedOutput + "\n");
                  } catch (e) {
                    const errorMsg = e.response?.data?.detail || e.message || "命令执行失败";
                    setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                    setError(errorMsg);
                  }
                }}
                onOlympics={async (matchType) => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  try {
                    setOutput((prev) => prev + `报名比赛 "${matchType}" 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                    const response = await api.olympics(selectedPlayerEmail, selectedPlayerAccounts, matchType, true);
                    const result = response.data;
                    const formattedOutput = formatCommandResults(result.results);
                    setOutput((prev) => prev + formattedOutput + "\n");
                  } catch (e) {
                    const errorMsg = e.response?.data?.detail || e.message || "报名比赛失败";
                    setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                    setError(errorMsg);
                  }
                }}
                onZonghengChallenge={async () => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  try {
                    setOutput((prev) => prev + `执行纵横天下挑战对 ${selectedPlayerAccounts.length} 个账号...\n`);
                    const response = await api.zonghengChallenge(selectedPlayerEmail, selectedPlayerAccounts, true);
                    const result = response.data;
                    const formattedOutput = formatCommandResults(result.results);
                    setOutput((prev) => prev + formattedOutput + "\n");
                  } catch (e) {
                    const errorMsg = e.response?.data?.detail || e.message || "纵横天下挑战失败";
                    setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                    setError(errorMsg);
                  }
                }}
                onLottery={(lotteryType) => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  setSelectedLotteryType(lotteryType);
                  setLotteryDialogOpen(true);
                }}
                onBuyDuelMedal={async (bigPackage = true) => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  try {
                    const packageType = bigPackage ? "大" : "单个";
                    setOutput((prev) => prev + `买通用徽章礼包(${packageType}) 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                    const response = await api.buyDuelMedal(selectedPlayerEmail, selectedPlayerAccounts, bigPackage, true);
                    const result = response.data;
                    const formattedOutput = formatCommandResults(result.results);
                    setOutput((prev) => prev + formattedOutput + "\n");
                  } catch (e) {
                    const errorMsg = e.response?.data?.detail || e.message || "买通用徽章失败";
                    setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                    setError(errorMsg);
                  }
                }}
                onFanBadge={() => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  setFanBadgeDialogOpen(true);
                }}
                onAutoGift={async () => {
                  if (selectedPlayerAccounts.length === 0) {
                    setError("请先选择账号");
                    return;
                  }
                  try {
                    setOutput((prev) => prev + `领取礼包 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                    const response = await api.autoGift(selectedPlayerEmail, selectedPlayerAccounts, true);
                    const result = response.data;
                    const formattedOutput = formatCommandResults(result.results);
                    setOutput((prev) => prev + formattedOutput + "\n");
                  } catch (e) {
                    const errorMsg = e.response?.data?.detail || e.message || "领取礼包失败";
                    setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                    setError(errorMsg);
                  }
                }}
              />
            )}
            </Box>
          )}
          
          {adminTab === 1 && (
            <ShutdownControl />
          )}

          {/* Dialogs for admin */}
          <AddAccountDialog
            open={addOpen}
            onClose={() => setAddOpen(false)}
            onSave={handleAdminSaveAccount}
          />

          <SettingsDialog
            open={settingsOpen}
            onClose={() => setSettingsOpen(false)}
            account={settingsAcc}
            onSave={handleAdminSaveSettings}
          />

          <ExecuteCommandDialog
            open={executeCommandOpen}
            onClose={() => setExecuteCommandOpen(false)}
            onExecute={async (command, id, isDuelCommand) => {
              if (selectedPlayerAccounts.length === 0) {
                setError("请先选择账号");
                return;
              }
              try {
                const commandPrefix = isDuelCommand ? '[跨服] ' : '';
                setOutput((prev) => prev + `${commandPrefix}执行命令 "${command}"${id ? ` (ID: ${id})` : ''} 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                const response = await api.executeCommand(selectedPlayerEmail, selectedPlayerAccounts, command, id, isDuelCommand, true);
                const result = response.data;
                const formattedOutput = formatCommandResults(result.results);
                setOutput((prev) => prev + formattedOutput + "\n");
                setExecuteCommandOpen(false);
              } catch (e) {
                const errorMsg = e.response?.data?.detail || e.message || "命令执行失败";
                setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                setError(errorMsg);
              }
            }}
            selectedCount={selectedPlayerAccounts.length}
          />

          <FanBadgeDialog
            open={fanBadgeDialogOpen}
            onClose={() => setFanBadgeDialogOpen(false)}
            onSubmit={async (badge, quantity) => {
              if (selectedPlayerAccounts.length === 0) {
                setError("请先选择账号");
                return;
              }
              try {
                setOutput((prev) => prev + `粉丝章兑换: ${badge.name} x${quantity} 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                const response = await api.exchangeFanBadge(selectedPlayerEmail, selectedPlayerAccounts, badge, quantity, true);
                const result = response.data;
                const formattedOutput = formatCommandResults(result.results);
                setOutput((prev) => prev + formattedOutput + "\n");
              } catch (e) {
                const errorMsg = e.response?.data?.detail || e.message || "粉丝章兑换失败";
                setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                setError(errorMsg);
              }
            }}
            selectedCount={selectedPlayerAccounts.length}
            username={selectedPlayerEmail}
            selected={selectedPlayerAccounts}
            isAdmin={true}
          />

          <LotteryDialog
            open={lotteryDialogOpen}
            onClose={() => {
              setLotteryDialogOpen(false);
              setSelectedLotteryType(null);
            }}
            onSubmit={async (lotteryNumbers) => {
              if (selectedPlayerAccounts.length === 0) {
                setError("请先选择账号");
                return;
              }
              try {
                setOutput((prev) => prev + `联赛竞猜 "${selectedLotteryType}" 号码 "${lotteryNumbers}" 对 ${selectedPlayerAccounts.length} 个账号...\n`);
                const response = await api.lottery(selectedPlayerEmail, selectedPlayerAccounts, selectedLotteryType, lotteryNumbers, true);
                const result = response.data;
                const formattedOutput = formatCommandResults(result.results);
                setOutput((prev) => prev + formattedOutput + "\n");
              } catch (e) {
                const errorMsg = e.response?.data?.detail || e.message || "联赛竞猜失败";
                setOutput((prev) => prev + `错误: ${errorMsg}\n\n`);
                setError(errorMsg);
              }
            }}
            selectedCount={selectedPlayerAccounts.length}
            lotteryType={selectedLotteryType}
          />

          <LogViewerDialog
            open={logViewerOpen}
            onClose={() => setLogViewerOpen(false)}
            username={selectedPlayerEmail || username}
          />

          <InfoDialogs
            missingHallDialogOpen={missingHallDialogOpen}
            setMissingHallDialogOpen={setMissingHallDialogOpen}
            missingHallAccounts={missingHallAccounts}
            missingAccountsDialogOpen={missingAccountsDialogOpen}
            setMissingAccountsDialogOpen={setMissingAccountsDialogOpen}
            missingAccounts={missingAccounts}
          />

          <GlobalSettingsDialog
            open={globalSettingsOpen}
            onClose={() => setGlobalSettingsOpen(false)}
            username={selectedPlayerEmail || username}
            accounts={playerAccounts}
            selectedAccounts={selectedPlayerAccounts}
            isAdmin={true}
          />

          <FeatureGuide open={featureGuideOpen} onClose={() => setFeatureGuideOpen(false)} />
        </Box>
      </ThemeProvider>
    );
  }

  // Player UI (existing code)
  return (
    <ThemeProvider theme={theme}>
      <Box sx={{ bgcolor: "#f5f5f5", minHeight: "100vh" }}>
        <AppBar position="static" sx={{ bgcolor: "#1976d2" }}>
        <Toolbar>
          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
            <Typography variant="subtitle1" component="div">
            武林英雄离线助手（{username}）
            </Typography>
            <Tooltip title="刷新缓存">
              <IconButton 
                color="inherit" 
                onClick={handleRefreshCache}
                sx={{ ml: 1 }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="全局设置">
              <IconButton 
                color="inherit" 
                onClick={handleOpenGlobalSettings}
                sx={{ ml: 1 }}
              >
                <SettingsIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="功能说明">
              <IconButton 
                color="inherit" 
                onClick={() => setFeatureGuideOpen(true)}
                sx={{ ml: 1 }}
              >
                <InfoIcon />
              </IconButton>
            </Tooltip>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Connection Status Indicator */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1, border: '1px solid rgba(255,255,255,0.3)', borderRadius: 1 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  bgcolor: connectionStatus === 'connected' ? 'success.main' : 
                           connectionStatus === 'error' ? 'error.main' : 
                           connectionStatus === 'testing' ? 'warning.main' : 'grey.500',
                  border: '2px solid white',
                  boxShadow: '0 0 4px rgba(0,0,0,0.3)'
                }}
              />
              <Typography variant="caption" sx={{ color: 'white', fontWeight: 'bold' }}>
                {connectionStatus === 'connected' ? '已连接' :
                 connectionStatus === 'error' ? '连接错误' :
                 connectionStatus === 'testing' ? '测试中' : '未知'}
              </Typography>
              {connectionError && (
                <Tooltip title={connectionError}>
                  <IconButton size="small" onClick={testConnection} sx={{ color: 'white' }}>
                    <RefreshIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
            
            {/* Hall Combat Status */}
            {hallCombatInfo && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1, border: '1px solid rgba(255,255,255,0.3)', borderRadius: 1, bgcolor: 'rgba(255,255,255,0.1)' }}>
                <Typography variant="caption" sx={{ color: 'white', fontWeight: 'bold', fontSize: '0.7rem' }}>
                  战斗状态:
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: hallCombatInfo.active_threads > 0 ? 'success.main' : 'warning.main'
                    }}
                  />
                  <Typography variant="caption" sx={{ color: 'white', fontSize: '0.7rem' }}>
                    {hallCombatInfo.active_threads}/{hallCombatInfo.total_threads} 线程
                  </Typography>
                </Box>
                <Typography variant="caption" sx={{ color: 'white', opacity: 0.8, fontSize: '0.7rem' }}>
                  {Math.floor(hallCombatInfo.duration / 60)}分{Math.floor(hallCombatInfo.duration % 60)}秒
                </Typography>
              </Box>
            )}
            
            {/* Active Connections Count */}
            {activeConnections > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1, border: '1px solid rgba(255,255,255,0.3)', borderRadius: 1, bgcolor: 'rgba(255,255,255,0.1)' }}>
                <Typography variant="caption" sx={{ color: 'white', fontWeight: 'bold', fontSize: '0.7rem' }}>
                  活跃连接: {activeConnections}
                </Typography>
              </Box>
            )}
            {/* Error Display */}
            {error && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" sx={{ color: 'error.light', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '0.7rem' }}>
                  {error}
                </Typography>
                <IconButton 
                  size="small" 
                  onClick={() => setError("")} 
                  sx={{ color: 'error.light' }}
                >
                  <CloseIcon fontSize="small" />
                </IconButton>
              </Box>
            )}
            <Button color="inherit" onClick={handleLogout}>
              退出登录
            </Button>
          </Box>
        </Toolbar>
      </AppBar>
      
      {/* Hall Combat Info Display - Below the blue banner */}
      {hallCombatInfo && (
        <Box sx={{ p: 2, bgcolor: '#f5f5f5', borderBottom: '1px solid #ddd' }}>
          <Box sx={{ p: 2, border: '1px solid #ddd', borderRadius: 1, bgcolor: '#f9f9f9' }}>
            <Typography variant="subtitle1" sx={{ mb: 2, color: 'primary.main' }}>
              战斗状态详情
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 3 }}>
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
                  线程状态
                </Typography>
                <Typography variant="body2">
                  {hallCombatInfo.active_threads} / {hallCombatInfo.total_threads} 活跃
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
                  运行时间
                </Typography>
                <Typography variant="body2">
                  {Math.floor(hallCombatInfo.duration / 3600)}小时 {Math.floor((hallCombatInfo.duration % 3600) / 60)}分钟 {Math.floor(hallCombatInfo.duration % 60)}秒
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
                  开始时间
                </Typography>
                <Typography variant="body2">
                  {new Date(hallCombatInfo.start_time).toLocaleString('zh-CN')}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
                  状态
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: hallCombatInfo.active_threads > 0 ? 'success.main' : 'warning.main'
                    }}
                  />
                  <Typography variant="body2">
                    {hallCombatInfo.active_threads > 0 ? '运行中' : '等待中'}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </Box>
        </Box>
      )}
      
      <Box sx={{ display: "flex", p: 2 }}>
        <Box sx={{ p: 3 }}>
          <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
            <Button variant="contained" onClick={handleAddAccount}>
              添加账号
            </Button>
            <Button 
              variant="outlined" 
              onClick={handleDeleteAccounts}
              disabled={selected.length === 0}
            >
              删除选中
            </Button>
            <Button 
              variant="outlined" 
              onClick={testConnection}
              color={connectionStatus === 'error' ? 'error' : 'primary'}
            >
              测试连接
            </Button>
          </Box>
          <AccountList
            accounts={accounts}
            selected={selected}
            onSelect={handleSelect}
            onSelectAll={handleSelectAll}
            onRefresh={() => fetchAccounts(username)}
            onAddAccount={handleAddAccount}
            onDeleteAccounts={handleDeleteAccounts}
            onOpenSettings={handleOpenSettings}
          />
        </Box>
        
        <OutputWindow
          output={output}
          advanced={advanced}
          onGetInfo={handleGetInfo}
          onGetDuelInfo={handleGetDuelInfo}
          onHallCombat={handleHallCombat}
          onStopCombat={handleStopCombat}
          onViewLastRun={handleViewLastRun}
          onOpenLogViewer={handleOpenLogViewer}
          selectedCount={selected.length}
          onHallChallenge={handleHallChallenge}
          username={username}
          selected={selected}
          onOpenExecuteCommand={handleOpenExecuteCommand}
          onOlympics={handleOlympics}
          onZonghengChallenge={handleZonghengChallenge}
          onLottery={handleLottery}
          onBuyDuelMedal={handleBuyDuelMedal}
          onFanBadge={handleOpenFanBadgeDialog}
          onAutoGift={handleAutoGift}
        />
      </Box>

      {/* Dialogs */}
      <AddAccountDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSave={handleSaveAccount}
      />

      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        account={settingsAcc}
        onSave={handleSaveSettings}
      />

      <GlobalSettingsDialog
        open={globalSettingsOpen}
        onClose={() => setGlobalSettingsOpen(false)}
        username={username}
        accounts={accounts}
        selectedAccounts={selected}
      />

      <LogViewerDialog
        open={logViewerOpen}
        onClose={() => setLogViewerOpen(false)}
        username={username}
      />

      <ExecuteCommandDialog
        open={executeCommandOpen}
        onClose={() => setExecuteCommandOpen(false)}
        onExecute={handleExecuteCommand}
        selectedCount={selected.length}
      />

      <FanBadgeDialog
        open={fanBadgeDialogOpen}
        onClose={() => setFanBadgeDialogOpen(false)}
        onSubmit={handleFanBadgeSubmit}
        selectedCount={selected.length}
        username={username}
        selected={selected}
      />

      <LotteryDialog
        open={lotteryDialogOpen}
        onClose={() => {
          setLotteryDialogOpen(false);
          setSelectedLotteryType(null);
        }}
        onSubmit={handleLotterySubmit}
        selectedCount={selected.length}
        lotteryType={selectedLotteryType}
      />

      <InfoDialogs
        missingHallDialogOpen={missingHallDialogOpen}
        setMissingHallDialogOpen={setMissingHallDialogOpen}
        missingHallAccounts={missingHallAccounts}
        missingAccountsDialogOpen={missingAccountsDialogOpen}
        setMissingAccountsDialogOpen={setMissingAccountsDialogOpen}
        missingAccounts={missingAccounts}
      />

      <FeatureGuide open={featureGuideOpen} onClose={() => setFeatureGuideOpen(false)} />
      </Box>
    </ThemeProvider>
  );
}

export default App;
