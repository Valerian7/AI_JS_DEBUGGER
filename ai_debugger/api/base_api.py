import json
import os
from pathlib import Path
from .prompt_templates import DEBUG_INSTRUCTION_PROMPT, DEBUGGER_ANALYZE_PROMPT, SYSTEM_ROLE_PROMPT

class BaseAPI:
    """基础API类，封装所有API共享的功能
    
    该类提供了通用的方法和属性，各个具体API实现可以继承这个基类。
    """
    
    def __init__(self):
        """初始化基础API类"""
        pass
        
    def get_debug_instruction(self, step_output: str) -> str:
        """根据调试信息决定下一步调试操作
        
        Args:
            step_output: 当前调试步骤的输出信息
            
        Returns:
            str: 下一步调试指令，可能的值为"step_into"、"step_out"或"step_over"
        """
        # 压缩调试信息，去除多余空格和换行
        compressed_info = " ".join(step_output.split())
        
        # 子类需要实现具体的API调用逻辑
        raise NotImplementedError("子类必须实现此方法")
    
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
        
        # 子类需要实现具体的API调用逻辑
        raise NotImplementedError("子类必须实现此方法")
    
    def _generate_markdown_report(self, path, ai_response):
        """生成Markdown格式的分析报告
        
        Args:
            path: 原始日志文件路径
            ai_response: AI分析结果
            
        Returns:
            str: 报告文件路径
        """
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
            
        return report_path