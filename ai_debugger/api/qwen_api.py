import json
import os
from pathlib import Path
from openai import OpenAI

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
        'content': '任务：根据JavaScript调试信息分析加密相关代码并决定最优调试策略。\n\n' +
        '分析重点：\n' +
        '1. 加密函数识别：检测函数名包含encrypt/decrypt/AES/RSA/DES/MD5/SHA/Hash/Crypto/签名/code等关键词\n' +
        '2. 可疑函数调用：sendData*/getToken*/getSign*/request*等数据传输或签名函数\n' +
        '3. 加密库引用：CryptoJS/WebCrypto/subtle/forge/jsencrypt等库的使用痕迹\n' +
        '4. 数据转换操作：Base64/HEX/UTF-8/toString/fromCharCode/字符串拼接或异或操作\n' +
        '5. 可疑参数：IV/key/salt/mode/padding等加密参数\n\n' +
        '精确决策规则：\n' +
        '- 【step_over】发现首次出现的加密相关函数调用时，进入该函数内部\n' +
        '- 【step_over】已经处于加密函数内部时，对非核心操作进行单步跳过\n' +
        '- 【step_out】深入3层以上的内部库函数实现或重复的循环操作时，跳出当前函数\n' +
        '- 【step_out】连续3次在相同位置或相似上下文中执行或”作用域中未找到相关变量“时，避免调试陷入循环\n' +
        #'- 【step_over】默认策略，用于常规代码分析\n\n' +
        '输出格式：仅返回单一JSON对象，三个字段中只有一个为true\n' +
        '```json\n' +
        '{\n' +
        '  "step_over": false,\n' +
        '  "step_out": false\n' +
        '}'},
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
            {'role': 'user', 'content': '这是我的js调试信息，请帮我分析加解密方法、密钥、加解密/生成密钥关键代码等，编写mitmproxy脚本，不需要加固建议，尽量简洁'}
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
