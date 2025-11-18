"""
Hook 模块初始化
暴露 HookManager 及辅助方法，供其他模块导入
"""

from .hook_manager import HookManager, get_hook_manager

__all__ = [
    'HookManager',
    'get_hook_manager'
]
