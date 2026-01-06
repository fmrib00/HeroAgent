import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  CircularProgress,
  Alert,
  Divider,
  IconButton,
  Tooltip
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import BlockIcon from "@mui/icons-material/Block";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import SettingsIcon from "@mui/icons-material/Settings";
import { api } from "../utils/api";
import AccountList from "./AccountList";

function AdminPanel({ username, onSelectPlayer, selectedPlayerEmail, selectedAccounts, selected, onSelectAccount, onSelectAllAccounts, onRefreshPlayerAccounts, onAddAccount, onOpenSettings, onDeleteAccounts, onOpenBrowser, onOpenGlobalSettings }) {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [toggling, setToggling] = useState({});

  useEffect(() => {
    fetchPlayers();
  }, []);

  const fetchPlayers = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.getAllPlayers();
      if (response.data.success) {
        const playersList = response.data.players || [];
        setPlayers(sortPlayers(playersList));
      } else {
        setError("Failed to fetch players");
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to fetch players");
    } finally {
      setLoading(false);
    }
  };

  const sortPlayers = (playersList) => {
    return [...playersList].sort((a, b) => {
      // Check if users have game accounts
      const aHasAccounts = (a.account_count || 0) > 0;
      const bHasAccounts = (b.account_count || 0) > 0;
      
      // Users with no accounts go to the bottom
      if (aHasAccounts && !bHasAccounts) return -1;
      if (!aHasAccounts && bHasAccounts) return 1;
      
      // Check if users are advanced (handle boolean, string, or truthy values)
      const aIsAdvanced = a.advanced === true || 
                         a.advanced === 'true' || 
                         a.advanced === 'True' || 
                         a.advanced === 'TRUE' ||
                         String(a.advanced).toLowerCase() === 'true';
      const bIsAdvanced = b.advanced === true || 
                         b.advanced === 'true' || 
                         b.advanced === 'True' || 
                         b.advanced === 'TRUE' ||
                         String(b.advanced).toLowerCase() === 'true';
      
      // Advanced users always come first (among users with same account status)
      if (aIsAdvanced && !bIsAdvanced) return -1;
      if (!aIsAdvanced && bIsAdvanced) return 1;
      
      // If both are advanced or both are not advanced, sort by expiration date
      // Handle missing expiration dates (put them at the end)
      if (!a.expiration && !b.expiration) return 0;
      if (!a.expiration) return 1;
      if (!b.expiration) return -1;
      
      // Parse expiration dates and sort in ascending order (earliest first)
      const dateA = new Date(a.expiration);
      const dateB = new Date(b.expiration);
      
      // Check if dates are valid
      if (isNaN(dateA.getTime()) && isNaN(dateB.getTime())) return 0;
      if (isNaN(dateA.getTime())) return 1;
      if (isNaN(dateB.getTime())) return -1;
      
      return dateA - dateB;
    });
  };

  const handleToggleStatus = async (playerEmail, currentStatus) => {
    const newStatus = !currentStatus;
    setToggling({ ...toggling, [playerEmail]: true });
    try {
      const response = await api.toggleUserStatus(playerEmail, newStatus);
      if (response.data.success) {
        // Update local state and maintain sort order
        const updatedPlayers = players.map(p => 
          p.email === playerEmail ? { ...p, disabled: newStatus } : p
        );
        setPlayers(sortPlayers(updatedPlayers));
      } else {
        setError(response.data.message || "Failed to toggle user status");
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to toggle user status");
    } finally {
      setToggling({ ...toggling, [playerEmail]: false });
    }
  };

  return (
    <Box sx={{ display: "flex", p: 2, gap: 2 }}>
      {/* Players List */}
      <Paper sx={{ width: 300, p: 2, maxHeight: 'calc(100vh - 112px)', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6">玩家列表</Typography>
          <Tooltip title="刷新列表">
            <IconButton onClick={fetchPlayers} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
            {error}
          </Alert>
        )}
        
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : players.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            暂无玩家
          </Typography>
        ) : (
          <List>
            {players.map((player, index) => {
              const hasNoAccounts = (player.account_count || 0) === 0;
              return (
              <React.Fragment key={player.email}>
                <ListItem
                  button
                  selected={selectedPlayerEmail === player.email}
                  onClick={() => onSelectPlayer(player.email)}
                  sx={{
                    bgcolor: selectedPlayerEmail === player.email 
                      ? 'action.selected' 
                      : hasNoAccounts 
                        ? 'rgba(255, 152, 0, 0.08)' // Light orange background for users with no accounts
                        : 'transparent',
                    color: hasNoAccounts ? 'text.secondary' : 'text.primary',
                    opacity: hasNoAccounts ? 0.7 : 1,
                    '&:hover': {
                      bgcolor: hasNoAccounts 
                        ? 'rgba(255, 152, 0, 0.12)' 
                        : 'action.hover'
                    }
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" sx={{ color: hasNoAccounts ? 'text.secondary' : 'inherit' }}>
                          {player.email}
                        </Typography>
                        {hasNoAccounts && (
                          <Chip
                            label="无账号"
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: 'rgba(255, 152, 0, 0.2)',
                              color: 'rgb(255, 152, 0)',
                              fontWeight: 500
                            }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                        <Chip
                          label={player.disabled ? "已禁用" : "正常"}
                          size="small"
                          color={player.disabled ? "error" : "success"}
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                        {player.expiration && (
                          <Typography variant="caption" color="text.secondary">
                            到期: {player.expiration}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Tooltip title={player.disabled ? "启用用户" : "禁用用户"}>
                      <IconButton
                        edge="end"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleStatus(player.email, player.disabled);
                        }}
                        disabled={toggling[player.email]}
                        color={player.disabled ? "success" : "error"}
                        size="small"
                      >
                        {player.disabled ? <CheckCircleIcon /> : <BlockIcon />}
                      </IconButton>
                    </Tooltip>
                  </ListItemSecondaryAction>
                </ListItem>
                {index < players.length - 1 && <Divider />}
              </React.Fragment>
            );
            })}
          </List>
        )}
      </Paper>

      {/* Player Accounts */}
      {selectedPlayerEmail && (
        <Box sx={{ flex: 1 }}>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="h6">
                玩家账号: {selectedPlayerEmail}
              </Typography>
              <Tooltip title="任务调度设置">
                <IconButton 
                  color="primary" 
                  onClick={onOpenGlobalSettings}
                  size="small"
                >
                  <SettingsIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Paper>
          {selectedAccounts && selectedAccounts.length > 0 ? (
            <AccountList
              accounts={selectedAccounts}
              selected={selected || []}
              onSelect={onSelectAccount}
              onSelectAll={onSelectAllAccounts}
              onRefresh={onRefreshPlayerAccounts}
              onAddAccount={onAddAccount}
              onDeleteAccounts={onDeleteAccounts}
              onOpenSettings={onOpenSettings}
              onOpenBrowser={onOpenBrowser}
            />
          ) : selectedPlayerEmail ? (
            <Paper sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary">
                该玩家暂无账号
              </Typography>
            </Paper>
          ) : null}
        </Box>
      )}
    </Box>
  );
}

export default AdminPanel;

