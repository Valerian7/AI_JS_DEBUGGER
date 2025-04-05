import json
import os
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from .base_api import BaseAPI
from .prompt_templates import DEBUG_INSTRUCTION_PROMPT, DEBUGGER_ANALYZE_PROMPT, SYSTEM_ROLE_PROMPT

class ErnieAPI(BaseAPI):
    """百度文心API实现"""
    
    def __init__(self, api_key="your-api-key-here", secret_key="your-secret-key-here"):
        """初始化百度文心API
        
        Args:
            api_key: 百度文心API Key
            secret_key: 百度文心Secret Key
        """
        super().__init__()
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expire_time = 0
        
        # 初始化OpenAI客户端（用于兼容性，但实际使用自定义请求）
        self.client = OpenAI(
            api_key="your-api-key-here",  # 这里的API key不会被实际使用
            base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",  # 这个URL仅作为占位符
        )
    
    def get_access_token(self):
        """获取百度文心API的access_token
        
        Returns:
            str: access_token
        """
        # 如果token未过期，直接返回
        current_time = time.time()
        if self.access_token and current_time < self.token_expire_time:
            return self.access_token
        
        # 获取新token
        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.secret_key}"
        
        payload = ""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = requests.request("POST", url, headers=headers, data=payload)
        result = response.json()
        
        if 'access_token' in result:
            self.access_token = result['access_token']
            # token有效期通常为30天，这里设置为29天以确保安全
            self.token_expire_time = current_time + 29 * 24 * 60 * 60
            return self.access_token
        else:
            raise Exception(f"获取access_token失败: {result}")
    
    def get_debug_instruction(self, step_output: str) -> str:
        """根据调试信息决定下一步调试操作
        
        Args:
            step_output: 当前调试步骤的输出信息
            
        Returns:
            str: 下一步调试指令，可能的值为"step_into"、"step_out"或"step_over"
        """
        # 压缩调试信息，去除多余空格和换行
        compressed_info = " ".join(step_output.split())
        
        try:
            # 获取access_token
            access_token = self.get_access_token()
            
            # 构造请求URL
            url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={access_token}"
            
            # 构造请求数据
            payload = json.dumps({
                "messages": [
                    {
                        "role": "system",
                        "content": DEBUG_INSTRUCTION_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"当前调试信息：{compressed_info}"
                    }
                ],
                "temperature": 0.7,
                "top_p": 0.8,
                "stream": False,
                "response_format": {"type": "json_object"},
                "system": "ERNIE-Bot-4"
            })
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            
            if 'result' in result:
                content = result['result']
                resp = json.loads(content)
                
                if resp.get("step_into", False):
                    instruction = "step_into"
                elif resp.get("step_out", False):
                    instruction = "step_out"
                else:
                    instruction = "step_over"
            else:
                print(f"文心API调用失败: {result}")
                instruction = "step_over"
                
        except Exception as e:
            print(f"调用文心API失败，默认使用step_over。错误信息：{e}")
            instruction = "step_over"
            
        return instruction
    
    def debugger_analyze(self, path):
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
        
        try:
            # 获取access_token
            access_token = self.get_access_token()
            
            # 构造请求URL
            url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={access_token}"
            
            # 构造请求数据
            payload = json.dumps({
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_ROLE_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"{DEBUGGER_ANALYZE_PROMPT}\n\n{file_content}"
                    }
                ],
                "temperature": 0.5,  # 降低温度以获得更确定性的回答
                "top_p": 0.8,
                "stream": False,
                "system": "ERNIE-Bot-4"
            })
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            
            if 'result' in result:
                ai_response = result['result']
            else:
                raise ValueError(f"文心API调用失败: {result}")
                
        except Exception as e:
            raise ValueError(f"调用文心API失败: {str(e)}")

        # 生成Markdown报告并返回分析结果
        report_path = self._generate_markdown_report(path, ai_response)
        return ai_response
    
    def generate_response(self, prompt, model_params):
        """生成文本响应
        
        Args:
            prompt: 用户输入的提示文本
            model_params: 模型参数
            
        Returns:
            dict: 包含响应结果的字典
        """
        try:
            # 获取access_token
            access_token = self.get_access_token()
            
            # 构造请求URL
            url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={access_token}"
            
            # 构造请求数据
            payload = json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": model_params.get('temperature', 0.7),
                "top_p": model_params.get('top_p', 0.8),
                "stream": False,
                "system": model_params.get('model', "ERNIE-Bot")  # 默认使用ERNIE-Bot
            })
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            
            if 'result' in result:
                return {
                    'status': 'success',
                    'response': result['result']
                }
            else:
                return {
                    'status': 'error',
                    'message': f"API请求失败: {result}"
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f"API请求失败: {str(e)}"
            }

# 创建API实例
ernie_api = ErnieAPI()

# 导出函数，保持与原始API兼容
def get_debug_instruction(step_output: str) -> str:
    return ernie_api.get_debug_instruction(step_output)

def debugger_analyze(path):
    return ernie_api.debugger_analyze(path)

def generate_response(prompt, model_params):
    return ernie_api.generate_response(prompt, model_params)