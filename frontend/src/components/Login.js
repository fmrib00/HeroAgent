import React, { useState } from "react";
import {
  Box, Paper, Typography, Button, TextField, Alert, Dialog, DialogTitle, DialogContent, DialogActions, Divider
} from "@mui/material";
import InfoIcon from '@mui/icons-material/Info';
import { useGoogleLogin } from '@react-oauth/google';
import { api } from "../utils/api";
import FeatureGuide from "./FeatureGuide";

function Login({ onLogin }) {
  const [mode, setMode] = useState("login"); // 'login' or 'register'
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [registerOpen, setRegisterOpen] = useState(false);
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerError, setRegisterError] = useState("");
  const [registerSuccess, setRegisterSuccess] = useState("");
  const [featureGuideOpen, setFeatureGuideOpen] = useState(false);

  // Check if Google OAuth is configured
  const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || '';
  const isGoogleOAuthEnabled = !!GOOGLE_CLIENT_ID;

  const handleGoogleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setError("");
      setSuccess("");
      try {
        // Send Google token to backend for verification and login
        const response = await api.loginWithGoogle(tokenResponse.access_token);
        // Store the JWT token
        if (response.data.access_token) {
          localStorage.setItem('access_token', response.data.access_token);
        }
        // Get user info from response
        const userEmail = response.data.email || response.data.username;
        const userType = response.data.user_type || 'player';
        const advanced = response.data.advanced || false;
        localStorage.setItem('user_type', userType);
        localStorage.setItem('advanced', advanced.toString());
        onLogin(userEmail, userType, advanced);
      } catch (e) {
        // Handle Google login errors
        if (!e.response) {
          setError("无法连接到服务器，请检查网络连接或稍后重试");
        } else if (e.response.status === 401) {
          setError("Google登录失败，请重试");
        } else {
          const detail = e.response?.data?.detail;
          setError(typeof detail === 'string' ? detail : "Google登录失败，请稍后重试");
        }
      }
    },
    onError: (error) => {
      console.error("Google login error:", error);
      if (!isGoogleOAuthEnabled) {
        setError("Google登录未配置，请在环境变量中设置 REACT_APP_GOOGLE_CLIENT_ID");
      } else {
        setError("Google登录失败，请重试");
      }
    },
  });

  const handleAuth = async () => {
    setError(""); 
    setSuccess("");
    try {
      if (mode === "login") {
        const response = await api.login(username, password);
        // Store the JWT token
        if (response.data.access_token) {
          localStorage.setItem('access_token', response.data.access_token);
        }
        // Get user_type from response (default to 'player' for backward compatibility)
        const userType = response.data.user_type || 'player';
        // Get advanced field from response (default to false for backward compatibility)
        const advanced = response.data.advanced || false;
        localStorage.setItem('user_type', userType);
        localStorage.setItem('advanced', advanced.toString());
        onLogin(username, userType, advanced);
      } else {
        await api.register(username);
        setSuccess("Registration successful! Please check your email for the password.");
        setMode("login");
      }
    } catch (e) {

      
      // Provide more specific error messages based on the error type
      if (!e.response) {
        // Network error - server is down or no connection
        if (e.message && e.message.includes('SSL证书验证失败')) {
          setError("SSL证书验证失败，请联系管理员检查服务器证书配置");
        } else if (e.message && e.message.includes('连接被服务器重置')) {
          setError("连接被服务器重置，请检查服务器状态或稍后重试");
        } else if (e.message && e.message.includes('混合内容错误')) {
          setError("混合内容错误：前端使用HTTPS但后端使用HTTP，请联系管理员配置HTTPS");
        } else if (e.message && e.message.includes('无法连接到服务器')) {
          setError("无法连接到服务器，请检查网络连接或稍后重试");
        } else if (e.message && e.message.includes('网络错误')) {
          setError("网络错误，请检查网络连接或稍后重试");
        } else {
          setError("无法连接到服务器，请检查网络连接或稍后重试");
        }
      } else if (e.response.status === 401) {
        // Authentication failed - check for specific error details
        if (e.response?.data?.detail === "Account expired") {
          setError("账号已过期，请联系管理员续费");
        } else {
          setError("邮箱或密码错误，请检查后重试");
        }
      } else if (e.response.status === 422) {
        // Validation error - handle Pydantic validation errors
        const detail = e.response?.data?.detail;
        if (Array.isArray(detail)) {
          // Multiple validation errors
          const errorMessages = detail.map(err => err.msg || err.message || 'Validation error').join(', ');
          setError(`输入验证失败: ${errorMessages}`);
        } else if (typeof detail === 'string') {
          setError(detail);
        } else {
          setError("输入数据格式不正确，请检查后重试");
        }
      } else if (e.response.status === 500) {
        // Server error
        setError("服务器内部错误，请稍后重试");
      } else if (e.response.status === 503) {
        // Service unavailable
        setError("服务暂时不可用，请稍后重试");
      } else {
        // Other errors - use server message if available
        const detail = e.response?.data?.detail;
        if (typeof detail === 'string') {
          setError(detail);
        } else {
          setError("登录失败，请稍后重试");
        }
      }
    }
  };

  const handleRegister = async () => {
    setRegisterError(""); 
    setRegisterSuccess("");
    if (!registerEmail) { 
      setRegisterError("请输入邮箱"); 
      return; 
    }
    try {
      await api.register(registerEmail);
      setRegisterSuccess("注册成功！请查收邮箱获取密码。");
    } catch (e) {
      // Provide more specific error messages for registration
      if (!e.response) {
        // Network error - server is down or no connection
        if (e.message && e.message.includes('SSL证书验证失败')) {
          setRegisterError("SSL证书验证失败，请联系管理员检查服务器证书配置");
        } else if (e.message && e.message.includes('连接被服务器重置')) {
          setRegisterError("连接被服务器重置，请检查服务器状态或稍后重试");
        } else if (e.message && e.message.includes('混合内容错误')) {
          setRegisterError("混合内容错误：前端使用HTTPS但后端使用HTTP，请联系管理员配置HTTPS");
        } else if (e.message && e.message.includes('无法连接到服务器')) {
          setRegisterError("无法连接到服务器，请检查网络连接或稍后重试");
        } else if (e.message && e.message.includes('网络错误')) {
          setRegisterError("网络错误，请检查网络连接或稍后重试");
        } else {
          setRegisterError("无法连接到服务器，请检查网络连接或稍后重试");
        }
      } else if (e.response.status === 400) {
        // Bad request - usually validation error
        const detail = e.response?.data?.detail;
        if (typeof detail === 'string') {
          setRegisterError(detail);
        } else {
          setRegisterError("邮箱格式不正确或已被注册");
        }
      } else if (e.response.status === 422) {
        // Validation error - handle Pydantic validation errors
        const detail = e.response?.data?.detail;
        if (Array.isArray(detail)) {
          // Multiple validation errors
          const errorMessages = detail.map(err => err.msg || err.message || 'Validation error').join(', ');
          setRegisterError(`输入验证失败: ${errorMessages}`);
        } else if (typeof detail === 'string') {
          setRegisterError(detail);
        } else {
          setRegisterError("输入数据格式不正确，请检查后重试");
        }
      } else if (e.response.status === 500) {
        // Server error
        setRegisterError("服务器内部错误，请稍后重试");
      } else if (e.response.status === 503) {
        // Service unavailable
        setRegisterError("服务暂时不可用，请稍后重试");
      } else {
        // Other errors - use server message if available
        const detail = e.response?.data?.detail;
        if (typeof detail === 'string') {
          setRegisterError(detail);
        } else {
          setRegisterError("注册失败，请稍后重试");
        }
      }
    }
  };

  return (
    <Box sx={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "#f5f5f5" }}>
      <Paper sx={{ p: 4, minWidth: 320, position: "relative" }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
          <Typography variant="h6">武林英雄离线助手</Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={<InfoIcon />}
            onClick={() => setFeatureGuideOpen(true)}
            sx={{ ml: 1 }}
          >
            功能说明
          </Button>
        </Box>
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}
        <TextField 
          label="邮箱" 
          fullWidth 
          margin="normal" 
          value={username} 
          onChange={e => setUsername(e.target.value)} 
        />
        <TextField 
          label="密码" 
          type="password" 
          fullWidth 
          margin="normal" 
          value={password} 
          onChange={e => setPassword(e.target.value)} 
        />
        <Button 
          variant="contained" 
          fullWidth 
          sx={{ mt: 2 }} 
          onClick={handleAuth}
        >
          {"登录"}
        </Button>
        
        <Box sx={{ display: 'flex', alignItems: 'center', my: 2 }}>
          <Divider sx={{ flexGrow: 1 }} />
          <Typography variant="body2" sx={{ px: 2, color: 'text.secondary' }}>
            或
          </Typography>
          <Divider sx={{ flexGrow: 1 }} />
        </Box>
        
        <Button 
          variant="outlined" 
          fullWidth 
          disabled={!isGoogleOAuthEnabled}
          sx={{ 
            mt: 1,
            borderColor: '#4285f4',
            color: '#4285f4',
            '&:hover': {
              borderColor: '#357ae8',
              backgroundColor: 'rgba(66, 133, 244, 0.04)'
            },
            '&:disabled': {
              borderColor: '#ccc',
              color: '#999'
            }
          }}
          onClick={() => {
            if (!isGoogleOAuthEnabled) {
              setError("Google登录未配置，请在环境变量中设置 REACT_APP_GOOGLE_CLIENT_ID");
              return;
            }
            handleGoogleLogin();
          }}
          startIcon={
            <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
              <g fill="#000" fillRule="evenodd">
                <path d="M9 3.48c1.69 0 2.83.73 3.48 1.34l2.54-2.48C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.96l2.91 2.26C4.6 5.05 6.62 3.48 9 3.48z" fill="#EA4335"/>
                <path d="M17.64 9.2c0-.74-.06-1.28-.19-1.84H9v3.34h4.96c-.21 1.18-.84 2.18-1.79 2.91l2.84 2.2c1.7-1.57 2.68-3.88 2.68-6.61z" fill="#4285F4"/>
                <path d="M3.88 10.78A5.54 5.54 0 0 1 3.58 9c0-.62.11-1.22.29-1.78L.96 4.96A9.008 9.008 0 0 0 0 9c0 1.45.35 2.82.96 4.04l2.92-2.26z" fill="#FBBC05"/>
                <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.84-2.2c-.76.53-1.78.9-3.12.9-2.38 0-4.4-1.57-5.12-3.74L.96 13.04C2.45 15.98 5.48 18 9 18z" fill="#34A853"/>
              </g>
            </svg>
          }
        >
          使用 Google 登录
        </Button>
        
        <Button 
          variant="text" 
          fullWidth 
          sx={{ mt: 1 }} 
          onClick={() => setRegisterOpen(true)}
        >
          注册
        </Button>
        <Typography variant="caption" color="secondary" align="center" sx={{ mt: 1 }}>
          需要帮助请通过 GitHub Issues 联系
        </Typography>
      </Paper>
      
      <Dialog open={registerOpen} onClose={() => setRegisterOpen(false)}>
        <DialogTitle sx={{ fontSize: '1rem' }}>注册新账号</DialogTitle>
        <DialogContent>
          <TextField 
            label="邮箱" 
            fullWidth 
            margin="normal" 
            value={registerEmail} 
            onChange={e => setRegisterEmail(e.target.value)} 
          />
          {registerError && <Alert severity="error">{registerError}</Alert>}
          {registerSuccess && <Alert severity="success">{registerSuccess}</Alert>}
          <Box sx={{ fontSize: '0.75rem', color: 'gray', mt: 1 }}>
            注册后，系统会自动生成密码并发送到您的邮箱。
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRegisterOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleRegister}>注册</Button>
        </DialogActions>
      </Dialog>

      <FeatureGuide open={featureGuideOpen} onClose={() => setFeatureGuideOpen(false)} />
    </Box>
  );
}

export default Login; 