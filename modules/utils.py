import time
import functools
import asyncio
from datetime import datetime

# 用于缓存脚本源代码的全局字典
script_source_cache = {}
# 用于保存当前调试会话的文件名
_debug_session_filename = None

def get_script_source_cache_key(script_id: str) -> str:
    """生成脚本缓存键"""
    return f"script_source:{script_id}"

def get_cached_script_source(script_id: str):
    """获取已缓存的脚本源代码"""
    key = get_script_source_cache_key(script_id)
    return script_source_cache.get(key)

def set_cached_script_source(script_id: str, source: str):
    """缓存脚本源代码"""
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
    return _debug_session_filename

async def async_write_to_file(info: str):
    """异步写入调试信息到文件，避免阻塞主线程"""
    filename = get_debug_session_filename()
    def _write():
        with open(filename, "a+", encoding="utf-8") as file:
            file.write(info + "\n")
    await asyncio.to_thread(_write)
