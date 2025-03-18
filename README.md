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
- Google Chrome浏览器
- 大模型API密钥

## 视频演示

[![](https://i.postimg.cc/0ycFpTyJ/i-Shot-2025-03-18-11-41-01.png)](https://www.bilibili.com/video/BV1kPXGYVEkj)

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

3. 配置Chrome路径：

在`main.py`中，替换chrome浏览器路径：
```Python
executable_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

#executable_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
```

4. 配置API密钥：

在`ai/api/qwen_api.py`中，替换示例API密钥为自己的大模型API密钥（目前只支持[通义千问](https://bailian.console.aliyun.com/#/home)）：

```python
client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
```

## 使用方法

1. 运行主程序：

```bash
python mian.py
```

2. 选择断点模式：
   - `js`: 使用JavaScript文件路径和行号设置断点
   - `xhr`: 设置XHR请求断点

2. 按照提示输入断点信息

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
