import React from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Paper,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  IconButton,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

function FeatureGuide({ open, onClose }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          maxHeight: "90vh",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          bgcolor: "#1976d2",
          color: "white",
          pb: 2,
        }}
      >
        <Typography variant="h6" component="div">
          功能说明
        </Typography>
        <IconButton
          onClick={onClose}
          sx={{ color: "white" }}
          size="small"
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ p: 3 }}>
        <Box sx={{ overflowY: "auto", maxHeight: "calc(90vh - 150px)" }}>
          {/* 产品概述 */}
          <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: "#f5f5f5" }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              产品概述
            </Typography>
            <Typography variant="body2" color="text.secondary">
              武林英雄离线助手是一款专为《武林英雄》网络游戏设计的全自动智能游戏助手。针对游戏复杂的操作流程，实现了完全自动化的任务执行系统，确保完成每日所有任务、领取每日每周常规福利，参与各类竞技活动和联盟争霸活动。
            </Typography>
          </Paper>

          {/* 核心功能 */}
          <Typography variant="h5" gutterBottom sx={{ mt: 3, mb: 2, color: "#1976d2" }}>
            核心功能
          </Typography>

          {/* 1. 日常任务自动化 */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              1. 日常任务自动化
            </Typography>
            
            <Box sx={{ mb: 2 }}>
              <Chip label="日常任务(早上)" size="small" sx={{ mb: 1, bgcolor: "#e3f2fd" }} />
              <List dense>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 设置技能配置、自动签到、托管竞技场、托管任务" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 抽幻化球、抽冲锋陷阵、训练" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 领取每日好礼和豪里、免费客房有礼、抽取黄金宝石" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 折磨奴隶、安抚奴隶、激活美女卡" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 购买60级瑕疵石、武馆培养、领取礼包" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 跨服任务、渑池挑战" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 怒海争锋自动升级，自动海战" />
                </ListItem>
              </List>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Chip label="日常任务(晚上)" size="small" sx={{ mb: 1, bgcolor: "#e3f2fd" }} />
              <List dense>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 武馆培养、分配武馆经验、化龙榜挑战" />
                </ListItem>
              </List>
            </Box>

            <Box>
              <Chip label="副本、打怪、渑池" size="small" sx={{ mb: 1, bgcolor: "#e3f2fd" }} />
              <List dense>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 副本挑战、打怪、渑池竞技场奖励" />
                </ListItem>
                <ListItem sx={{ py: 0.5 }}>
                  <ListItemText primary="✅ 领取奖励、捐献物品、激活美女卡、武馆培养" />
                </ListItem>
              </List>
            </Box>
          </Paper>

          {/* 2. 竞技活动自动化 */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              2. 竞技活动自动化
            </Typography>
            <List dense>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 每日竞技场（在早上任务中自动执行）" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 风云争霸：自动参与风云争霸活动、设置技能配置" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 化龙榜挑战（在晚上任务中自动执行）" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 跨服任务：跨服试炼、抓跨服奴隶" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 角色互奴：自动互相抓取同账号下游戏角色的奴隶，智能处理账号间的奴隶关系" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 踢护武馆：自动护馆踢馆指定武馆，自动开启武馆美女图" />
              </ListItem>
            </List>
          </Paper>

          {/* 3. 周期性任务 */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              3. 周期性任务
            </Typography>
            <List dense>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 周一任务：自动抽取战马饲料、纳贤阁自动挑战，自动招募门客" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 周三任务：奖励兑换、幻境领次数、跨服副本" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 周六任务：红颜探索、兑换坐骑宝石" />
              </ListItem>
            </List>
          </Paper>

          {/* 4. 福利领取 */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              4. 福利领取
            </Typography>
            <List dense>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="✅ 自动领取礼包：自动领取每日、每周常规福利礼包（在早上任务中自动执行）" />
              </ListItem>
            </List>
          </Paper>

          {/* 5. 幻境挑战 */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              5. 幻境挑战
            </Typography>
            <List dense>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText 
                  primary="✅ 全自动幻境挑战"
                  secondary="支持多个幻境场景（封神异志、平倭群英传、三国鼎立、乱世群雄、绝代风华、武林群侠传），智能技能配置和战斗策略，支持复活重打、客房补血、自动买次数等高级功能"
                />
              </ListItem>
            </List>
          </Paper>

          {/* 幻境设置详解 */}
          <Paper elevation={2} sx={{ p: 3, mb: 2, bgcolor: "#e3f2fd" }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2", fontWeight: "bold" }}>
              🏛️ 幻境设置详解
            </Typography>
            
            <Box sx={{ mt: 2, mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                幻境设置方式
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                系统支持6个幻境场景的配置：封神异志、平倭群英传、武林群侠传、三国鼎立、乱世群雄、绝代风华
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1.5, borderRadius: 1, mb: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: "bold", mb: 0.5 }}>
                  每个幻境有三种设置方式：
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • <strong>通关</strong>：点击"通关"按钮，设置为空字符串，系统会自动通关该幻境<br/>
                  • <strong>跳过</strong>：点击"跳过"按钮，不保存该项，该幻境将被跳过，不进行挑战<br/>
                  • <strong>自定义</strong>：在输入框中输入自定义设置内容
                </Typography>
              </Box>
            </Box>
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                1. 随意设置打塔顺序
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                在自定义输入框中设置每层的挑战目标，格式：<code>层数:目标类型</code>
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1, borderRadius: 1, mb: 1, fontFamily: "monospace", fontSize: "0.85rem" }}>
                {"示例：22:NPC | 25:小怪 | 30:NPC | 35:退出"}
              </Box>
              <Typography variant="body2" color="text.secondary">
                • <code>22:NPC</code> - 第22层挑战NPC<br/>
                • <code>25:小怪</code> - 第25层挑战小怪<br/>
                • <code>30:退出</code> - 第30层后退出<br/>
                • <code>30:切换</code> - 第30层后切换幻境<br/>
                • <code>5:空蓝|27:切换</code> - 第5层空蓝挑战，第27层后切换
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                2. 自动换塔功能
              </Typography>
              <Typography variant="body2" color="text.secondary">
                当挑战失败且启用"失败切换"功能时，系统会自动切换到其他幻境继续挑战，智能判断挑战次数，避免浪费。
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                3. 自动根据角色类型设置最佳技能
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                系统内置了各职业（邪皇、武神、英豪、天煞、剑尊等）在不同幻境、不同层数的最佳技能配置，自动为每层选择最优的主技能和辅助技能组合。
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1, borderRadius: 1, mb: 1, fontFamily: "monospace", fontSize: "0.85rem" }}>
                {"自定义技能：27:NPC!(穿心0天,{怒澜式,蚀蛊式})"}
              </Box>
              <Typography variant="body2" color="text.secondary">
                支持自定义技能设置，格式：<code>{"层数:NPC!(主技能,{辅助技能1,辅助技能2})"}</code>
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                4. 失败切换
              </Typography>
              <Typography variant="body2" color="text.secondary">
                启用后，当挑战失败且复活重打次数用完后，自动切换到其他幻境继续挑战，避免卡在同一层浪费时间。
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                5. 自动买次数
              </Typography>
              <Typography variant="body2" color="text.secondary">
                启用后，当本周挑战次数用完后，系统会自动购买挑战次数继续挑战，确保能够完成所有预设的挑战目标。
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                6. 封神赵公明自动单数血挑战
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                针对封神异志中的赵公明等特殊BOSS，支持设置"奇数血"挑战模式。
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1, borderRadius: 1, mb: 1, fontFamily: "monospace", fontSize: "0.85rem" }}>
                {"设置：48:奇数血"}
              </Box>
              <Typography variant="body2" color="text.secondary">
                例如：<code>48:奇数血</code> 表示第48层使用奇数血挑战，系统会自动将角色血量调整为单数后挑战，提高挑战成功率。
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                7. 自动使用积分买经验
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                系统会自动使用幻境积分购买"灵台清明"（经验道具），可设置保留积分数量。
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1, borderRadius: 1, mb: 1, fontFamily: "monospace", fontSize: "0.85rem" }}>
                设置：灵台清明:100000（保留10万积分）
              </Box>
              <Typography variant="body2" color="text.secondary">
                剩余积分自动购买经验道具，最大化经验收益。
              </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                8. 自动购买黑铁矿
              </Typography>
              <Typography variant="body2" color="text.secondary">
                每次挑战开始前，系统会自动使用幻境积分购买2件黑铁矿。黑铁矿是重要的强化材料，自动购买确保资源充足。
              </Typography>
            </Box>

            <Divider sx={{ my: 3 }} />

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                设置示例
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1.5, borderRadius: 1, mb: 1 }}>
                <Typography variant="body2" color="text.secondary" component="div">
                  • <strong>封神异志</strong>：<code>48:奇数血</code> - 第48层使用奇数血挑战赵公明<br/>
                  • <strong>武林群侠传</strong>：<code>5:切换</code> - 第5层后切换幻境<br/>
                  • <strong>乱世群雄</strong>：<code>5:空蓝|27:切换</code> - 第5层空蓝挑战，第27层后切换<br/>
                  • <strong>三国鼎立</strong>：通关（空字符串）- 自动通关整个幻境<br/>
                  • <strong>平倭群英传</strong>：跳过 - 不挑战该幻境
                </Typography>
              </Box>
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: "bold" }}>
                底部选项说明
              </Typography>
              <Box sx={{ bgcolor: "#fff", p: 1.5, borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary" component="div">
                  • <strong>复活重打</strong>：挑战失败后自动复活并重新挑战（最多3次）<br/>
                  • <strong>客房补血</strong>：每10层自动使用客房补血功能<br/>
                  • <strong>自动买次数</strong>：挑战次数用完后自动购买次数继续挑战<br/>
                  • <strong>失败切换</strong>：挑战失败且复活次数用完后，自动切换到其他幻境继续挑战
                </Typography>
              </Box>
            </Box>
          </Paper>


          {/* 6. 任务调度系统 */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              6. 任务调度系统
            </Typography>
            <List dense>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="• 灵活调度：支持每日、每小时、每周三种任务类型" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="• 自定义时间：可为每个任务设置具体的执行时间（小时和分钟）" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="• 账号选择：支持为每个任务选择特定账号执行" />
              </ListItem>
              <ListItem sx={{ py: 0.5 }}>
                <ListItemText primary="• 一键开关：可随时启用或禁用任务调度功能" />
              </ListItem>
            </List>
          </Paper>

          <Divider sx={{ my: 3 }} />

          {/* 主要特性 */}
          <Typography variant="h5" gutterBottom sx={{ mt: 3, mb: 2, color: "#1976d2" }}>
            主要特性
          </Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 2 }}>
            <Paper elevation={1} sx={{ p: 2, bgcolor: "#e3f2fd" }}>
              <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold" }}>
                ✨ 全自动化执行
              </Typography>
              <Typography variant="body2" color="text.secondary">
                无需人工干预，系统自动完成所有游戏任务，智能处理各种游戏场景和异常情况
              </Typography>
            </Paper>
            <Paper elevation={1} sx={{ p: 2, bgcolor: "#f3e5f5" }}>
              <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold" }}>
                🎯 多账号管理
              </Typography>
              <Typography variant="body2" color="text.secondary">
                支持管理多个游戏账号，可为不同账号配置不同的任务策略，批量操作提高效率
              </Typography>
            </Paper>
            <Paper elevation={1} sx={{ p: 2, bgcolor: "#e8f5e9" }}>
              <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold" }}>
                ⚙️ 灵活配置
              </Typography>
              <Typography variant="body2" color="text.secondary">
                每个账号可独立配置幻境挑战策略，支持自定义技能组合和战斗参数
              </Typography>
            </Paper>
            <Paper elevation={1} sx={{ p: 2, bgcolor: "#fff3e0" }}>
              <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold" }}>
                📊 实时监控
              </Typography>
              <Typography variant="body2" color="text.secondary">
                实时查看任务执行日志，查看账号信息和战斗状态，连接状态监控和错误提示
              </Typography>
            </Paper>
          </Box>

          <Divider sx={{ my: 3 }} />

          {/* 使用说明 */}
          <Typography variant="h5" gutterBottom sx={{ mt: 3, mb: 2, color: "#1976d2" }}>
            快速开始
          </Typography>
          <Paper elevation={1} sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold" }}>
              1. 注册与登录
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              访问系统，点击"注册"按钮，输入邮箱地址完成注册。系统将自动生成密码并发送到您的邮箱，使用邮箱和密码登录系统。
            </Typography>

            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold", mt: 2 }}>
              2. 添加游戏账号
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              登录后，点击"添加账号"按钮，输入账号名称，自动抓取游戏Cookie，配置账号的幻境挑战、副本等设置（可选），保存账号信息。
            </Typography>

            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: "bold", mt: 2 }}>
              3. 配置任务调度
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              点击顶部工具栏的"全局设置"图标，在任务调度列表中，为需要自动执行的任务设置启用状态、执行时间和账号选择，确保"任务调度总开关"已开启，保存设置。
            </Typography>
          </Paper>

          <Divider sx={{ my: 3 }} />

          {/* 技术支持 */}
          <Box sx={{ textAlign: "center", py: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ color: "#1976d2" }}>
              技术支持
            </Typography>
            <Typography variant="body2" color="text.secondary">
              如遇到问题或需要帮助，请通过 GitHub Issues 联系项目维护者。
            </Typography>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ bgcolor: "#f5f5f5", px: 3, py: 2 }}>
        <Button onClick={onClose} variant="contained" color="primary">
          关闭
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default FeatureGuide;

