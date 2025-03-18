import json
import os
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
import websocket
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from .base_api import BaseAPI
from .prompt_templates import DEBUG_INSTRUCTION_PROMPT, DEBUGGER_ANALYZE_PROMPT, SYSTEM_ROLE_PROMPT

# 讯飞星火API配置
APP_ID = "your-app-id-here"
API_KEY = "your-api-key-here"
API_SECRET = "your-api-secret-here"
SPARK_URL = "wss://spark-api.xf-yun.com/v3.5/chat"

# 初始化OpenAI客户端（用于兼容性，但实际使用自定义请求）
client = OpenAI(
    api_key="your-api-key-here",  # 这里的API key不会被实际使用
    base_url="https://api.xfyun.cn/v2.1/chat",  # 这个URL仅作为占位符
)


def generate_auth_url():
    """生成讯飞星火API的鉴权URL"""
    # 生成RFC1123格式的时间戳
    now = datetime.now()
    date = now.strftime('%a, %d %b %Y %H:%M:%S') + ' GMT'
    
    # 拼接字符串
    signature_origin = f"host: spark-api.xf-yun.com\ndate: {date}\nGET /v3.5/chat HTTP/1.1"
    
    # 使用hmac-sha256进行加密
    signature_sha = hmac.new(API_SECRET.encode('utf-8'), signature_origin.encode('utf-8'),
                           digestmod=hashlib.sha256).digest()
    
    # 进行base64编码
    signature_sha_base64 = base64.b64encode(signature_sha).decode()
    
    # 构造authorization
    authorization = f"api_key=\"{API_KEY}\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"{signature_sha_base64}\""
    
    # 构造完整的URL
    authorization_url_encoded = urllib.parse.quote(authorization, safe='')
    date_url_encoded = urllib.parse.quote(date, safe='')
    
    url = f"{SPARK_URL}?authorization={authorization_url_encoded}&date={date_url_encoded}&host=spark-api.xf-yun.com"
    return url


def get_debug_instruction(step_output: str) -> str:
    """根据调试信息决定下一步调试操作
    
    Args:
        step_output: 当前调试步骤的输出信息
        
    Returns:
        str: 下一步调试指令，可能的值为"step_into"、"step_out"或"step_over"
    """
    # 压缩调试信息，去除多余空格和换行
    compressed_info = " ".join(step_output.split())
    
    # 构造请求数据
    data = {
        "header": {
            "app_id": APP_ID,
            "uid": "user_001"
        },
        "parameter": {
            "chat": {
                "domain": "general",
                "temperature": 0.7,
                "max_tokens": 1024
            }
        },
        "payload": {
            "message": {
                "text": [
                    {
                        "role": "system",
                        "content": DEBUG_INSTRUCTION_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"当前调试信息：{compressed_info}"
                    }
                ]
            }
        }
    }
    
    try:
        # 使用HTTP方式调用星火API
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 构建API URL（这里使用HTTP接口，而非WebSocket）
        host = "https://spark-api.xf-yun.com/v3.5/chat"
        url = f"{host}?appid={APP_ID}&api_key={API_KEY}&api_secret={API_SECRET}"
        
        response = requests.post(url, json=data, headers=headers)
        result = response.json()
        
        # 解析响应
        if result.get("header", {}).get("code") == 0:
            content = result.get("payload", {}).get("choices", {}).get("text", [{}])[0].get("content", "")
            resp = json.loads(content)
            
            if resp.get("step_into", False):
                instruction = "step_into"
            elif resp.get("step_out", False):
                instruction = "step_out"
            else:
                instruction = "step_over"
        else:
            print(f"星火API调用失败: {result}")
            instruction = "step_over"
            
    except Exception as e:
        print(f"调用星火API失败，默认使用step_over。错误信息：{e}")
        instruction = "step_over"
        
    return instruction


def debugger_analyze(path):
    """分析调试日志文件
    
    Args:
        path: 调试日志文件路径
        
    Returns:
        str: 分析结果
    """
    path = Path(path)
    
    # 读取文件内容
    with open(path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    # 构造请求数据
    data = {
        "header": {
            "app_id": APP_ID,
            "uid": "user_002"
        },
        "parameter": {
            "chat": {
                "domain": "general",
                "temperature": 0.5,  # 降低温度以获得更确定性的回答
                "max_tokens": 4096  # 增加token数以获得更详细的分析
            }
        },
        "payload": {
            "message": {
                "text": [
                    {
                        "role": "system",
                        "content": SYSTEM_ROLE_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"{DEBUGGER_ANALYZE_PROMPT}\n\n{file_content}"
                    }
                ]
            }
        }
    }
    
    try:
        # 使用HTTP方式调用星火API
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 构建API URL（这里使用HTTP接口，而非WebSocket）
        host = "https://spark-api.xf-yun.com/v3.5/chat"
        url = f"{host}?appid={APP_ID}&api_key={API_KEY}&api_secret={API_SECRET}"
        
        response = requests.post(url, json=data, headers=headers)
        result = response.json()
        
        # 解析响应
        if result.get("header", {}).get("code") == 0:
            ai_response = result.get("payload", {}).get("choices", {}).get("text", [{}])[0].get("content", "")
        else:
            raise ValueError(f"星火API调用失败: {result}")
            
    except Exception as e:
        raise ValueError(f"调用星火API失败: {str(e)}")

    # 生成Markdown报告
    md_content = f"""# JavaScript 加密分析报告

## 原始日志
{path}

{ai_response}
"""

    # 生成报告文件名
    report_filename = path.stem + ".md"
    report_path = path.parent.parent / "report" / report_filename
    
    # 确保report目录存在
    report_dir = report_path.parent
    if not report_dir.exists():
        report_dir.mkdir(parents=True)
        
    # 写入报告文件
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    return ai_response