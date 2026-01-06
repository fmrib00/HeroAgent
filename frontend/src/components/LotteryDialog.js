import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography
} from "@mui/material";

function LotteryDialog({ open, onClose, onSubmit, selectedCount, lotteryType }) {
  const [lotteryNumbers, setLotteryNumbers] = useState("");

  const handleSubmit = () => {
    if (lotteryNumbers.trim()) {
      // Validate that input contains only numbers
      if (/^\d+$/.test(lotteryNumbers.trim())) {
        onSubmit(lotteryNumbers.trim());
        setLotteryNumbers("");
        onClose();
      }
    }
  };

  const handleClose = () => {
    setLotteryNumbers("");
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputChange = (e) => {
    const value = e.target.value;
    // Only allow numbers
    if (value === "" || /^\d+$/.test(value)) {
      setLotteryNumbers(value);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>联赛竞猜 - {lotteryType}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            请输入竞猜号码，每个组别一个数字（例如: 543 表示组1选5，组2选4，组3选3）
          </Typography>
          <TextField
            label="竞猜号码"
            value={lotteryNumbers}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="例如: 543"
            fullWidth
            required
            autoFocus
            inputProps={{ inputMode: 'numeric', pattern: '[0-9]*' }}
            helperText={`将为 ${selectedCount} 个选中账号提交竞猜`}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>取消</Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          disabled={!lotteryNumbers.trim() || !/^\d+$/.test(lotteryNumbers.trim())}
        >
          提交竞猜
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default LotteryDialog;

