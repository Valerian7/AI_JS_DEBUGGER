import time
import functools
import asyncio
import os
import platform
import gc
from datetime import datetime
from collections import OrderedDict
from typing import Dict, Optional, Any, List
from pathlib import Path

class LRUCache(OrderedDict):
    """LRU缓存实现
    
    使用OrderedDict实现的LRU（最近最少使用）缓存，当缓存大小超过限制时，
    自动删除最久未使用的项目。
    
    Attributes:
        capacity: 缓存容量（项目数量）
    """
    
    def __init__(self, capacity: int = 100):
        """初始化LRU缓存
        
        Args:
            capacity: 缓存容量，默认为100项
        """
        super().__init__()
        self.capacity = capacity
        self._size_estimate = 0  # 估计的内存占用（字节）
    
    def __getitem__(self, key):
        """获取缓存项并更新其位置（标记为最近使用）"""
        if key not in self:
            return None
        self.move_to_end(key)  # 将访问的项移到末尾（最近使用）
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        """设置缓存项，如果缓存已满则删除最久未使用的项"""
        if key in self:
            old_value = self[key]
            old_size = len(old_value) if isinstance(old_value, str) else 0
            self._size_estimate -= old_size
            self.move_to_end(key)  # 将更新的项移到末尾（最近使用）
        elif len(self) >= self.capacity:
            oldest = next(iter(self))
            oldest_value = self[oldest]
            oldest_size = len(oldest_value) if isinstance(oldest_value, str) else 0
            self._size_estimate -= oldest_size
            self.popitem(last=False)  # 删除第一项（最久未使用）
        
        super().__setitem__(key, value)
        new_size = len(value) if isinstance(value, str) else 0
        self._size_estimate += new_size
    
    def get(self, key, default=None):
        """获取缓存项，如果不存在则返回默认值"""
        if key not in self:
            return default
        return self[key]  # 使用__getitem__以更新访问顺序
    
    def clear(self):
        """清空缓存"""
        super().clear()
        self._size_estimate = 0
    
    def get_size_estimate(self) -> int:
        """获取缓存大小估计（字节）"""
        return self._size_estimate

script_source_cache = LRUCache(capacity=500)

# 性能监控
class PerformanceMonitor:
    """性能监控类,用于跟踪关键操作的耗时"""

    def __init__(self):
        self.metrics = {}
        self.start_times = {}

    def start(self, operation: str):
        """开始计时"""
        import time
        self.start_times[operation] = time.perf_counter()

    def end(self, operation: str) -> float:
        """结束计时并返回耗时(秒)"""
        import time
        if operation not in self.start_times:
            return 0.0
        elapsed = time.perf_counter() - self.start_times[operation]
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(elapsed)
        del self.start_times[operation]
        return elapsed

    def get_stats(self, operation: str) -> dict:
        """获取操作的统计信息"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        times = self.metrics[operation]
        return {
            'count': len(times),
            'total': sum(times),
            'avg': sum(times) / len(times),
            'min': min(times),
            'max': max(times)
        }

    def get_all_stats(self) -> dict:
        """获取所有操作的统计信息"""
        return {op: self.get_stats(op) for op in self.metrics.keys()}

    def clear(self):
        """清空所有统计数据"""
        self.metrics.clear()
        self.start_times.clear()

performance_monitor = PerformanceMonitor()

_debug_session_filename = None

def get_script_source_cache_key(script_id: str) -> str:
    """生成脚本缓存键"""
    return f"script_source:{script_id}"

def get_cached_script_source(script_id: str) -> Optional[str]:
    """获取已缓存的脚本源代码
    
    使用LRU缓存机制，访问时会自动将脚本标记为最近使用。
    
    Args:
        script_id: 脚本ID
        
    Returns:
        str: 缓存的脚本源代码，如果不存在则返回None
    """
    key = get_script_source_cache_key(script_id)
    return script_source_cache.get(key)

def set_cached_script_source(script_id: str, source: str):
    """缓存脚本源代码
    
    使用LRU缓存机制，当缓存达到容量上限时，会自动删除最久未使用的脚本。
    
    Args:
        script_id: 脚本ID
        source: 脚本源代码
    """
    key = get_script_source_cache_key(script_id)
    script_source_cache[key] = source
    

def measure_time(func):
    """
    装饰器：记录同步或异步函数的执行时间并打印日志
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            print(f"[DEBUG] 异步函数 {func.__name__} 执行耗时: {elapsed:.6f} 秒")
            return result
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            print(f"[DEBUG] 同步函数 {func.__name__} 执行耗时: {elapsed:.6f} 秒")
            return result
        return sync_wrapper

def compress_debug_info(info: str) -> str:
    """将调试信息压缩为单行字符串"""
    return " ".join(info.split())

def get_debug_session_filename():
    """获取调试会话的文件名，如果不存在则创建新的"""
    global _debug_session_filename
    if _debug_session_filename is None:
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        _debug_session_filename = f"result/logs/debug_data-{timestamp_str}.txt"
        print(f"为调试会话创建新文件: {_debug_session_filename}")
    path = Path(_debug_session_filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return _debug_session_filename

async def async_write_to_file(info: str):
    """异步写入调试信息到文件，避免阻塞主线程"""
    filename = get_debug_session_filename()
    def _write():
        with open(filename, "a+", encoding="utf-8") as file:
            file.write(info + "\n")
    await asyncio.to_thread(_write)
    
def get_browser_path(browser_type="chrome"):
    """根据操作系统类型和浏览器类型获取浏览器可执行文件路径

    Args:
        browser_type: 浏览器类型，支持"chrome"和"edge"，默认为"chrome"

    Returns:
        str: 浏览器可执行文件路径，如果找不到则返回None
    """
    system = platform.system()

    browser_paths = {
        "Windows": {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ],
            "edge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            ]
        },
        "Darwin": {  # macOS
            "chrome": [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ],
            "edge": [
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
            ]
        },
        "Linux": {
            "chrome": [
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium"
            ],
            "edge": [
                "/usr/bin/microsoft-edge"
            ]
        }
    }
    
    if system in browser_paths and browser_type in browser_paths[system]:
        paths = browser_paths[system][browser_type]
        
        for path in paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                return expanded_path
    
    return None
