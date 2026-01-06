# 🎮 武林英雄离线助手

> 全自动智能游戏助手 - 解放双手，轻松挂机！自动完成日常任务、竞技场、副本挑战、幻境闯关等所有重复性操作。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18%2B-blue)](https://reactjs.org/)

---

## 🏯 关于《武林英雄》

《武林英雄》是由**九维网（9wee）**运营的经典武侠RPG网页游戏，于**2008年12月**正式公测，至今已有**16年**的历史，是国服最长寿的网页游戏之一。

### 🎖️ 辉煌成就
- 🏆 **2009年金翎奖** - 荣获"中国游戏奥斯卡"最佳网页游戏大奖，获得超过2万票遥遥领先
- 🌏 **海外发行** - 2010年推出韩国版、日本版，将中国武侠文化推向海外
- 👥 **持续运营** - 从2008年至今仍在稳定运营，拥有大量忠实玩家群体

### 🎭 游戏特色
- **战国背景** - 以战国时期为历史背景，恢宏的武侠世界观
- **职业平衡** - 邪皇、武神、英豪、剑尊、天煞五大职业，各有特色
- **竞技PK** - 强烈的PK系统，纯粹的武侠竞技体验
- **办公休闲** - 被誉为"最适合办公室玩的竞技类网页游戏"
- **六大幻境** - 封神异志、平倭群英传、武林群侠传、三国鼎立、乱世群雄、绝代风华

### 🔗 官方网站
- [武林英雄官网](http://hero.9wee.com/) - [九维网](http://www.9wee.com/)

---

## ✨ 核心功能

### 🤖 全自动日常任务
- **每日必做**: 自动签到、托管竞技场、托管任务、训练、领取礼包
- **幻境挑战**: 6大幻境全自动闯关，支持自定义策略
- **副本挑战**: 根据配置自动挑战副本，智能重试
- **周期任务**: 周一、周三、周六专属任务自动执行
- **任务调度**: 灵活的时间调度系统 - 每日、每小时、每周定时执行

### 👥 多账号管理
- 同时管理多个游戏账号
- 每个账号独立配置策略
- 批量操作，高效便捷

### ⚙️ 高度可定制
- 每个职业自定义技能组合
- 逐层自定义挑战策略
- 自动复活、自动购买次数、失败自动切换
- 账号间自动互抓奴隶

### 📊 实时监控
- Server-Sent Events 实时日志推送
- 战斗进度实时追踪
- 连接状态监控
- 历史日志文件查看

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Node.js 16+
- Azure Table Storage 账号（用于数据存储）

### 后端安装

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入你的配置
uvicorn main:app --reload
```

### 前端安装

```bash
cd frontend
npm install
cp .env.example .env
# 编辑 .env 填入你的 API 配置
npm start
```

### 配置说明

在 `backend` 目录创建 `.env` 文件：

```env
# Azure Table Storage
connection_string=<你的Azure连接字符串>

# API 配置
API_KEY=<随机生成的API密钥>
API_PORT=8081
JWT_SECRET_KEY=<你的JWT密钥>

# SMTP 邮件配置（用于用户注册）
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<你的邮箱>
SMTP_PASSWORD=<你的邮箱密码或应用密码>
```

## 🎯 使用流程

1. **注册/登录**: 邮箱注册或使用 Google OAuth 登录
2. **添加游戏账号**: 使用内置的 Cookie 提取工具添加游戏账号
3. **配置策略**: 为每个账号设置幻境挑战策略和技能配置
4. **调度任务**: 启用定时任务或手动执行
5. **监控进度**: 实时查看任务执行日志

## 🛠️ 技术栈

### 后端
- **FastAPI** - 现代化 Python Web 框架
- **Azure Table Storage** - NoSQL 数据库存储账号和设置
- **Playwright** - 浏览器自动化用于 Cookie 提取
- **BeautifulSoup4** - HTML 解析游戏响应
- **Python Schedule** - 任务调度系统

### 前端
- **React 18** - UI 框架
- **Material-UI (MUI)** - 组件库
- **Axios** - HTTP 客户端
- **Server-Sent Events** - 实时日志流

## 📖 配置示例

### 幻境挑战策略

```javascript
// 自动通关某个幻境
"封神异志": ""

// 跳过某个幻境
// (不包含在设置中即可)

// 自定义楼层策略
"武林群侠传": "5:空蓝|27:NPC|30:切换"

// 特定BOSS使用单数血挑战
"封神异志": "48:奇数血"
```

### 定时任务配置

```javascript
// 每日早上8点执行日常任务
{
  "id": "morning_routine",
  "type": "daily",
  "hour": 8,
  "minute": 0,
  "enabled": true
}
```

## 🎮 支持的游戏功能

### 日常任务
- ✅ 设置技能配置
- ✅ 自动签到
- ✅ 托管竞技场
- ✅ 托管任务
- ✅ 抽幻化球、冲锋陷阵
- ✅ 训练
- ✅ 领取每日好礼和豪礼
- ✅ 免费客房有礼
- ✅ 抽取黄金宝石
- ✅ 折磨/安抚奴隶
- ✅ 激活美女卡
- ✅ 购买60级瑕疵石
- ✅ 武馆培养
- ✅ 跨服任务
- ✅ 渑池挑战
- ✅ 怒海争锋

### 周期任务
- ✅ 周一：战马饲料、纳贤阁
- ✅ 周三：奖励兑换、幻境领次数、跨服副本
- ✅ 周六：红颜探索、兑换坐骑宝石

### 幻境挑战
- 封神异志、平倭群英传、武林群侠传
- 三国鼎立、乱世群雄、绝代风华
- 支持逐层自定义策略
- 自动选择最优技能组合

## 🤝 贡献

欢迎贡献代码！请随时提交 Pull Request。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m '添加某个很酷的功能'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📜 开源协议

本项目采用 MIT 协议 - 详见 [LICENSE](LICENSE) 文件

## ⚠️ 免责声明

本工具仅供学习交流使用，请遵守游戏服务条款，合理使用。

## 🙏 致谢

- 为武林英雄游戏社区打造
- 感谢所有贡献者和用户的支持

---

**用心为武林英雄玩家打造 ❤️**

[Star](https://github.com/yourusername/heroweb/stargazers) · [Fork](https://github.com/yourusername/heroweb/fork) · [提问题](https://github.com/yourusername/heroweb/issues)
# Social preview image
