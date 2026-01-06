import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import PowerSettingsNewIcon from "@mui/icons-material/PowerSettingsNew";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import WarningIcon from "@mui/icons-material/Warning";
import { api } from "../utils/api";

function ShutdownControl() {
  const [jobStatus, setJobStatus] = useState(null);
  const [shutdownStatus, setShutdownStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pollingInterval, setPollingInterval] = useState(null);

  useEffect(() => {
    fetchStatus();
    
    // Cleanup polling on unmount
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, []);

  // Auto-poll shutdown status when shutdown is requested
  useEffect(() => {
    if (shutdownStatus?.shutdown_requested && !shutdownStatus?.safe_to_restart) {
      // Poll every 5 seconds
      const interval = setInterval(() => {
        fetchShutdownStatus();
      }, 5000);
      setPollingInterval(interval);
      
      return () => clearInterval(interval);
    } else {
      // Stop polling when shutdown is complete or not requested
      if (pollingInterval) {
        clearInterval(pollingInterval);
        setPollingInterval(null);
      }
    }
  }, [shutdownStatus?.shutdown_requested, shutdownStatus?.safe_to_restart]);

  const fetchStatus = async () => {
    setLoading(true);
    setError("");
    try {
      const [jobResponse, shutdownResponse] = await Promise.all([
        api.getJobStatus(),
        api.getShutdownStatus()
      ]);
      
      if (jobResponse.data.success) {
        setJobStatus(jobResponse.data);
      }
      if (shutdownResponse.data.success) {
        setShutdownStatus(shutdownResponse.data);
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to fetch status");
    } finally {
      setLoading(false);
    }
  };

  const fetchShutdownStatus = async () => {
    try {
      const response = await api.getShutdownStatus();
      if (response.data.success) {
        setShutdownStatus(response.data);
      }
    } catch (e) {
      console.error("Failed to fetch shutdown status:", e);
    }
  };

  const handleInitiateShutdown = async () => {
    setConfirmDialogOpen(false);
    setLoading(true);
    setError("");
    try {
      const response = await api.initiateShutdown();
      if (response.data.success) {
        // Refresh status after initiating shutdown
        await fetchStatus();
      } else {
        setError(response.data.message || "Failed to initiate shutdown");
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to initiate shutdown");
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) {
      return `${seconds}秒`;
    } else if (seconds < 3600) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}分${secs}秒`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      return `${hours}小时${mins}分`;
    }
  };

  const formatDateTime = (dateTimeStr) => {
    if (!dateTimeStr) return "-";
    try {
      const date = new Date(dateTimeStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      return dateTimeStr;
    }
  };

  return (
    <Box sx={{ p: 2 }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h5">系统关闭控制</Typography>
          <Tooltip title="刷新状态">
            <IconButton onClick={fetchStatus} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
            {error}
          </Alert>
        )}

        {/* Shutdown Control Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>关闭控制</Typography>
          
          {loading && !jobStatus && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          )}

          {shutdownStatus && (
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                <Chip
                  label={`关闭请求: ${shutdownStatus.shutdown_requested ? '是' : '否'}`}
                  color={shutdownStatus.shutdown_requested ? "warning" : "default"}
                  size="small"
                />
                <Chip
                  label={`调度器暂停: ${shutdownStatus.scheduler_paused ? '是' : '否'}`}
                  color={shutdownStatus.scheduler_paused ? "warning" : "default"}
                  size="small"
                />
                <Chip
                  label={`运行中任务: ${shutdownStatus.active_jobs_count}`}
                  color={shutdownStatus.active_jobs_count > 0 ? "warning" : "success"}
                  size="small"
                />
              </Box>

              {shutdownStatus.safe_to_restart ? (
                <Alert 
                  severity="success" 
                  icon={<CheckCircleIcon />}
                  sx={{ mb: 2 }}
                >
                  <Typography variant="body1" fontWeight="bold">
                    ✅ 可以安全重启服务器！
                  </Typography>
                  <Typography variant="body2">
                    所有任务已完成，调度器已暂停。现在可以手动停止并重启服务器。
                  </Typography>
                </Alert>
              ) : shutdownStatus.shutdown_requested ? (
                <Alert 
                  severity="warning" 
                  icon={<WarningIcon />}
                  sx={{ mb: 2 }}
                >
                  <Typography variant="body1" fontWeight="bold">
                    ⏳ 等待任务完成...
                  </Typography>
                  <Typography variant="body2">
                    {shutdownStatus.message || `等待 ${shutdownStatus.active_jobs_count} 个任务完成...`}
                  </Typography>
                </Alert>
              ) : null}

              {!shutdownStatus.shutdown_requested && (
                <Button
                  variant="contained"
                  color="warning"
                  startIcon={<PowerSettingsNewIcon />}
                  onClick={() => setConfirmDialogOpen(true)}
                  sx={{ mt: 1 }}
                >
                  启动关闭流程
                </Button>
              )}
            </Box>
          )}
        </Box>

        {/* Active Jobs Section */}
        {jobStatus && jobStatus.active_jobs_count > 0 && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              当前运行中的任务 ({jobStatus.active_jobs_count})
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>用户名</TableCell>
                    <TableCell>任务ID</TableCell>
                    <TableCell>开始时间</TableCell>
                    <TableCell>运行时长</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobStatus.active_jobs.map((job) => (
                    <TableRow key={job.execution_id}>
                      <TableCell>{job.username}</TableCell>
                      <TableCell>{job.job_id}</TableCell>
                      <TableCell>{formatDateTime(job.start_time)}</TableCell>
                      <TableCell>{formatDuration(job.duration_seconds)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* Recent Executions Section */}
        {jobStatus && jobStatus.recent_executions && jobStatus.recent_executions.length > 0 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 2 }}>
              最近执行记录 (最近50条)
            </Typography>
            <TableContainer sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>用户名</TableCell>
                    <TableCell>任务ID</TableCell>
                    <TableCell>任务类型</TableCell>
                    <TableCell>状态</TableCell>
                    <TableCell>计划时间</TableCell>
                    <TableCell>开始时间</TableCell>
                    <TableCell>结束时间</TableCell>
                    <TableCell>错误信息</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobStatus.recent_executions.slice(0, 20).map((execution) => (
                    <TableRow key={execution.execution_id}>
                      <TableCell>{execution.username}</TableCell>
                      <TableCell>{execution.job_id}</TableCell>
                      <TableCell>{execution.job_type}</TableCell>
                      <TableCell>
                        <Chip
                          label={execution.status}
                          size="small"
                          color={
                            execution.status === 'completed' ? 'success' :
                            execution.status === 'failed' ? 'error' :
                            execution.status === 'running' ? 'warning' :
                            'default'
                          }
                        />
                      </TableCell>
                      <TableCell>{formatDateTime(execution.scheduled_time)}</TableCell>
                      <TableCell>{formatDateTime(execution.execution_start_time)}</TableCell>
                      <TableCell>{formatDateTime(execution.execution_end_time)}</TableCell>
                      <TableCell>
                        {execution.error_message ? (
                          <Tooltip title={execution.error_message}>
                            <Typography variant="caption" color="error" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {execution.error_message}
                            </Typography>
                          </Tooltip>
                        ) : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {jobStatus && jobStatus.active_jobs_count === 0 && 
         (!jobStatus.recent_executions || jobStatus.recent_executions.length === 0) && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
            暂无任务记录
          </Typography>
        )}
      </Paper>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialogOpen}
        onClose={() => setConfirmDialogOpen(false)}
      >
        <DialogTitle>确认启动关闭流程</DialogTitle>
        <DialogContent>
          <DialogContentText>
            启动关闭流程后，系统将：
            <ul>
              <li>暂停所有新的任务调度</li>
              <li>等待当前运行的任务完成</li>
              <li>在所有任务完成后，可以安全重启服务器</li>
            </ul>
            确定要继续吗？
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)}>
            取消
          </Button>
          <Button onClick={handleInitiateShutdown} color="warning" variant="contained">
            确认
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default ShutdownControl;
