import React, { useState, useEffect } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Box, Checkbox, Tabs, Tab, Typography, Select, MenuItem, FormControl, InputLabel
} from "@mui/material";
import { CheckCircle, Error } from "@mui/icons-material";
import { HALLS } from "../utils/constants";
import { parseCookie, composeCookie } from "../utils/cookieUtils";
import { api } from "../utils/api";

function SettingsDialog({ open, onClose, account, onSave }) {
  const [settingsTab, setSettingsTab] = useState(0);
  const [hallSettings, setHallSettings] = useState({});
  const [commonSettings, setCommonSettings] = useState({});
  const [dungeonSettings, setDungeonSettings] = useState([
    { 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' },
    { 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' },
    { 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' }
  ]);
  const [duelDungeonSettings, setDuelDungeonSettings] = useState([
    { 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' },
    { 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' }
  ]);
  const [editUrl, setEditUrl] = useState("");
  const [editWeeCookie, setEditWeeCookie] = useState("");
  const [editHeroSession, setEditHeroSession] = useState("");
  const [confirmationDialog, setConfirmationDialog] = useState({ open: false, type: 'success', title: '', message: '' });

  useEffect(() => {
    if (account) {
      let hall = { ...(account.hall || {}) };
      // Ensure the three keys exist with boolean values, with fallback for backward compatibility
      if (hall['复活重打'] === undefined) hall['复活重打'] = false;
      if (hall['客房补血'] === undefined) hall['客房补血'] = false;
      if (hall['自动买次数'] === undefined) hall['自动买次数'] = false;
      if (hall['失败切换'] === undefined) hall['失败切换'] = true;
      
      // Convert legacy integer values to boolean for backward compatibility
      if (typeof hall['复活重打'] === 'number') hall['复活重打'] = Boolean(hall['复活重打']);
      if (typeof hall['客房补血'] === 'number') hall['客房补血'] = Boolean(hall['客房补血']);
      if (typeof hall['自动买次数'] === 'number') hall['自动买次数'] = Boolean(hall['自动买次数']);
      
      setHallSettings(hall);
      
      // Initialize common settings
      let common = { ...(account.common_settings || {}) };
      if (common['武馆'] === undefined) common['武馆'] = '';
      setCommonSettings(common);
      
      // Initialize dungeon settings
      let dungeons = account.dungeon_settings || [];
      // Ensure we have 3 dungeons with all 5 fields
      while (dungeons.length < 3) {
        dungeons.push({ 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' });
      }
      // Ensure each dungeon has all 5 fields
      dungeons = dungeons.map(dungeon => ({
        副本: dungeon.副本 || '',
        队员1: dungeon.队员1 || '',
        队员2: dungeon.队员2 || '',
        角色功能: dungeon.角色功能 || '',
        目标位置: dungeon.目标位置 || '通关'
      }));
      setDungeonSettings(dungeons.slice(0, 3));
      
      // Initialize duel dungeon settings
      let duelDungeons = account.duel_dungeon_settings || [];
      // Ensure we have 2 dungeons with all 5 fields
      while (duelDungeons.length < 2) {
        duelDungeons.push({ 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' });
      }
      // Ensure each dungeon has all 5 fields
      duelDungeons = duelDungeons.map(dungeon => ({
        副本: dungeon.副本 || '',
        队员1: dungeon.队员1 || '',
        队员2: dungeon.队员2 || '',
        角色功能: dungeon.角色功能 || '',
        目标位置: dungeon.目标位置 || '通关'
      }));
      setDuelDungeonSettings(duelDungeons.slice(0, 2));
      
      // Parse cookie string for url, weeCookie, heroSession
      const { url, weeCookie, heroSession } = parseCookie(account.cookie);
      setEditUrl(url);
      setEditWeeCookie(weeCookie);
      setEditHeroSession(heroSession);
    }
  }, [account]);

  const handleHallOption = (hall, option) => {
    setHallSettings((prev) => {
      const next = { ...prev };
      if (option === "skip") {
        delete next[hall];
      } else if (option === "pass") {
        next[hall] = "";
      }
      return next;
    });
  };

  const handleHallInput = (hall, value) => {
    setHallSettings((prev) => ({ ...prev, [hall]: value }));
  };

  const handleSave = async () => {
    if (!account) return;
    // Compose new cookie string
    if (!editUrl || !editWeeCookie || !editHeroSession) return;
    const newCookie = composeCookie(editUrl, editWeeCookie, editHeroSession);
    
    await onSave({
      account_name: account.name,
      cookie: newCookie,
      hall_settings: hallSettings,
      common_settings: commonSettings,
      dungeon_settings: dungeonSettings,
      duel_dungeon_settings: duelDungeonSettings
    });
    onClose();
  };

  const handleCancel = () => {
    // Reset form state to original account values
    if (account) {
      let hall = { ...(account.hall || {}) };
      // Ensure the four keys exist with boolean values, with fallback for backward compatibility
      if (hall['复活重打'] === undefined) hall['复活重打'] = false;
      if (hall['客房补血'] === undefined) hall['客房补血'] = false;
      if (hall['自动买次数'] === undefined) hall['自动买次数'] = false;
      if (hall['失败切换'] === undefined) hall['失败切换'] = true;
      
      // Convert legacy integer values to boolean for backward compatibility
      if (typeof hall['复活重打'] === 'number') hall['复活重打'] = Boolean(hall['复活重打']);
      if (typeof hall['客房补血'] === 'number') hall['客房补血'] = Boolean(hall['客房补血']);
      if (typeof hall['自动买次数'] === 'number') hall['自动买次数'] = Boolean(hall['自动买次数']);
      if (typeof hall['失败切换'] === 'number') hall['失败切换'] = Boolean(hall['失败切换']);
      
      setHallSettings(hall);
      
      // Reset common settings
      let common = { ...(account.common_settings || {}) };
      if (common['武馆'] === undefined) common['武馆'] = '';
      setCommonSettings(common);
      
      // Reset dungeon settings
      let dungeons = account.dungeon_settings || [];
      while (dungeons.length < 3) {
        dungeons.push({ 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' });
      }
      dungeons = dungeons.map(dungeon => ({
        副本: dungeon.副本 || '',
        队员1: dungeon.队员1 || '',
        队员2: dungeon.队员2 || '',
        角色功能: dungeon.角色功能 || '',
        目标位置: dungeon.目标位置 || '通关'
      }));
      setDungeonSettings(dungeons.slice(0, 3));
      
      // Reset duel dungeon settings
      let duelDungeons = account.duel_dungeon_settings || [];
      while (duelDungeons.length < 2) {
        duelDungeons.push({ 副本: '', 队员1: '', 队员2: '', 角色功能: '', 目标位置: '通关' });
      }
      duelDungeons = duelDungeons.map(dungeon => ({
        副本: dungeon.副本 || '',
        队员1: dungeon.队员1 || '',
        队员2: dungeon.队员2 || '',
        角色功能: dungeon.角色功能 || '',
        目标位置: dungeon.目标位置 || '通关'
      }));
      setDuelDungeonSettings(duelDungeons.slice(0, 2));
      
      // Parse cookie string for url, weeCookie, heroSession
      const { url, weeCookie, heroSession } = parseCookie(account.cookie);
      setEditUrl(url);
      setEditWeeCookie(weeCookie);
      setEditHeroSession(heroSession);
    }
    onClose();
  };

  const showConfirmationDialog = (type, title, message) => {
    setConfirmationDialog({ open: true, type, title, message });
  };

  const closeConfirmationDialog = () => {
    setConfirmationDialog({ open: false, type: 'success', title: '', message: '' });
  };

  const handleBuyCombatCount = async () => {
    if (!account) return;
    
    try {
      const result = await api.buyCombatCount(account.username, account.name);
      
      if (result.data.success) {
        showConfirmationDialog('success', '购买成功', `角色 ${account.name} ${result.data.message}`);
        // Optionally refresh account data or close dialog
        onSave({
          account_name: account.name,
          cookie: account.cookie,
          hall_settings: account.hall
        });
      } else {
        showConfirmationDialog('error', '购买失败', '购买挑战次数失败: ' + result.data.message);
      }
    } catch (error) {
      console.error('Error buying combat count:', error);
      showConfirmationDialog('error', '购买失败', '购买挑战次数失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  if (!account) return null;

  return (
    <>
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontSize: '1rem' }}>角色设置 - {account.name}</DialogTitle>
      <DialogContent>
        <Tabs value={settingsTab} onChange={(_, v) => setSettingsTab(v)} sx={{ mb: 2 }}>
          <Tab label="幻境设置" />
          <Tab label="角色设置" />
          <Tab label="一般设置" />
          <Tab label="副本设置" />
          <Tab label="跨服副本设置" />
        </Tabs>
        
        {settingsTab === 0 && (
          <>
            {HALLS.map(hall => {
              const value = hallSettings[hall];
              let option;
              if (value === undefined) {
                option = "skip";
              } else if (value === "") {
                option = "pass";
              } else {
                option = "custom";
              }
              return (
                <Box key={hall} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Typography sx={{ minWidth: 100 }}>{hall}</Typography>
                  <Button
                    variant={option === "pass" ? "contained" : "outlined"}
                    size="small"
                    onClick={() => handleHallOption(hall, "pass")}
                  >通关</Button>
                  <Button
                    variant={option === "skip" ? "contained" : "outlined"}
                    size="small"
                    onClick={() => handleHallOption(hall, "skip")}
                  >跳过</Button>
                  <TextField
                    size="small"
                    placeholder="自定义设置"
                    value={option === "custom" ? value : ""}
                    onChange={e => handleHallInput(hall, e.target.value)}
                    sx={{ flex: 1 }}
                  />
                </Box>
              );
            })}
            <Box sx={{ fontSize: 12, color: 'gray', mt: 2 }}>
              通关=空字符串，跳过=不保存该项，自定义=输入框内容。<br />
              当前设置: {JSON.stringify(hallSettings, null, 2)}
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'row', gap: 2, mt: 3, flexWrap: 'wrap' }}>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Checkbox 
                  checked={!!hallSettings['复活重打']} 
                  onChange={e => setHallSettings(prev => ({ ...prev, 复活重打: e.target.checked }))} 
                />
                <span>复活重打</span>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Checkbox 
                  checked={!!hallSettings['客房补血']} 
                  onChange={e => setHallSettings(prev => ({ ...prev, 客房补血: e.target.checked }))} 
                />
                <span>客房补血</span>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Checkbox 
                  checked={!!hallSettings['自动买次数']} 
                  onChange={e => setHallSettings(prev => ({ ...prev, 自动买次数: e.target.checked }))} 
                />
                <span>自动买次数</span>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Checkbox 
                  checked={!!hallSettings['失败切换']} 
                  onChange={e => setHallSettings(prev => ({ ...prev, 失败切换: e.target.checked }))} 
                />
                <span>失败切换</span>
              </Box>
            </Box>
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
              <Button 
                variant="contained" 
                color="primary"
                onClick={handleBuyCombatCount}
                sx={{ minWidth: 150 }}
              >
                购买挑战次数
              </Button>
            </Box>
          </>
        )}
        
        {settingsTab === 1 && (
          <Box sx={{ mt: 3 }}>
            <TextField 
              label="游戏网址" 
              fullWidth 
              margin="normal" 
              value={editUrl} 
              onChange={e => setEditUrl(e.target.value)} 
            />
            <TextField 
              label="weeCookie" 
              fullWidth 
              margin="normal" 
              value={editWeeCookie} 
              onChange={e => setEditWeeCookie(e.target.value)} 
            />
            <TextField 
              label="50hero_session" 
              fullWidth 
              margin="normal" 
              value={editHeroSession} 
              onChange={e => setEditHeroSession(e.target.value)} 
            />
          </Box>
        )}
        
        {settingsTab === 2 && (
          <Box sx={{ mt: 3 }}>
            <TextField 
              label="每日护馆踢馆目标" 
              fullWidth 
              margin="normal" 
              value={commonSettings['武馆'] || ''} 
              onChange={e => setCommonSettings(prev => ({ ...prev, '武馆': e.target.value }))} 
              helperText="武馆设置：控制每日护馆踢馆目标"
              placeholder="请输入武馆设置"
            />
          </Box>
        )}
        
        {settingsTab === 3 && (
          <Box sx={{ mt: 3 }}>
            {dungeonSettings.map((dungeon, index) => (
              <Box key={index} sx={{ mb: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 'bold' }}>
                  副本设置 {index + 1}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                  <FormControl size="small" sx={{ flex: 1.5 }}>
                    <InputLabel>副本</InputLabel>
                    <Select
                      value={dungeon.副本 || ''}
                      label="副本"
                      onChange={e => {
                        const newDungeons = [...dungeonSettings];
                        newDungeons[index].副本 = e.target.value;
                        setDungeonSettings(newDungeons);
                      }}
                    >
                      <MenuItem value="咸阳暗道#困难">咸阳暗道#困难</MenuItem>
                      <MenuItem value="冰火石窟">冰火石窟</MenuItem>
                      <MenuItem value="天堂瀑布">天堂瀑布</MenuItem>
                    </Select>
                  </FormControl>
                  <TextField 
                    label="队员1" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.队员1 || ''} 
                    onChange={e => {
                      const newDungeons = [...dungeonSettings];
                      newDungeons[index].队员1 = e.target.value;
                      setDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入队员1名称"
                  />
                  <TextField 
                    label="队员2" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.队员2 || ''} 
                    onChange={e => {
                      const newDungeons = [...dungeonSettings];
                      newDungeons[index].队员2 = e.target.value;
                      setDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入队员2名称"
                  />
                  <TextField 
                    label="角色功能" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.角色功能 || ''} 
                    onChange={e => {
                      const newDungeons = [...dungeonSettings];
                      newDungeons[index].角色功能 = e.target.value;
                      setDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入角色功能"
                  />
                  <TextField 
                    label="目标位置" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.目标位置 || '通关'} 
                    onChange={e => {
                      const newDungeons = [...dungeonSettings];
                      newDungeons[index].目标位置 = e.target.value;
                      setDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入目标位置"
                  />
                </Box>
              </Box>
            ))}
          </Box>
        )}
        
        {settingsTab === 4 && (
          <Box sx={{ mt: 3 }}>
            {duelDungeonSettings.map((dungeon, index) => (
              <Box key={index} sx={{ mb: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 'bold' }}>
                  跨服副本设置 {index + 1}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                  <TextField 
                    label="副本" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.副本 || ''} 
                    onChange={e => {
                      const newDungeons = [...duelDungeonSettings];
                      newDungeons[index].副本 = e.target.value;
                      setDuelDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入副本名称"
                  />
                  <TextField 
                    label="队员1" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.队员1 || ''} 
                    onChange={e => {
                      const newDungeons = [...duelDungeonSettings];
                      newDungeons[index].队员1 = e.target.value;
                      setDuelDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入队员1名称"
                  />
                  <TextField 
                    label="队员2" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.队员2 || ''} 
                    onChange={e => {
                      const newDungeons = [...duelDungeonSettings];
                      newDungeons[index].队员2 = e.target.value;
                      setDuelDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入队员2名称"
                  />
                  <TextField 
                    label="角色功能" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.角色功能 || ''} 
                    onChange={e => {
                      const newDungeons = [...duelDungeonSettings];
                      newDungeons[index].角色功能 = e.target.value;
                      setDuelDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入角色功能"
                  />
                  <TextField 
                    label="目标位置" 
                    size="small"
                    sx={{ flex: 1 }}
                    value={dungeon.目标位置 || '通关'} 
                    onChange={e => {
                      const newDungeons = [...duelDungeonSettings];
                      newDungeons[index].目标位置 = e.target.value;
                      setDuelDungeonSettings(newDungeons);
                    }} 
                    placeholder="请输入目标位置"
                  />
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCancel}>取消</Button>
        <Button variant="contained" onClick={handleSave}>保存</Button>
      </DialogActions>
    </Dialog>

    {/* Confirmation Dialog */}
    <Dialog 
      open={confirmationDialog.open} 
      onClose={closeConfirmationDialog}
      maxWidth="xs"
      fullWidth
      sx={{
        '& .MuiDialog-paper': {
          borderRadius: 2,
          boxShadow: '0 8px 32px rgba(0,0,0,0.12)'
        }
      }}
    >
      <DialogContent sx={{ pt: 3, pb: 2, px: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          {confirmationDialog.type === 'success' ? (
            <CheckCircle sx={{ color: 'success.main', fontSize: 32, mr: 2 }} />
          ) : (
            <Error sx={{ color: 'error.main', fontSize: 32, mr: 2 }} />
          )}
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {confirmationDialog.title}
          </Typography>
        </Box>
        <Typography variant="body1" sx={{ color: 'text.secondary', lineHeight: 1.6 }}>
          {confirmationDialog.message}
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3, pt: 1 }}>
        <Button 
          variant="contained" 
          onClick={closeConfirmationDialog}
          sx={{ 
            minWidth: 100,
            borderRadius: 1,
            textTransform: 'none',
            fontWeight: 600
          }}
        >
          确定
        </Button>
      </DialogActions>
    </Dialog>
    </>
  );
}

export default SettingsDialog; 