import json
import os
from pathlib import Path
from openai import OpenAI
from .base_api import BaseAPI
from .prompt_templates import DEBUG_INSTRUCTION_PROMPT, DEBUGGER_ANALYZE_PROMPT, SYSTEM_ROLE_PROMPT

client = OpenAI(
    api_key="sk-xxxx", # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def get_debug_instruction(step_output: str) -> str:
    # 压缩调试信息，去除多余空格和换行
    compressed_info = " ".join(step_output.split())
    
    completion = client.chat.completions.create(
    model="qwen-turbo", 
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
    file_object = client.files.create(file=path, purpose="file-extract")
    
    completion = client.chat.completions.create(
        model="qwen-long",
        messages=[
            {'role': 'system', 'content': f'fileid://{file_object.id}'},
            {'role': 'user', 'content': DEBUGGER_ANALYZE_PROMPT}
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
