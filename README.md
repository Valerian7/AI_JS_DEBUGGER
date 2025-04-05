# <h1 align="center">AI_JS_DEBUGGER</h1>

本项目是基于Chrome开发者协议(CDP)的AI自动化JavaScript逆向分析工具，通过AI自动调试前端JS，自动分析加解密算法、密钥等，自动生成分析报告以及mitmproxy脚本。

**声明：文中所涉及的技术、思路和工具仅供以安全为目的的学习交流使用，<u>任何人不得将其用于非法用途以及盈利等目的，否则后果自负</u>** 

## 功能特点

- 支持固定js文件断点、XHR请求断点
- XHR回溯，XHR模式下自动回溯顶层调用堆栈并自动断点
- 根据调用堆栈、js片段、作用域等断点调试信息自动调试
- 自动分析加解密算法、密钥、生成密钥方式等
- 生成分析报告以及mitmproxy脚本

## 环境要求

- Python 3.8+
- 支持的浏览器（至少安装一种）：
  - Google Chrome浏览器
  - Mozilla Firefox浏览器
  - Microsoft Edge浏览器
- 大模型API密钥（支持通义千问、GPT、Deepseek、文心ERNIE、讯飞星火）

## 视频演示

[![](https://i.postimg.cc/0ycFpTyJ/i-Shot-2025-03-18-11-41-01.png)](https://player.bilibili.com/player.html?isOutside=true&aid=114181269363837&bvid=BV1kPXGYVEkj&cid=28924709737&p=1)

## 安装

1. 克隆本仓库：

```bash
git clone https://github.com/yourusername/js-debugger-ai.git
cd js-debugger-ai
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 浏览器配置：

程序支持Chrome、Firefox和Edge浏览器。运行时会提示选择浏览器类型，并自动查找浏览器的默认安装路径。

如需手动指定浏览器路径，可在`main.py`中取消注释相应的路径配置：

```Python
# Chrome路径
#executable_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'  # macOS路径
#executable_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'  # Windows路径

# Firefox路径
#executable_path = '/Applications/Firefox.app/Contents/MacOS/firefox'  # macOS路径
#executable_path = r'C:\Program Files\Mozilla Firefox\firefox.exe'  # Windows路径

# Edge路径
#executable_path = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'  # macOS路径
#executable_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'  # Windows路径
```

4. 配置API密钥：

根据您选择的大模型，在相应的API文件中配置密钥：

- 通义千问（默认）：在`ai_debugger/api/qwen_api.py`中配置
```python
client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
```

- GPT：在`ai_debugger/api/gpt_api.py`中配置
```python
# 默认使用官方API
use_third_party_api = False  # 设置为True启用第三方API
third_party_base_url = "https://your-third-party-api.com/v1"  # 第三方API地址

# 配置客户端
if use_third_party_api and third_party_base_url:
    client = OpenAI(
        api_key="your-api-key-here",
        base_url=third_party_base_url,
    )
else:
    client = OpenAI(
        api_key="your-api-key-here",
        # 使用官方API地址，无需设置base_url
    )
```

- Deepseek：在`ai_debugger/api/deepseek_api.py`中配置
```python
client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://api.deepseek.com/v1",
)
```

- 文心ERNIE：在`ai_debugger/api/ernie_api.py`中配置
```python
client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
)
```

- 讯飞星火：在`ai_debugger/api/spark_api.py`中配置
```python
client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://api.xfyun.cn/v2.1/chat",
)
```

## 使用方法

1. 运行主程序：

```bash
python main.py
```

2. 选择断点模式和大模型API：
   - 断点模式：
     - `js`: 使用JavaScript文件路径和行号设置断点
     - `xhr`: 设置XHR请求断点
   - 大模型API：
     - `qwen`: 使用通义千问API（默认）
     - `gpt`: 使用OpenAI GPT API
     - `deepseek`: 使用Deepseek API
     - `ernie`: 使用百度文心ERNIE API
     - `spark`: 使用讯飞星火API

3. 按照提示输入断点信息

### JS断点示例

FAQ：若JS被压缩成一行，则断点行数为0行
```
请输入待分析站点链接:https://example.com/login
请选择断点模式(js/xhr): js
请输入JS文件路径: https://example.com/js/main.js
请输入断点行数: 120
请输入断点列数: 0
```

### XHR断点示例

```
请输入待分析站点链接:https://example.com/login
请选择断点模式(js/xhr): xhr
请输入XHR请求URL(不填写则监听所有请求): /api/login
```

## 贡献

欢迎通过Pull Request或Issue贡献代码和想法。

## 许可证

本项目采用MIT许可证 - 详情请查看[LICENSE](LICENSE)文件。
