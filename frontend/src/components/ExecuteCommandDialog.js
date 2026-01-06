import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  FormControlLabel,
  Checkbox
} from "@mui/material";

function ExecuteCommandDialog({ open, onClose, onExecute, selectedCount }) {
  const [command, setCommand] = useState("");
  const [id, setId] = useState("");
  const [isDuelCommand, setIsDuelCommand] = useState(false);

  const handleExecute = () => {
    if (command.trim()) {
      onExecute(command.trim(), id.trim() || null, isDuelCommand);
      setCommand("");
      setId("");
      setIsDuelCommand(false);
      onClose();
    }
  };

  const handleClose = () => {
    setCommand("");
    setId("");
    setIsDuelCommand(false);
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleExecute();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>执行命令</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="命令"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="例如: 签到查看, 移动场景, 打怪, 等"
            fullWidth
            required
            autoFocus
            helperText={`将为 ${selectedCount} 个选中账号执行此命令`}
          />
          <TextField
            label="ID (可选)"
            value={id}
            onChange={(e) => setId(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="例如: 483 (场景ID), 73 (怪物ID), 等"
            fullWidth
            helperText="某些命令需要ID参数，如移动场景、打怪等"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={isDuelCommand}
                onChange={(e) => setIsDuelCommand(e.target.checked)}
                color="primary"
              />
            }
            label="跨服竞技场"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>取消</Button>
        <Button 
          onClick={handleExecute} 
          variant="contained" 
          disabled={!command.trim()}
        >
          执行
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default ExecuteCommandDialog;

