import json
import os
from pathlib import Path
from openai import OpenAI
from .base_api import BaseAPI
from .prompt_templates import DEBUG_INSTRUCTION_PROMPT, DEBUGGER_ANALYZE_PROMPT, SYSTEM_ROLE_PROMPT

# 初始化OpenAI客户端（Deepseek使用OpenAI兼容接口）
client = OpenAI(
    api_key="sk-xxxx", # 替换为你的Deepseek API Key
    base_url="https://api.deepseek.com/v1", # Deepseek API地址
)


def get_debug_instruction(step_output: str) -> str:
    # 压缩调试信息，去除多余空格和换行
    compressed_info = " ".join(step_output.split())
    
    completion = client.chat.completions.create(
    model="deepseek-chat", # Deepseek的基础对话模型
    messages=[{
        'role': 'system', 
        'content': DEBUG_INSTRUCTION_PROMPT},
        {'role': 'system','content': f'当前调试信息：{compressed_info}'
    }],
    response_format={"type": "json_object"},
)
    try:
        result = completion.choices[0].message.content
        resp = json.loads(result)
        
        if resp.get("step_into", False):
            instruction = "step_into"
        elif resp.get("step_out", False):
            instruction = "step_out"
        else:
            instruction = "step_over"  
            
    except Exception as e:
        print("调用远程 API 失败，默认使用 step_over。错误信息：", e)
        instruction = "step_over"
    return instruction


def debugger_analyze(path):
    path = Path(path)
    
    # 读取文件内容
    with open(path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    completion = client.chat.completions.create(
        model="deepseek-coder", # 使用Deepseek的代码模型进行分析
        messages=[
            {'role': 'system', 'content': SYSTEM_ROLE_PROMPT},
            {'role': 'user', 'content': f'{DEBUGGER_ANALYZE_PROMPT}\n\n{file_content}'}
        ],
        stream=False  
    )

    if completion.choices and completion.choices[0].message:
        ai_response = completion.choices[0].message.content.strip()
    else:
        raise ValueError("未获取到有效响应内容")

    # 生成Markdown报告
    md_content = f"""# JavaScript 加密分析报告

## 原始日志
{path}

{ai_response}

"""
    output_path = f"result/report/{path.stem}.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return output_path