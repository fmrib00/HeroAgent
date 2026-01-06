import { useRef, useEffect } from 'react';
import { api } from '../utils/api';

export function useStreaming() {
  const eventSourcesRef = useRef([]);

  const cleanupEventSources = () => {
    eventSourcesRef.current.forEach(es => {
      if (es && typeof es.close === 'function') es.close();
      if (es && typeof es.abort === 'function') es.abort();
    });
    eventSourcesRef.current = [];
  };

  const stopAllStreams = () => {
    cleanupEventSources();
  };

  const streamResumeStream = async (username, accountNames, setOutput, setError, isAdmin = false) => {
    setOutput("");
    
    // Clean up any previous EventSources
    cleanupEventSources();

    const controller = new AbortController();
    eventSourcesRef.current.push(controller);

    try {
      const res = await api.resumeStream(username, accountNames, isAdmin);
      if (!res.body) return;
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let lines = buffer.split("\n\n");
        buffer = lines.pop(); // last incomplete
        for (let line of lines) {
          if (line.startsWith("data: ")) {
            const msg = line.slice(6);
            setOutput(prev => prev + msg + "\n");
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        if (!error.response) {
          // Check for specific streaming errors
          if (error.message && error.message.includes('ERR_INCOMPLETE_CHUNKED_ENCODING')) {
            setError("流式传输连接中断，请重试。\n提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接");
          } else if (error.message && error.message.includes('ERR_CONNECTION_RESET')) {
            setError("连接被重置，请检查网络连接并重试\n提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接");
          } else {
            setError("无法连接到服务器，请检查网络连接\n提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接");
          }
        } else if (error.response.status === 404) {
          setError("未找到活跃的战斗会话或日志文件");
        } else if (error.response.status === 500) {
          setError("服务器内部错误，请稍后重试");
        } else {
          setError("查看最新日志失败: " + (error.response?.data?.detail || error.message));
        }
      }
    }
  };

  const streamHallCombat = async (username, selected, setOutput, setMissingHallDialogOpen, setMissingHallAccounts, accounts, isAdmin = false) => {
    // Check for missing hall settings
    const missing = accounts.filter(acc => selected.includes(acc.name) && !acc.hall);
    if (missing.length > 0) {
      setMissingHallAccounts(missing.map(acc => acc.name));
      setMissingHallDialogOpen(true);
      return;
    }
    
    setOutput("");
    
    // Clean up any previous EventSources
    cleanupEventSources();

    const controller = new AbortController();
    eventSourcesRef.current.push(controller);

    // Check if there's already an active connection before starting
    try {
      const statusRes = await api.connectionStatus(username);
      console.log('Connection status:', statusRes.data);
      if (statusRes.data.active_connections > 0) {
        const activeRequest = statusRes.data.requests[0];
        console.log('Active request:', activeRequest);
        if (activeRequest.type === 'hall_combat_stream') {
          // Different accounts are running, automatically stop the previous session
          setOutput(`检测到其他账号的战斗会话正在运行 (${activeRequest.accounts.join(', ')})\n`);
          setOutput("正在停止之前的会话...\n");
          
          try {
            await api.stopCombat(username);
            setOutput("之前的会话已停止，开始新的战斗会话...\n");
            
            // Wait a moment for cleanup to complete
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Continue with starting new session instead of returning
          } catch (stopError) {
            setOutput(`停止之前的会话失败: ${stopError.message}\n`);
            setOutput("请手动停止之前的会话后重试\n");
            return;
          }
        }
      }
    } catch (error) {
      // If we can't check status, continue with normal flow
      console.log("Could not check connection status:", error);
      setOutput("无法检查连接状态，开始新的战斗会话...\n");
    }

    // Only start new session if no existing session was found or resumed
    try {
      setOutput("开始新的幻境战斗会话...\n");
      const res = await api.hallCombatStream(username, selected, isAdmin);
      if (!res.body) {
        throw new Error("No response body received");
      }
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let lines = buffer.split("\n\n");
        buffer = lines.pop(); // last incomplete
        for (let line of lines) {
          if (line.startsWith("data: ")) {
            const msg = line.slice(6);
            setOutput(prev => prev + msg + "\n");
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        // Handle authentication errors first
        if (error.message === 'Authentication required') {
          setOutput(prev => prev + "登录已过期，请重新登录\n");
          return;
        }
        
        if (!error.response) {
          // Check for specific streaming errors
          if (error.message && error.message.includes('ERR_INCOMPLETE_CHUNKED_ENCODING')) {
            setOutput(prev => prev + "流式传输连接中断。\n");
            setOutput(prev => prev + "提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接\n");
          } else if (error.message && error.message.includes('ERR_CONNECTION_RESET')) {
            setOutput(prev => prev + "连接被重置。\n");
            setOutput(prev => prev + "提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接\n");
          } else {
            setOutput(prev => prev + "连接失败。\n");
            setOutput(prev => prev + "提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接\n");
          }
        } else if (error.response.status === 401 || error.response.status === 403) {
          setOutput(prev => prev + "登录已过期，请重新登录\n");
        } else if (error.response.status === 409) {
          setOutput(prev => prev + "已有战斗会话正在运行，请等待完成或先停止当前会话\n");
        } else if (error.response.status === 404) {
          setOutput(prev => prev + "未找到有效的游戏账号\n");
        } else if (error.response.status === 500) {
          setOutput(prev => prev + "服务器内部错误，请稍后重试\n");
        } else {
          setOutput(prev => prev + "幻境挑战失败: " + (error.response?.data?.detail || error.message) + "\n");
        }
      }
    }
  };

  const streamHallChallenge = async (username, accountNames, hallName, setOutput, setError, isAdmin = false) => {
    setOutput("");
    
    // Clean up any previous EventSources
    cleanupEventSources();

    const controller = new AbortController();
    eventSourcesRef.current.push(controller);

    try {
      // Use the appropriate API based on number of accounts
      if (Array.isArray(accountNames) && accountNames.length > 1) {
        // Multiple accounts - use the new multiple accounts endpoint
        setOutput(prev => prev + `开始为 ${accountNames.length} 个账号挑战 ${hallName}...\n`);
        const res = await api.hallChallengeMultiple(username, accountNames, hallName, isAdmin);
        
        if (!res.body) {
          throw new Error("No response body received");
        }
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let lines = buffer.split("\n\n");
          buffer = lines.pop(); // last incomplete
          for (let line of lines) {
            if (line.startsWith("data: ")) {
              const msg = line.slice(6);
              setOutput(prev => prev + msg + "\n");
            }
          }
        }
      } else {
        // Single account - use the original single account endpoint
        const accountName = Array.isArray(accountNames) ? accountNames[0] : accountNames;
        const res = await api.hallChallenge(username, accountName, hallName, isAdmin);
        
        if (!res.body) {
          throw new Error("No response body received");
        }
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let lines = buffer.split("\n\n");
          buffer = lines.pop(); // last incomplete
          for (let line of lines) {
            if (line.startsWith("data: ")) {
              const msg = line.slice(6);
              setOutput(prev => prev + msg + "\n");
            }
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        // Handle authentication errors first
        if (error.message === 'Authentication required') {
          setOutput(prev => prev + "登录已过期，请重新登录\n");
          return;
        }
        
        if (!error.response) {
          // Check for specific streaming errors
          if (error.message && error.message.includes('ERR_INCOMPLETE_CHUNKED_ENCODING')) {
            setOutput(prev => prev + "流式传输连接中断。\n");
            setOutput(prev => prev + "提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接\n");
          } else if (error.message && error.message.includes('ERR_CONNECTION_RESET')) {
            setOutput(prev => prev + "连接被重置。\n");
            setOutput(prev => prev + "提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接\n");
          } else {
            setOutput(prev => prev + "连接失败。\n");
            setOutput(prev => prev + "提示：如果后端仍在运行，您可以稍后点击'查看最新日志'来重新连接\n");
          }
        } else if (error.response.status === 401 || error.response.status === 403) {
          setOutput(prev => prev + "登录已过期，请重新登录\n");
        } else if (error.response.status === 409) {
          setOutput(prev => prev + "已有战斗会话正在运行，请等待完成或先停止当前会话\n");
        } else if (error.response.status === 404) {
          setOutput(prev => prev + "未找到有效的游戏账号\n");
        } else if (error.response.status === 500) {
          setOutput(prev => prev + "服务器内部错误，请稍后重试\n");
        } else {
          setOutput(prev => prev + `${hallName}挑战失败: ` + (error.response?.data?.detail || error.message) + "\n");
        }
      }
    }
  };

  // Clean up EventSources on unmount
  useEffect(() => {
    return cleanupEventSources;
  }, []);

  return {
    streamResumeStream,
    streamHallCombat,
    streamHallChallenge,
    cleanupEventSources,
    stopAllStreams
  };
} 