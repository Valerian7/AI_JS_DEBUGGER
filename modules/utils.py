import time
import functools
import asyncio
import gc
from datetime import datetime
from collections import OrderedDict
from typing import Dict, Optional, Any, List

# 用于缓存脚本源代码的LRU缓存字典
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
            # 更新现有项，先减去旧值的大小估计
            old_value = self[key]
            old_size = len(old_value) if isinstance(old_value, str) else 0
            self._size_estimate -= old_size
            self.move_to_end(key)  # 将更新的项移到末尾（最近使用）
        elif len(self) >= self.capacity:
            # 缓存已满，删除最久未使用的项（字典头部）
            oldest = next(iter(self))
            oldest_value = self[oldest]
            oldest_size = len(oldest_value) if isinstance(oldest_value, str) else 0
            self._size_estimate -= oldest_size
            self.popitem(last=False)  # 删除第一项（最久未使用）
        
        # 添加新项并更新大小估计
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

# 创建脚本源代码缓存（默认容量100个脚本）
script_source_cache = LRUCache(capacity=100)

# 用于保存当前调试会话的文件名
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
    
    # 如果缓存大小估计超过50MB，主动触发垃圾回收
    if script_source_cache.get_size_estimate() > 50 * 1024 * 1024:
        gc.collect()

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
    return _debug_session_filename

async def async_write_to_file(info: str):
    """异步写入调试信息到文件，避免阻塞主线程"""
    filename = get_debug_session_filename()
    def _write():
        with open(filename, "a+", encoding="utf-8") as file:
            file.write(info + "\n")
    await asyncio.to_thread(_write)
