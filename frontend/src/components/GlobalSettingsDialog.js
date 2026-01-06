import React, { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Checkbox,
  Switch,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Alert,
  CircularProgress,
  Select,
  MenuItem,
  FormControl
} from "@mui/material";
import { api } from "../utils/api";

function GlobalSettingsDialog({ open, onClose, username, accounts, selectedAccounts, isAdmin = false }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  
  // Jobs data
  const [jobsTable, setJobsTable] = useState({});
  const [jobSettings, setJobSettings] = useState({});
  const [masterJobSchedulingEnabled, setMasterJobSchedulingEnabled] = useState(true);
  
  // Form validation
  const [validationErrors, setValidationErrors] = useState({});
  
  // Job execution state
  const [executingJobs, setExecutingJobs] = useState(new Set());

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // Load jobs table and user settings in parallel
      // getJobsTable now automatically refreshes the cache and loads from database
      const [jobsResponse, settingsResponse] = await Promise.all([
        api.getJobsTable(),
        api.getUserSettings(username, isAdmin)
      ]);
      
      setJobsTable(jobsResponse.data.jobs_table || {});
      
      const userSettings = settingsResponse.data;
      const loadedJobSettings = userSettings.job_settings || {};
      
      // Load master job scheduling setting
      setMasterJobSchedulingEnabled(userSettings.job_scheduling_enabled !== false);
      
      // Initialize job settings with defaults if not set
      const initializedSettings = {};
      Object.keys(jobsResponse.data.jobs_table || {}).forEach(jobId => {
        const jobConfig = jobsResponse.data.jobs_table[jobId];
        
        // Check if we have saved settings for this job
        if (loadedJobSettings[jobId]) {
          // Use saved settings, but ensure hour is a string for the input field
          initializedSettings[jobId] = {
            enabled: loadedJobSettings[jobId].enabled || false,
            hour: String(loadedJobSettings[jobId].hour !== undefined ? loadedJobSettings[jobId].hour : (jobConfig.default_hour || 0)),
            day_of_week: loadedJobSettings[jobId].day_of_week !== undefined ? loadedJobSettings[jobId].day_of_week : (jobConfig.default_day_of_week || 0),
            type: loadedJobSettings[jobId].type || jobConfig.type,
            minute: String(loadedJobSettings[jobId].minute !== undefined ? loadedJobSettings[jobId].minute : (jobConfig.default_minute || 0))
          };
        } else {
          // Use defaults
          initializedSettings[jobId] = {
            enabled: false,
            hour: String(jobConfig.default_hour || 0),
            day_of_week: jobConfig.default_day_of_week || 0,
            type: jobConfig.type,
            minute: String(jobConfig.default_minute || 0)
          };
        }
      });
      
      setJobSettings(initializedSettings);
    } catch (err) {
      console.error("Failed to load data:", err);
      setError("加载数据失败: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, [username]);

  // Load data when dialog opens
  useEffect(() => {
    if (open && username) {
      loadData();
    }
  }, [open, username, loadData]);

  const validateJobSettings = () => {
    const errors = {};
    
    Object.keys(jobSettings).forEach(jobId => {
      const settings = jobSettings[jobId];
      
      if (settings.enabled && settings.type === 'daily') {
        const hour = parseInt(settings.hour);
        if (isNaN(hour) || hour < 0 || hour > 23) {
          errors[jobId] = "小时数必须在 0-23 之间";
        }
        
        const minute = parseInt(settings.minute);
        if (isNaN(minute) || minute < 0 || minute > 59) {
          errors[jobId] = "分钟数必须在 0-59 之间";
        }
      }
      
      if (settings.enabled && settings.type === 'weekly') {
        const dayOfWeek = parseInt(settings.day_of_week);
        if (isNaN(dayOfWeek) || dayOfWeek < 0 || dayOfWeek > 6) {
          errors[jobId] = "星期数必须在 0-6 之间 (0=周一, 6=周日)";
        }
        
        const hour = parseInt(settings.hour);
        if (isNaN(hour) || hour < 0 || hour > 23) {
          errors[jobId] = "小时数必须在 0-23 之间";
        }
      }

      if (settings.enabled && settings.type === 'hourly') {
        const minute = parseInt(settings.minute);
        if (isNaN(minute) || minute < 0 || minute > 59) {
          errors[jobId] = "分钟数必须在 0-59 之间";
        }
      }
    });
    
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleJobToggle = (jobId) => {
    setJobSettings(prev => ({
      ...prev,
      [jobId]: {
        ...prev[jobId],
        enabled: !prev[jobId].enabled
      }
    }));
    
    // Clear validation error for this job
    if (validationErrors[jobId]) {
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[jobId];
        return newErrors;
      });
    }
  };

  const handleMasterToggle = () => {
    setMasterJobSchedulingEnabled(!masterJobSchedulingEnabled);
  };

  const handleHourChange = (jobId, hour) => {
    // Only allow digits and empty string
    const cleanHour = hour.replace(/[^0-9]/g, '');
    
    // Limit to 2 digits max
    const limitedHour = cleanHour.length > 2 ? cleanHour.slice(0, 2) : cleanHour;
    
    setJobSettings(prev => ({
      ...prev,
      [jobId]: {
        ...prev[jobId],
        hour: limitedHour
      }
    }));
    
    // Clear validation error for this job
    if (validationErrors[jobId]) {
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[jobId];
        return newErrors;
      });
    }
  };

  const handleMinuteChange = (jobId, minute) => {
    // Only allow digits and empty string
    const cleanMinute = minute.replace(/[^0-9]/g, '');
    
    // Limit to 2 digits max
    const limitedMinute = cleanMinute.length > 2 ? cleanMinute.slice(0, 2) : cleanMinute;
    
    setJobSettings(prev => ({
      ...prev,
      [jobId]: {
        ...prev[jobId],
        minute: limitedMinute
      }
    }));
    
    // Clear validation error for this job
    if (validationErrors[jobId]) {
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[jobId];
        return newErrors;
      });
    }
  };

  const handleTypeChange = (jobId, type) => {
    setJobSettings(prev => ({
      ...prev,
      [jobId]: {
        ...prev[jobId],
        type: type
      }
    }));
  };

  const handleDayOfWeekChange = (jobId, dayOfWeek) => {
    setJobSettings(prev => ({
      ...prev,
      [jobId]: {
        ...prev[jobId],
        day_of_week: dayOfWeek
      }
    }));
  };

  const handleRefreshCache = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    
    try {
      await api.refreshCache(username);
      setSuccess("缓存刷新成功！");
      setTimeout(() => {
        setSuccess("");
      }, 2000);
    } catch (err) {
      console.error("Failed to refresh cache:", err);
      setError("刷新缓存失败: " + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!validateJobSettings()) {
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");
    
    try {
      // Convert hour/minute strings to integers before saving
      const processedJobSettings = { ...jobSettings };
      Object.keys(processedJobSettings).forEach(jobId => {
        const settings = processedJobSettings[jobId];
        
        // Always convert hour to integer if it exists
        if (settings.hour !== undefined) {
          const hourValue = settings.hour;
          const parsedHour = parseInt(hourValue);
          processedJobSettings[jobId] = {
            ...settings,
            hour: isNaN(parsedHour) ? 0 : parsedHour
          };
        }
        // Convert minute to integer if it exists
        if (settings.minute !== undefined) {
          const minuteValue = settings.minute;
          const parsedMinute = parseInt(minuteValue);
          processedJobSettings[jobId] = {
            ...processedJobSettings[jobId],
            minute: isNaN(parsedMinute) ? 0 : parsedMinute
          };
        }
        
        // Convert day_of_week to integer for weekly jobs
        if (settings.type === 'weekly' && settings.day_of_week !== undefined) {
          const dayOfWeekValue = settings.day_of_week;
          const parsedDayOfWeek = parseInt(dayOfWeekValue);
          processedJobSettings[jobId] = {
            ...processedJobSettings[jobId],
            day_of_week: isNaN(parsedDayOfWeek) ? 0 : parsedDayOfWeek
          };
        }
      });
      
      await api.setJobSettings(username, processedJobSettings, masterJobSchedulingEnabled, isAdmin);
      
      setSuccess("设置保存成功！");
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      console.error("Failed to save job settings:", err);
      setError("保存设置失败: " + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setError("");
    setSuccess("");
    setValidationErrors({});
    onClose();
  };

  const handleExecuteJob = async (jobId) => {
    setExecutingJobs(prev => new Set(prev).add(jobId));
    setError("");
    setSuccess("");
    
    try {
      // Convert selected accounts to array, or use all accounts if none selected
      const accountNames = selectedAccounts && selectedAccounts.length > 0 ? selectedAccounts : [];
      const response = await api.executeJob(jobId, accountNames, username, isAdmin);
      setSuccess(response.data.message || "任务执行成功！");
      setTimeout(() => {
        setSuccess("");
      }, 3000);
    } catch (err) {
      console.error("Failed to execute job:", err);
      setError("执行任务失败: " + (err.response?.data?.detail || err.message));
    } finally {
      setExecutingJobs(prev => {
        const newSet = new Set(prev);
        newSet.delete(jobId);
        return newSet;
      });
    }
  };

  const getDayOfWeekLabel = (dayOfWeek) => {
    const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return days[dayOfWeek] || '周一';
  };

  if (!username) return null;

  return (
    <Dialog open={open} onClose={handleCancel} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '1.1rem', fontWeight: 'bold', py: 1.5 }}>
        <Box>
          任务调度设置 - {username}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>
            任务调度总开关:
          </Typography>
          <Switch
            checked={masterJobSchedulingEnabled}
            onChange={handleMasterToggle}
            color="primary"
            size="small"
          />
        </Box>
      </DialogTitle>
      
      <DialogContent>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        )}
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {success}
          </Alert>
        )}
        
        {!loading && Object.keys(jobsTable).length > 0 && (
          <Box sx={{ mt: 0.5 }}>
            <Typography variant="h6" sx={{ mb: 1, color: 'primary.main', fontSize: '1rem' }}>
              任务配置
            </Typography>
            
            <TableContainer component={Paper} sx={{ mb: 1.5 }}>
              <Table size="small" sx={{ '& .MuiTableCell-root': { py: 0.5, px: 0.5 } }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ py: 1, px: 0.5, fontWeight: 'bold', fontSize: '0.8rem', width: '12%' }}>启用</TableCell>
                    <TableCell sx={{ py: 1, px: 0.5, fontWeight: 'bold', fontSize: '0.8rem', width: '35%' }}>任务名称</TableCell>
                    <TableCell sx={{ py: 1, px: 0.5, fontWeight: 'bold', fontSize: '0.8rem', width: '18%' }}>类型</TableCell>
                    <TableCell sx={{ py: 1, px: 0.5, fontWeight: 'bold', fontSize: '0.8rem', width: '20%' }}>时间</TableCell>
                    <TableCell sx={{ py: 1, px: 0.5, fontWeight: 'bold', fontSize: '0.8rem', width: '15%' }}>操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {Object.entries(jobsTable).map(([jobId, jobConfig]) => {
                    const settings = jobSettings[jobId] || { enabled: false, hour: jobConfig.default_hour || 0, type: jobConfig.type };
                    const hasError = !!validationErrors[jobId];
                    
                    return (
                      <TableRow key={jobId} sx={{ '&:last-child td': { borderBottom: 0 } }}>
                        <TableCell sx={{ py: 0.5, px: 0.5, width: '12%' }}>
                          <Checkbox
                            checked={settings.enabled}
                            onChange={() => handleJobToggle(jobId)}
                            color="primary"
                            size="small"
                          />
                        </TableCell>
                        <TableCell sx={{ py: 0.5, px: 0.5, width: '35%' }}>
                          <Typography variant="body2" sx={{ fontWeight: 'bold', fontSize: '0.75rem' }}>
                            {jobConfig.name}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ py: 0.5, px: 0.5, width: '18%' }}>
                          <FormControl size="small" sx={{ minWidth: 80 }}>
                            <Select
                              value={settings.type}
                              onChange={(e) => handleTypeChange(jobId, e.target.value)}
                              disabled={!settings.enabled}
                              sx={{ 
                                height: 26,
                                fontSize: '0.7rem',
                                '& .MuiSelect-select': { py: 0.5 }
                              }}
                            >
                              <MenuItem value="daily" sx={{ fontSize: '0.7rem' }}>每日</MenuItem>
                              <MenuItem value="hourly" sx={{ fontSize: '0.7rem' }}>每小时</MenuItem>
                              <MenuItem value="weekly" sx={{ fontSize: '0.7rem' }}>每周</MenuItem>
                            </Select>
                          </FormControl>
                        </TableCell>
                        <TableCell sx={{ py: 0.5, px: 0.5, width: '20%' }}>
                          {settings.type === 'daily' ? (
                            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                              <TextField
                                size="small"
                                value={settings.hour}
                                onChange={(e) => handleHourChange(jobId, e.target.value)}
                                disabled={!settings.enabled}
                                error={hasError}
                                helperText={hasError ? validationErrors[jobId] : ""}
                                placeholder="0-23"
                                inputProps={{ maxLength: 2 }}
                                sx={{ 
                                  width: 45,
                                  '& .MuiInputBase-root': { height: 26 },
                                  '& .MuiFormHelperText-root': { fontSize: '0.6rem', margin: 0 },
                                  '& input': { 
                                    textAlign: 'center',
                                    fontSize: '0.75rem'
                                  }
                                }}
                              />
                              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                                :
                              </Typography>
                              <TextField
                                size="small"
                                value={settings.minute}
                                onChange={(e) => handleMinuteChange(jobId, e.target.value)}
                                disabled={!settings.enabled}
                                error={hasError}
                                helperText={hasError ? validationErrors[jobId] : ""}
                                placeholder="0-59"
                                inputProps={{ maxLength: 2 }}
                                sx={{ 
                                  width: 45,
                                  '& .MuiInputBase-root': { height: 26 },
                                  '& .MuiFormHelperText-root': { fontSize: '0.6rem', margin: 0 },
                                  '& input': { 
                                    textAlign: 'center',
                                    fontSize: '0.75rem'
                                  }
                                }}
                              />
                            </Box>
                          ) : settings.type === 'weekly' ? (
                            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                              <FormControl size="small" sx={{ minWidth: 50 }}>
                                <Select
                                  value={settings.day_of_week}
                                  onChange={(e) => handleDayOfWeekChange(jobId, e.target.value)}
                                  disabled={!settings.enabled}
                                  sx={{ 
                                    height: 26,
                                    fontSize: '0.7rem',
                                    '& .MuiSelect-select': { py: 0.5 }
                                  }}
                                >
                                  {[0,1,2,3,4,5,6].map(day => (
                                    <MenuItem key={day} value={day} sx={{ fontSize: '0.7rem' }}>
                                      {getDayOfWeekLabel(day)}
                                    </MenuItem>
                                  ))}
                                </Select>
                              </FormControl>
                              <TextField
                                size="small"
                                value={settings.hour}
                                onChange={(e) => handleHourChange(jobId, e.target.value)}
                                disabled={!settings.enabled}
                                error={hasError}
                                helperText={hasError ? validationErrors[jobId] : ""}
                                placeholder="0-23"
                                inputProps={{ maxLength: 2 }}
                                sx={{ 
                                  width: 45,
                                  '& .MuiInputBase-root': { height: 26 },
                                  '& .MuiFormHelperText-root': { fontSize: '0.6rem', margin: 0 },
                                  '& input': { 
                                    textAlign: 'center',
                                    fontSize: '0.75rem'
                                  }
                                }}
                              />
                            </Box>
                          ) : (
                            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                                每小时 第
                              </Typography>
                              <TextField
                                size="small"
                                value={settings.minute}
                                onChange={(e) => handleMinuteChange(jobId, e.target.value)}
                                disabled={!settings.enabled}
                                error={hasError}
                                helperText={hasError ? validationErrors[jobId] : ""}
                                placeholder="0-59"
                                inputProps={{ maxLength: 2 }}
                                sx={{ 
                                  width: 45,
                                  '& .MuiInputBase-root': { height: 26 },
                                  '& .MuiFormHelperText-root': { fontSize: '0.6rem', margin: 0 },
                                  '& input': { 
                                    textAlign: 'center',
                                    fontSize: '0.75rem'
                                  }
                                }}
                              />
                              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                                分
                              </Typography>
                            </Box>
                          )}
                        </TableCell>
                        <TableCell sx={{ py: 0.5, px: 0.5, width: '15%' }}>
                          <Button
                            variant="outlined"
                            size="small"
                            onClick={() => handleExecuteJob(jobId)}
                            disabled={executingJobs.has(jobId)}
                            sx={{ 
                              fontSize: '0.7rem',
                              minWidth: 'auto',
                              px: 1,
                              py: 0.5,
                              height: 24
                            }}
                          >
                            {executingJobs.has(jobId) ? (
                              <CircularProgress size={12} />
                            ) : (
                              '立即执行'
                            )}
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
            
            {/* Summary Information */}
            <Box sx={{ mt: 1.5, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.3, fontWeight: 'bold', fontSize: '0.75rem' }}>
                设置说明:
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.3, fontSize: '0.7rem' }}>
                • <strong>每日任务</strong>: 在指定小时和分钟自动执行，时间使用中国时区 (UTC+8)
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.3, fontSize: '0.7rem' }}>
                • <strong>每小时任务</strong>: 每小时自动执行维护任务
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.3, fontSize: '0.7rem' }}>
                • <strong>每周任务</strong>: 在指定星期和时间自动执行，0=周一，6=周日
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.3, fontSize: '0.7rem' }}>
                • 勾选复选框启用任务，取消勾选禁用任务
              </Typography>
              <Typography variant="body2" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                当前已启用任务: {Object.values(jobSettings).filter(s => s.enabled).length} / {Object.keys(jobsTable).length}
              </Typography>
            </Box>
          </Box>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleCancel} disabled={saving}>
          取消
        </Button>
        <Button 
          variant="outlined" 
          onClick={handleRefreshCache}
          disabled={saving}
          sx={{ mr: 1 }}
        >
          刷新缓存
        </Button>
        <Button 
          variant="contained" 
          onClick={handleSave}
          disabled={saving || Object.keys(validationErrors).length > 0}
        >
          {saving ? <CircularProgress size={20} /> : "保存"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default GlobalSettingsDialog;