export const HALLS = [
  "封神异志",
  "平倭群英传",
  "武林群侠传",
  "三国鼎立",
  "乱世群雄",
  "绝代风华"
];

export const COOKIE_HELP_TEXT = {
  title: "如何获取游戏 Cookie 字符串：",
  steps: [
    "在浏览器中打开游戏网址并登录账号。",
    "按 F12（或 Ctrl+Shift+I）打开开发者工具。",
    "切换到 Application（或 存储/Storage）标签页。",
    "在左侧栏点击 Cookies，选择游戏网址。",
    "找到名为 weeCookie 和 50hero_session 的 Cookie：",
    "将两个 Cookie 字符串分别粘贴到下方输入框。"
  ],
  note: "示例: weeCookie=xxxx 和 50hero_session=yyyy"
};

// API URL Configuration Utilities
export const API_URL_HELP = {
  title: "如何配置 API URL：",
  methods: [
    {
      name: "URL 参数",
      description: "在网址后添加 ?api_url=你的API地址",
      example: "http://localhost:3000?api_url=http://localhost:8080/api"
    },
    {
      name: "浏览器控制台",
      description: "按 F12 打开控制台，输入以下命令：",
      example: "setCustomApiUrl('http://localhost:8080/api')"
    },
    {
      name: "环境变量",
      description: "设置 REACT_APP_API_URL 环境变量",
      example: "REACT_APP_API_URL=http://localhost:8080/api npm start"
    }
  ],
  note: "优先级：URL参数 > 本地存储 > 环境变量 > 默认地址"
}; 