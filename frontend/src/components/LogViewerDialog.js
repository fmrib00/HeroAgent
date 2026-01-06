import React, { useState, useEffect, useCallback } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Box, Typography, List, ListItem, ListItemText, Paper
} from "@mui/material";
import { api } from "../utils/api";

function LogViewerDialog({ open, onClose, username }) {
  const [logFiles, setLogFiles] = useState([]);
  const [selectedLogFile, setSelectedLogFile] = useState(null);
  const [logContent, setLogContent] = useState("");

  const fetchLogFiles = useCallback(async () => {
    try {
      const response = await api.getLogFiles(username);
      setLogFiles(response.data.log_files || []);
    } catch (e) {
      console.error("Failed to fetch log files", e);
    }
  }, [username]);


  const handleViewLogFile = async (logFile, retryCount = 0) => {
    setSelectedLogFile(logFile);
    setLogContent("Loading...");
    
    try {
      // Use the new endpoint to get specific log file content
      const response = await api.getLogFileContent(username, logFile.path);
      
      if (!response.ok) {
        console.error("Log file request failed:", response.status, response.statusText);
        setLogContent(`Failed to load log file: ${response.status} ${response.statusText}`);
        return;
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let content = "";
      
      try {
        while (true) {
          const { value, done } = await reader.read();
          const decodedValue = value ? decoder.decode(value, { stream: true }) : null;
          
          if (done) break;
          
          content += decodedValue;
          
          // Check if this is the completion message
          if (decodedValue && decodedValue.includes('日志文件读取完成')) {
            break;
          }
        }
        
        // Process the content to extract log lines from Server-Sent Events format
        const lines = content.split('\n');
        const logLines = [];
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const logLine = line.substring(6); // Remove 'data: ' prefix
            if (logLine.trim()) {
              logLines.push(logLine);
            }
          }
        }
        
        if (logLines.length === 0) {
          setLogContent("没有找到日志内容。可能没有活跃的战斗会话或日志文件。");
        } else {
          setLogContent(logLines.join('\n'));
        }
      } catch (streamError) {
        console.error("Error reading stream:", streamError);
        setLogContent("Error reading log file stream");
      } finally {
        reader.releaseLock();
      }
    } catch (e) {
      console.error("Error loading log file:", e);
      
      // Retry up to 2 times for network errors
      if (retryCount < 2 && (e.message.includes('network') || e.message.includes('connection') || e.message.includes('timeout'))) {
        console.log(`Retrying log file load (${retryCount + 1}/2)...`);
        setTimeout(() => {
          handleViewLogFile(logFile, retryCount + 1);
        }, 1000 * (retryCount + 1)); // Exponential backoff
        return;
      }
      
      setLogContent(`Error loading log file: ${e.message}`);
    }
  };

  useEffect(() => {
    if (open) {
      fetchLogFiles();
    }
  }, [open, username, fetchLogFiles]);

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="lg"
      fullWidth
    >
      <DialogTitle>日志管理</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', gap: 2, height: 500 }}>
          {/* Log Files List */}
          <Box sx={{ width: 300, border: '1px solid #ddd', borderRadius: 1, p: 1 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>日志文件</Typography>
            <List sx={{ maxHeight: 400, overflowY: 'auto' }}>
              {logFiles.map((logFile, index) => (
                <ListItem 
                  key={index} 
                  button 
                  selected={selectedLogFile?.filename === logFile.filename}
                  onClick={() => handleViewLogFile(logFile)}
                >
                  <ListItemText 
                    primary={logFile.filename}
                    secondary={`${new Date(logFile.modified).toLocaleString()} (${(logFile.size / 1024).toFixed(1)} KB)`}
                  />
                </ListItem>
              ))}
              {logFiles.length === 0 && (
                <ListItem>
                  <ListItemText primary="暂无日志文件" />
                </ListItem>
              )}
            </List>
          </Box>
          
          {/* Log Content */}
          <Box sx={{ flex: 1, border: '1px solid #ddd', borderRadius: 1, p: 1 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {selectedLogFile ? selectedLogFile.filename : '选择日志文件查看内容'}
            </Typography>
            <Paper
              sx={{
                p: 2,
                height: 400,
                fontFamily: "monospace",
                whiteSpace: "pre-wrap",
                overflowY: "auto",
                fontSize: 12,
                bgcolor: '#f5f5f5'
              }}
            >
              {logContent}
            </Paper>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>关闭</Button>
        <Button 
          variant="contained" 
          onClick={() => {
            fetchLogFiles();
          }}
        >
          刷新
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default LogViewerDialog; 