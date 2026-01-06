import React, { useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Box,
  Tabs, Tab, CircularProgress, Alert, AlertTitle
} from "@mui/material";
import { COOKIE_HELP_TEXT } from "../utils/constants";
import { cleanCookieValue, composeCookie, parseCookie } from "../utils/cookieUtils";
import { api } from "../utils/api";
import { logger } from "../utils/logger";

// Helper function to normalize URLs - add http:// if missing
const normalizeUrl = (url) => {
  if (!url || !url.trim()) {
    return url;
  }
  
  const trimmedUrl = url.trim();
  
  // If URL doesn't start with http:// or https://, add http://
  if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
    return 'http://' + trimmedUrl;
  }
  
  return trimmedUrl;
};

function AddAccountDialog({ open, onClose, onSave }) {
  const [newAcc, setNewAcc] = useState({ 
    name: "", 
    cookie: "", 
    url: "", 
    weeCookie: "", 
    heroSession: "" 
  });
  const [cookieMethod, setCookieMethod] = useState(0); // 0 = automated (default), 1 = manual
  const [gameAccount, setGameAccount] = useState(""); // Game account/passport for login
  const [gamePassword, setGamePassword] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState(null);
  const [extractionSuccess, setExtractionSuccess] = useState(false);

  const handleExtractCookies = async () => {
    if (!gameAccount || !gamePassword) {
      setExtractionError("请输入游戏通行证和密码");
      return;
    }

    setExtracting(true);
    setExtractionError(null);
    setExtractionSuccess(false);

    // Get user email for logging
    const userEmail = localStorage.getItem('hero_email') || null;
    const accountName = newAcc.name || '未命名账号';
    const normalizedUrl = newAcc.url ? normalizeUrl(newAcc.url) : null;

    // Log cookie extraction start
    logger.info(`提取 Cookie: 账号=${accountName}, 游戏通行证=${gameAccount}, URL=${normalizedUrl || 'default'}`, {
      userId: userEmail,
      userEmail: userEmail,
      accountName: accountName,
      gameAccount: gameAccount,
      url: normalizedUrl,
      action: 'extract_cookies_start'
    });

    try {
      // Normalize URL before sending to API
      const result = await api.extractCookies(gameAccount, gamePassword, normalizedUrl, 60);
      
      if (result.data.success) {
        // Parse the cookie string to extract components
        const parsed = parseCookie(result.data.cookie_string);
        
        // Set default URL if not already set
        const url = newAcc.url || parsed.url || "https://hero.9wee.com";
        
        // Extract cookie values - prefer separate fields, fallback to parsed values
        const weeCookie = result.data.weeCookie || parsed.weeCookie || "";
        const heroSession = result.data["50hero_session"] || parsed.heroSession || "";
        
        // Update state with extracted cookies
        setNewAcc({
          ...newAcc,
          url: url,
          weeCookie: weeCookie,
          heroSession: heroSession
        });
        
        setExtractionSuccess(true);
        setExtractionError(null);
        
        // Log successful cookie extraction
        logger.info(`提取 Cookie 成功: 账号=${accountName}, 游戏通行证=${gameAccount}`, {
          userId: userEmail,
          userEmail: userEmail,
          accountName: accountName,
          gameAccount: gameAccount,
          url: url,
          hasWeeCookie: !!weeCookie,
          hasHeroSession: !!heroSession,
          action: 'extract_cookies_success'
        });
        
        // Clear success message after 3 seconds
        setTimeout(() => setExtractionSuccess(false), 3000);
      } else {
        const errorMsg = result.data.error || "Cookie提取失败";
        setExtractionError(errorMsg);
        
        // Log failed cookie extraction
        logger.error(`提取 Cookie 失败: 账号=${accountName}, 游戏通行证=${gameAccount}, 错误=${errorMsg}`, null, {
          userId: userEmail,
          userEmail: userEmail,
          accountName: accountName,
          gameAccount: gameAccount,
          url: normalizedUrl,
          error: errorMsg,
          action: 'extract_cookies_failed'
        });
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message || "Cookie提取失败";
      setExtractionError(errorMsg);
      setExtractionSuccess(false);
      
      // Log cookie extraction error
      logger.error(`提取 Cookie 错误: 账号=${accountName}, 游戏通行证=${gameAccount}, 错误=${errorMsg}`, error, {
        userId: userEmail,
        userEmail: userEmail,
        accountName: accountName,
        gameAccount: gameAccount,
        url: normalizedUrl,
        error: errorMsg,
        action: 'extract_cookies_error'
      });
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!newAcc.url || !newAcc.name || !newAcc.weeCookie || !newAcc.heroSession) return;
    
    // Normalize URL before saving
    const normalizedUrl = normalizeUrl(newAcc.url);
    
    // Clean cookie values
    let weeCookieVal = cleanCookieValue(newAcc.weeCookie, 'weeCookie=');
    let heroSessionVal = cleanCookieValue(newAcc.heroSession, '50hero_session=');
    const combinedCookie = composeCookie(normalizedUrl, weeCookieVal, heroSessionVal);
    
    // Default hall settings for new accounts
    const defaultHallSettings = {
      "封神异志": "",
      "武林群侠传": "",
      "三国鼎立": "",
      "乱世群雄": "",
      "绝代风华": "",
      "复活重打": false,
      "客房补血": false,
      "自动买次数": false,
      "失败切换": true
    };
    
    await onSave({ 
      account_name: newAcc.name, 
      cookie: combinedCookie,
      hall_settings: defaultHallSettings,
      game_id: gameAccount || null,  // Save game ID if provided
      password: gamePassword || null  // Save password if provided
    });
    setNewAcc({ name: '', cookie: '', url: '', weeCookie: '', heroSession: '' });
    setGameAccount("");
    setGamePassword("");
    setCookieMethod(0); // Reset to default (auto extract)
    setExtractionError(null);
    setExtractionSuccess(false);
    onClose();
  };

  const handleClose = () => {
    setNewAcc({ name: '', cookie: '', url: '', weeCookie: '', heroSession: '' });
    setGameAccount("");
    setGamePassword("");
    setCookieMethod(0); // Reset to default (auto extract)
    setExtractionError(null);
    setExtractionSuccess(false);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontSize: '1rem' }}>添加账号</DialogTitle>
      <DialogContent>
        <TextField 
          label="游戏网址" 
          fullWidth 
          margin="normal" 
          value={newAcc.url || ''} 
          onChange={e => {
            const inputValue = e.target.value;
            // Normalize URL when user finishes typing (on blur) or when extracting cookies
            // For now, just store the raw value and normalize when using it
            setNewAcc({ ...newAcc, url: inputValue });
          }}
          onBlur={e => {
            // Normalize URL when user leaves the field
            if (e.target.value) {
              const normalized = normalizeUrl(e.target.value);
              setNewAcc({ ...newAcc, url: normalized });
            }
          }}
          placeholder="https://hero.9wee.com" 
        />
        <TextField 
          label="游戏角色名称" 
          fullWidth 
          margin="normal" 
          value={newAcc.name} 
          onChange={e => setNewAcc({ ...newAcc, name: e.target.value })} 
        />
        
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mt: 2, mb: 2 }}>
          <Tabs value={cookieMethod} onChange={(e, newValue) => setCookieMethod(newValue)}>
            <Tab label="自动提取" />
            <Tab label="手动输入" />
          </Tabs>
        </Box>

        {cookieMethod === 0 ? (
          // Automated cookie extraction
          <>
            <Box sx={{ 
              bgcolor: "#e3f2fd", 
              border: "1px solid #90caf9", 
              borderRadius: 1, 
              p: 2, 
              mb: 2, 
              fontSize: 14 
            }}>
              <b>自动提取 Cookie：</b>
              <ol style={{ paddingLeft: 18, margin: "8px 0 0 0" }}>
                <li>在上方输入游戏角色名称（用于标识账号）</li>
                <li>输入游戏通行证（用于登录游戏）</li>
                <li>输入游戏账号密码</li>
                <li>点击"提取 Cookie"按钮</li>
                <li>系统将自动登录并提取所需的 Cookie</li>
                <li>提取成功后，Cookie 将自动填充到下方字段</li>
              </ol>
            </Box>
            
            <TextField 
              label="游戏通行证" 
              fullWidth 
              margin="normal" 
              value={gameAccount} 
              onChange={e => setGameAccount(e.target.value)} 
              placeholder="输入游戏登录账号"
              disabled={extracting}
            />
            <TextField 
              label="游戏账号密码" 
              fullWidth 
              margin="normal" 
              type="password"
              value={gamePassword} 
              onChange={e => setGamePassword(e.target.value)} 
              placeholder="输入游戏账号密码"
              disabled={extracting}
            />
            
            <Box sx={{ mt: 2, mb: 2 }}>
              <Button 
                variant="outlined" 
                onClick={handleExtractCookies}
                disabled={extracting || !gameAccount || !gamePassword}
                startIcon={extracting ? <CircularProgress size={16} /> : null}
                fullWidth
              >
                {extracting ? "正在提取 Cookie..." : "提取 Cookie"}
              </Button>
            </Box>

            {extractionError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setExtractionError(null)}>
                <AlertTitle>提取失败</AlertTitle>
                {extractionError}
              </Alert>
            )}

            {extractionSuccess && (
              <Alert severity="success" sx={{ mb: 2 }} onClose={() => setExtractionSuccess(false)}>
                Cookie 提取成功！已自动填充到下方字段。
              </Alert>
            )}

            <TextField 
              label="weeCookie 字符串" 
              fullWidth 
              margin="normal" 
              value={newAcc.weeCookie} 
              onChange={e => setNewAcc({ ...newAcc, weeCookie: e.target.value })} 
              placeholder="提取后将自动填充" 
              disabled={extracting}
            />
            <TextField 
              label="50hero_session 字符串" 
              fullWidth 
              margin="normal" 
              value={newAcc.heroSession} 
              onChange={e => setNewAcc({ ...newAcc, heroSession: e.target.value })} 
              placeholder="提取后将自动填充" 
              disabled={extracting}
            />
          </>
        ) : (
          // Manual cookie input
          <>
            <Box sx={{ 
              bgcolor: "#f9f9f9", 
              border: "1px solid #ddd", 
              borderRadius: 1, 
              p: 2, 
              mb: 2, 
              fontSize: 14 
            }}>
              <b>{COOKIE_HELP_TEXT.title}</b>
              <ol style={{ paddingLeft: 18, margin: 0 }}>
                {COOKIE_HELP_TEXT.steps.map((step, index) => (
                  <li key={index}>
                    {step}
                    {index === 4 && (
                      <span style={{ color: "#888" }}>
                        <br/>（点击下面的Cookie Value，全部选择并右键复制，分别粘贴到下方输入框）
                      </span>
                    )}
                  </li>
                ))}
              </ol>
              <div style={{ color: "#888", fontSize: 12, marginTop: 8 }}>
                {COOKIE_HELP_TEXT.note}
              </div>
            </Box>
            <TextField 
              label="weeCookie 字符串" 
              fullWidth 
              margin="normal" 
              value={newAcc.weeCookie} 
              onChange={e => setNewAcc({ ...newAcc, weeCookie: e.target.value })} 
              placeholder="weeCookie=xxxx" 
            />
            <TextField 
              label="50hero_session 字符串" 
              fullWidth 
              margin="normal" 
              value={newAcc.heroSession} 
              onChange={e => setNewAcc({ ...newAcc, heroSession: e.target.value })} 
              placeholder="50hero_session=yyyy" 
            />
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>取消</Button>
        <Button 
          variant="contained" 
          onClick={handleSave}
          disabled={!newAcc.url || !newAcc.name || !newAcc.weeCookie || !newAcc.heroSession}
        >
          保存
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default AddAccountDialog; 