import React from "react";
import {
  Paper, Typography, Button, Box, Checkbox, List, ListItem, ListItemText, ListItemIcon, IconButton, Tooltip
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import SettingsIcon from "@mui/icons-material/Settings";
import OpenInBrowserIcon from "@mui/icons-material/OpenInBrowser";

function AccountList({ 
  accounts, 
  selected, 
  onSelect, 
  onSelectAll, 
  onRefresh, 
  onAddAccount, 
  onDeleteAccounts, 
  onOpenSettings,
  onOpenBrowser
}) {
  const handleSelect = (name) => {
    onSelect(name);
  };

  const handleAll = (all) => {
    onSelectAll(all);
  };

  const handleDelete = async () => {
    if (!window.confirm('确定要删除选中的账号吗？')) return;
    await onDeleteAccounts();
  };

  return (
    <Paper sx={{ 
      width: 240, 
      mr: 2, 
      p: 1, 
      display: "flex", 
      flexDirection: "column", 
      maxHeight: 'calc(100vh - 112px)', 
      minHeight: 200, 
      justifyContent: "space-between" 
    }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>账号列表</Typography>
          <Tooltip title="刷新账号列表">
            <IconButton onClick={onRefresh} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
        <List sx={{ 
          flex: 1, 
          overflowY: 'auto', 
          py: 0,
          minHeight: 0,
          '&::-webkit-scrollbar': {
            width: '6px',
          },
          '&::-webkit-scrollbar-track': {
            background: '#f1f1f1',
            borderRadius: '3px',
          },
          '&::-webkit-scrollbar-thumb': {
            background: '#c1c1c1',
            borderRadius: '3px',
          },
          '&::-webkit-scrollbar-thumb:hover': {
            background: '#a8a8a8',
          },
        }}>
          {accounts.map((acc, idx) => (
            <ListItem 
              key={acc.name + '-' + idx} 
              button 
              onClick={() => handleSelect(acc.name)}
              sx={{ 
                py: 0.5, 
                minHeight: 32,
                '&:hover': {
                  bgcolor: 'action.hover'
                }
              }}
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <Checkbox checked={selected.includes(acc.name)} size="small" />
              </ListItemIcon>
              <ListItemText 
                primary={acc.name} 
                sx={{ 
                  '& .MuiListItemText-primary': {
                    fontSize: '0.8rem',
                    lineHeight: 1.2
                  }
                }}
              />
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {onOpenBrowser && (
                  <Tooltip title="在浏览器中打开（使用存储的cookies登录）">
                    <IconButton 
                      edge="end" 
                      onClick={e => { e.stopPropagation(); onOpenBrowser(acc); }}
                      size="small"
                      sx={{ p: 0.5 }}
                    >
                      <OpenInBrowserIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip title="设置幻境配置">
                  <IconButton 
                    edge="end" 
                    onClick={e => { e.stopPropagation(); onOpenSettings(acc); }}
                    size="small"
                    sx={{ p: 0.5 }}
                  >
                    <SettingsIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </ListItem>
          ))}
        </List>
        <Box sx={{ display: "flex", justifyContent: "space-between", mt: 1, flexShrink: 0 }}>
          <Button size="small" onClick={() => handleAll(true)}>全选</Button>
          <Button size="small" onClick={() => handleAll(false)}>取消全选</Button>
        </Box>
      </Box>
      <Box sx={{ flexShrink: 0, mt: 2 }}>
        <Button variant="contained" fullWidth onClick={onAddAccount}>
          添加账号
        </Button>
        <Button 
          variant="outlined" 
          color="error" 
          fullWidth 
          sx={{ mt: 1 }} 
          disabled={selected.length === 0} 
          onClick={handleDelete}
        >
          删除账户
        </Button>
      </Box>
    </Paper>
  );
}

export default AccountList; 