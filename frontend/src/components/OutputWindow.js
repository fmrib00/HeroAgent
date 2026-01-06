import React, { useState } from "react";
import { Paper, Box, Button, Tooltip, Typography, Menu, MenuItem } from "@mui/material";
import { HALLS } from "../utils/constants";
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';

function OutputWindow({ output, onGetInfo, onGetDuelInfo, onHallCombat, onStopCombat, onViewLastRun, onOpenLogViewer, selectedCount, onHallChallenge, username, selected, onOpenExecuteCommand, onOlympics, onBuyDuelMedal, onFanBadge, onAutoGift, onLottery, onZonghengChallenge, advanced = false }) {
  const [olympicsAnchorEl, setOlympicsAnchorEl] = useState(null);
  const olympicsMenuOpen = Boolean(olympicsAnchorEl);
  
  const [lotteryAnchorEl, setLotteryAnchorEl] = useState(null);
  const lotteryMenuOpen = Boolean(lotteryAnchorEl);
  
  const [medalAnchorEl, setMedalAnchorEl] = useState(null);
  const medalMenuOpen = Boolean(medalAnchorEl);

  const availableMatches = ['职业赛', '单人赛', '多人赛', '乱战赛', '纵横'];
  const availableLotteryTypes = ['巅峰赛', '全明星'];

  const handleOlympicsMenuOpen = (event) => {
    setOlympicsAnchorEl(event.currentTarget);
  };

  const handleOlympicsMenuClose = () => {
    setOlympicsAnchorEl(null);
  };

  const handleOlympicsSelect = (matchType) => {
    handleOlympicsMenuClose();
    if (onOlympics) {
      onOlympics(matchType);
    }
  };

  const handleLotteryMenuOpen = (event) => {
    setLotteryAnchorEl(event.currentTarget);
  };

  const handleLotteryMenuClose = () => {
    setLotteryAnchorEl(null);
  };

  const handleLotterySelect = (lotteryType) => {
    handleLotteryMenuClose();
    if (onLottery) {
      onLottery(lotteryType);
    }
  };

  const handleMedalMenuOpen = (event) => {
    setMedalAnchorEl(event.currentTarget);
  };

  const handleMedalMenuClose = () => {
    setMedalAnchorEl(null);
  };

  const handleBuyMedal = () => {
    handleMedalMenuClose();
    if (onBuyDuelMedal) {
      onBuyDuelMedal(true);
    }
  };

  const handleBuyMedalSmall = () => {
    handleMedalMenuClose();
    if (onBuyDuelMedal) {
      onBuyDuelMedal(false);
    }
  };

  const handleFanBadge = () => {
    handleMedalMenuClose();
    if (onFanBadge) {
      onFanBadge();
    }
  };
  return (
    <Box sx={{ flex: 1 }}>
      <Paper
        sx={{
          p: 2,
          height: 600,
          mb: 2,
          fontFamily: "monospace",
          whiteSpace: "pre-wrap",
          overflowY: "auto"
        }}
        ref={el => {
          if (el) {
            el.scrollTop = el.scrollHeight;
          }
        }}
        id="output-window"
      >
        {output}
      </Paper>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mb: 2 }}>
        {/* First row of buttons */}
        <Box sx={{ display: "flex", gap: 2 }}>
          <Button 
            variant="contained" 
            onClick={onGetInfo} 
            disabled={selectedCount === 0}
          >
            获取角色信息
          </Button>
          <Button 
            variant="contained" 
            color="success"
            onClick={onGetDuelInfo} 
            disabled={selectedCount === 0}
          >
            获取跨服信息
          </Button>
          <Button 
            variant="contained" 
            color="info" 
            onClick={onHallCombat} 
            disabled={selectedCount === 0}
          >
            幻境挑战
          </Button>
          <Button 
            variant="contained" 
            color="error" 
            onClick={onStopCombat} 
            disabled={selectedCount === 0}
          >
            停止挑战
          </Button>
          <Button 
            variant="outlined" 
            color="primary"
            onClick={onViewLastRun}
            title="查看最新日志"
          >
            查看最新日志
          </Button>
          <Button variant="outlined" onClick={onOpenLogViewer}>
            日志管理
          </Button>
        </Box>
        {/* Second row of buttons */}
        <Box sx={{ display: "flex", gap: 2 }}>
          {advanced && (
            <Button 
              variant="outlined" 
              color="secondary"
              onClick={onOpenExecuteCommand}
              disabled={selectedCount === 0}
            >
              执行命令
            </Button>
          )}
          <Button
            variant="contained"
            color="warning"
            onClick={handleOlympicsMenuOpen}
            disabled={selectedCount === 0}
            endIcon={<ArrowDropDownIcon />}
          >
            报名比赛
          </Button>
          <Menu
            anchorEl={olympicsAnchorEl}
            open={olympicsMenuOpen}
            onClose={handleOlympicsMenuClose}
          >
            {availableMatches.map((match) => (
              <MenuItem key={match} onClick={() => handleOlympicsSelect(match)}>
                {match}
              </MenuItem>
            ))}
          </Menu>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleLotteryMenuOpen}
            disabled={selectedCount === 0}
            endIcon={<ArrowDropDownIcon />}
          >
            联赛竞猜
          </Button>
          <Menu
            anchorEl={lotteryAnchorEl}
            open={lotteryMenuOpen}
            onClose={handleLotteryMenuClose}
          >
            {availableLotteryTypes.map((lotteryType) => (
              <MenuItem key={lotteryType} onClick={() => handleLotterySelect(lotteryType)}>
                {lotteryType}
              </MenuItem>
            ))}
          </Menu>
          <Button
            variant="contained"
            color="info"
            onClick={handleMedalMenuOpen}
            disabled={selectedCount === 0}
            endIcon={<ArrowDropDownIcon />}
          >
            联盟徽章
          </Button>
          <Menu
            anchorEl={medalAnchorEl}
            open={medalMenuOpen}
            onClose={handleMedalMenuClose}
          >
            <MenuItem onClick={handleBuyMedal}>
              买通用徽章礼包(大)
            </MenuItem>
            <MenuItem onClick={handleBuyMedalSmall}>
              买单个通用徽章礼包
            </MenuItem>
            <MenuItem onClick={handleFanBadge}>
              粉丝章兑换
            </MenuItem>
          </Menu>
          <Button
            variant="contained"
            color="secondary"
            onClick={onAutoGift}
            disabled={selectedCount === 0}
          >
            领礼包
          </Button>
          {advanced && (
            <Button
              variant="contained"
              color="warning"
              onClick={onZonghengChallenge}
              disabled={selectedCount === 0}
            >
              纵横天下
            </Button>
          )}
        </Box>
      </Box>
      
      {/* Individual Hall Challenge Section */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
            指定幻境挑战
          </Typography>
          {selectedCount === 0 && (
            <Typography variant="caption" color="warning.main" sx={{ fontSize: '0.65rem' }}>
              (请先选择一个账号)
            </Typography>
          )}
          {selectedCount > 0 && (
            <Typography variant="caption" color="success.main" sx={{ fontSize: '0.65rem' }}>
              (已选择 {selectedCount} 个账号)
            </Typography>
          )}
        </Box>
        
        {/* Individual Hall Challenge Buttons */}
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          {HALLS.map((hall) => (
            <Tooltip 
              key={hall}
              title={
                selectedCount === 0 
                  ? "请先选择一个账号" 
                  : `为 ${selectedCount} 个账号挑战 ${hall}`
              }
              placement="top"
            >
              <span>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => onHallChallenge(hall)}
                  disabled={selectedCount === 0}
                  sx={{ 
                    minWidth: 'auto',
                    fontSize: '0.75rem',
                    px: 1,
                    py: 0.5
                  }}
                >
                  {hall}
                </Button>
              </span>
            </Tooltip>
          ))}
        </Box>
      </Box>
      
    </Box>
  );
}

export default OutputWindow; 