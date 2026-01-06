import React, { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  CircularProgress,
  Typography
} from "@mui/material";
import { api } from "../utils/api";

function FanBadgeDialog({ open, onClose, onSubmit, selectedCount, username, selected, isAdmin = false }) {
  const [badges, setBadges] = useState([]);
  const [selectedBadge, setSelectedBadge] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchBadges = useCallback(async () => {
    console.log("FanBadgeDialog: fetchBadges called", { username, selected, isAdmin });
    setLoading(true);
    setError("");
    try {
      const response = await api.getFanBadges(username, selected, isAdmin);
      const result = response.data;
      
      // Extract badges from results
      // The badges are returned in the results for each account
      // We'll use the first account's badges, or merge all badges
      const allBadges = [];
      const badgeMap = new Map(); // Use Map to avoid duplicates by name
      
      Object.values(result.results || {}).forEach(accountResult => {
        if (accountResult.success && accountResult.message) {
          try {
            const accountBadges = JSON.parse(accountResult.message);
            if (Array.isArray(accountBadges)) {
              accountBadges.forEach(badge => {
                if (badge.name && !badgeMap.has(badge.name)) {
                  badgeMap.set(badge.name, badge);
                  allBadges.push(badge);
                }
              });
            }
          } catch (e) {
            console.error("Error parsing badges:", e);
          }
        }
      });
      
      setBadges(allBadges);
      if (allBadges.length === 0) {
        setError("未找到可兑换的粉丝章");
      }
    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message || "获取粉丝章列表失败";
      setError(errorMsg);
      console.error("Error fetching badges:", e);
    } finally {
      setLoading(false);
    }
  }, [username, selected, isAdmin]);

  // Fetch badges when dialog opens
  useEffect(() => {
    if (open && selected.length > 0) {
      fetchBadges();
    } else {
      // Reset state when dialog closes
      setBadges([]);
      setSelectedBadge("");
      setQuantity("1");
      setError("");
    }
  }, [open, selected, username, fetchBadges]);

  const handleSubmit = () => {
    if (!selectedBadge || !quantity) {
      setError("请选择粉丝章并输入数量");
      return;
    }
    
    const qty = parseInt(quantity);
    if (isNaN(qty) || qty < 1 || qty > 100) {
      setError("数量必须在1-100之间");
      return;
    }
    
    const badge = badges.find(b => b.name === selectedBadge);
    if (badge) {
      onSubmit(badge, qty);
      setSelectedBadge("");
      setQuantity("1");
      setError("");
      onClose();
    }
  };

  const handleClose = () => {
    setSelectedBadge("");
    setQuantity("1");
    setError("");
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && selectedBadge && quantity) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>粉丝章兑换</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", py: 4 }}>
              <CircularProgress />
              <Typography sx={{ ml: 2 }}>正在获取粉丝章列表...</Typography>
            </Box>
          ) : (
            <>
              <FormControl fullWidth required>
                <InputLabel>选择粉丝章</InputLabel>
                <Select
                  value={selectedBadge}
                  onChange={(e) => setSelectedBadge(e.target.value)}
                  label="选择粉丝章"
                >
                  {badges.map((badge) => (
                    <MenuItem key={badge.id || badge.name} value={badge.name}>
                      {badge.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="数量"
                type="number"
                value={quantity}
                onChange={(e) => {
                  const val = e.target.value;
                  // Allow empty string for user to clear and type
                  if (val === "") {
                    setQuantity(val);
                    return;
                  }
                  // Parse as number and validate range
                  const numVal = parseInt(val, 10);
                  if (!isNaN(numVal) && numVal >= 1 && numVal <= 100) {
                    setQuantity(val);
                  } else if (!isNaN(numVal) && numVal > 100) {
                    // Cap at 100 if user types something > 100
                    setQuantity("100");
                  }
                  // If invalid (like non-numeric), don't update
                }}
                onKeyDown={handleKeyDown}
                placeholder="1-100"
                fullWidth
                required
                inputProps={{ min: 1, max: 100 }}
                helperText={`将为 ${selectedCount} 个选中账号兑换`}
              />
              {error && (
                <Typography color="error" variant="body2">
                  {error}
                </Typography>
              )}
            </>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>取消</Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          disabled={!selectedBadge || !quantity || loading}
        >
          确认兑换
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default FanBadgeDialog;

