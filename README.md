# <h1 align="center">AI_JS_DEBUGGER</h1>

本项目是基于Chrome开发者协议(CDP)的AI自动化JavaScript逆向分析工具，通过AI自动调试前端JS，自动分析加解密算法、密钥等，自动生成分析报告以及mitmproxy脚本。

**声明：文中所涉及的技术、思路和工具仅供以安全为目的的学习交流使用，<u>任何人不得将其用于非法用途以及盈利等目的，否则后果自负</u>** 

## 功能特点

- 支持固定js文件断点、XHR请求断点
- XHR回溯，XHR模式下自动回溯顶层调用堆栈并自动断点
- 根据调用堆栈、js片段、作用域等断点调试信息自动调试
- 使用js hook获取AES、RSA等常见加密密钥/密文/明文
- 自动分析加解密算法、密钥、生成密钥方式等
- 生成分析报告以及mitmproxy脚本
- web界面操作，多个自定义参数配置，简单高效

## 环境要求

- Python 3.11+
- 支持的浏览器（至少安装一种）：
  - Google Chrome浏览器
  - Microsoft Edge浏览器
- 大模型API密钥（兼容OpenAI的API请求格式，如Qwen、deepseek、Chatgpt、Claude等，可自定义添加）

## 快速开始

1. 克隆本仓库：

```bash
git clone https://github.com/Valerian7/AI_JS_DEBUGGER.git
cd AI_JS_DEBUGGER
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 启动flask服务：

启动服务，浏览器访问http://localhost:5001

```Python
python3 run_flask.py
```

## 部分功能截图
### 调试配置
<img width="2559" height="1418" alt="image" src="https://github.com/user-attachments/assets/64c7b3c1-6b2b-4ff8-87c2-21e99df0964c" />

### 提示词配置
<img width="2559" height="1418" alt="image" src="https://github.com/user-attachments/assets/35fb2cdf-f12b-4fa8-b851-dd64b6777380" />

### 实时查看调试信息
<img width="2559" height="1418" alt="image" src="https://github.com/user-attachments/assets/94df28e0-e242-4bb1-b971-45a33fdb4285" />

### 分析报告管理
<img width="2559" height="1418" alt="image" src="https://github.com/user-attachments/assets/f2a3b0ff-afa2-4fd3-a823-a697c1b6de68" />

### 设置中心
<img width="2559" height="1418" alt="image" src="https://github.com/user-attachments/assets/762d4be6-29ab-40db-b421-9f8d1c3319e9" />


## 项目结构概览

```
AI_JS_DEBUGGER_0.4.0
├── backend
│   ├── app.py              # Flask + Socket.IO 入口
│   ├── routes/             # 调试、配置、系统监控 API
│   ├── services/           # AI/代理管理与系统任务
│   ├── static/             # Web UI JS/CSS/图标
│   └── templates/          # 仪表盘页面
├── ai_debugger
│   ├── ai_debugger.py      # 调试循环调度器
│   └── modules/            # 工具模块（分析、日志等）
├── modules
│   ├── cdp/                # 浏览器会话、Hook 注入
│   ├── debug/              # 断点、报告、日志处理
│   └── hooks/              # Hook 管理器封装
├── hooks
│   └── Hook_Combined.js    # HOOK 脚本
├── run_flask.py            # Web UI 启动脚本
└── config.yaml             # 模型/代理/Hook 配置
```

### FAQ

- 问：若JS被压缩成一行怎么设置断点行数和列数
  - 答：取消浏览器js美化，查看断点行数和列数，行数一般为0
- 问：不知道在哪断点怎么办
  - 答：可通过xhr方式断点，可自动回溯到最顶层堆栈；可查看浏览器开发者工具-网络-启动器查看请求调用堆栈
- 问：触发xhr断点之后怎么还要再重新触发一次
  - 答：xhr模式需要二次触发断点，第一次为xhr断点，第二次为回溯到顶层堆栈重新下的断点


## 贡献

欢迎通过Pull Request或Issue贡献代码和想法。

## 许可证

本项目采用MIT许可证 - 详情请查看[LICENSE](LICENSE)文件。
