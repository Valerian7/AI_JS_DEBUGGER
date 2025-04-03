import gc
import psutil
import os
import time
import threading
import logging
from typing import Dict, List, Optional, Callable

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('memory_manager')

class MemoryManager:
    """内存管理器
    
    该类负责监控和管理程序的内存使用情况，提供内存使用统计、垃圾回收触发和资源释放等功能。
    通过定期检查内存使用情况，在内存占用过高时自动执行清理操作，防止内存溢出。
    
    Attributes:
        threshold_percent: 内存使用阈值百分比，超过此值触发清理
        check_interval: 内存检查间隔时间（秒）
        monitoring: 是否正在监控内存
        _monitor_thread: 内存监控线程
        _callbacks: 注册的内存清理回调函数
        _cache_stats: 缓存统计信息
    """
    
    def __init__(self, threshold_percent: float = 75.0, check_interval: float = 5.0):
        """初始化内存管理器
        
        Args:
            threshold_percent: 内存使用阈值百分比，默认为75%
            check_interval: 内存检查间隔时间（秒），默认为5秒
        """
        self.threshold_percent = threshold_percent
        self.check_interval = check_interval
        self.monitoring = False
        self._monitor_thread = None
        self._callbacks: Dict[str, Callable] = {}
        self._cache_stats: Dict[str, Dict] = {}
        self.process = psutil.Process(os.getpid())
    
    def start_monitoring(self):
        """启动内存监控线程"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_memory, daemon=True)
        self._monitor_thread.start()
        logger.info(f"内存监控已启动，阈值: {self.threshold_percent}%，检查间隔: {self.check_interval}秒")
    
    def stop_monitoring(self):
        """停止内存监控线程"""
        self.monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
            logger.info("内存监控已停止")
    
    def _monitor_memory(self):
        """内存监控线程主函数"""
        while self.monitoring:
            try:
                memory_info = self.get_memory_info()
                memory_percent = memory_info['percent']
                
                # 记录内存使用情况
                if memory_percent > 50:
                    logger.info(f"当前内存使用: {memory_percent:.1f}%, {memory_info['used_mb']:.1f}MB / {memory_info['total_mb']:.1f}MB")
                
                # 如果内存使用超过阈值，触发清理
                if memory_percent > self.threshold_percent:
                    logger.warning(f"内存使用超过阈值 {self.threshold_percent}%，触发清理操作")
                    self.force_cleanup()
            except Exception as e:
                logger.error(f"内存监控出错: {e}")
            
            time.sleep(self.check_interval)
    
    def get_memory_info(self) -> Dict:
        """获取当前内存使用情况
        
        Returns:
            Dict: 包含内存使用信息的字典
        """
        # 获取进程内存信息
        process_memory = self.process.memory_info()
        # 获取系统内存信息
        system_memory = psutil.virtual_memory()
        
        return {
            'process_rss_mb': process_memory.rss / (1024 * 1024),  # 进程实际内存使用（MB）
            'process_vms_mb': process_memory.vms / (1024 * 1024),  # 进程虚拟内存（MB）
            'used_mb': system_memory.used / (1024 * 1024),  # 系统已用内存（MB）
            'total_mb': system_memory.total / (1024 * 1024),  # 系统总内存（MB）
            'percent': system_memory.percent,  # 系统内存使用百分比
            'process_percent': self.process.memory_percent()  # 进程内存占比
        }
    
    def register_cleanup_callback(self, name: str, callback: Callable):
        """注册内存清理回调函数
        
        Args:
            name: 回调函数名称
            callback: 回调函数，无参数，用于清理资源
        """
        self._callbacks[name] = callback
        logger.debug(f"已注册内存清理回调函数: {name}")
    
    def unregister_cleanup_callback(self, name: str):
        """注销内存清理回调函数
        
        Args:
            name: 回调函数名称
        """
        if name in self._callbacks:
            del self._callbacks[name]
            logger.debug(f"已注销内存清理回调函数: {name}")
    
    def force_cleanup(self):
        """强制执行内存清理操作"""
        start_time = time.time()
        logger.info("开始执行内存清理...")
        
        # 执行注册的清理回调函数
        for name, callback in self._callbacks.items():
            try:
                callback()
                logger.debug(f"执行清理回调: {name}")
            except Exception as e:
                logger.error(f"执行清理回调 {name} 出错: {e}")
        
        # 执行Python垃圾回收
        collected = gc.collect()
        
        # 记录清理结果
        elapsed = time.time() - start_time
        after_memory = self.get_memory_info()
        logger.info(f"内存清理完成，耗时: {elapsed:.2f}秒，回收对象: {collected}，")
        logger.info(f"清理后内存使用: {after_memory['percent']:.1f}%, {after_memory['used_mb']:.1f}MB")
    
    def register_cache(self, cache_name: str, cache_dict: Dict):
        """注册缓存字典以进行统计和管理
        
        Args:
            cache_name: 缓存名称
            cache_dict: 缓存字典对象
        """
        self._cache_stats[cache_name] = {
            'dict': cache_dict,
            'last_size': len(cache_dict)
        }
    
    def get_cache_stats(self) -> Dict[str, Dict]:
        """获取所有注册缓存的统计信息
        
        Returns:
            Dict: 包含各缓存统计信息的字典
        """
        stats = {}
        for name, info in self._cache_stats.items():
            cache_dict = info['dict']
            current_size = len(cache_dict)
            stats[name] = {
                'size': current_size,
                'growth': current_size - info['last_size']
            }
            # 更新上次大小记录
            info['last_size'] = current_size
        return stats
    
    def clear_cache(self, cache_name: Optional[str] = None):
        """清理指定或所有缓存
        
        Args:
            cache_name: 要清理的缓存名称，如果为None则清理所有缓存
        """
        if cache_name:
            if cache_name in self._cache_stats:
                cache_dict = self._cache_stats[cache_name]['dict']
                size_before = len(cache_dict)
                cache_dict.clear()
                logger.info(f"已清理缓存 {cache_name}，释放 {size_before} 个项目")
        else:
            # 清理所有缓存
            for name, info in self._cache_stats.items():
                size_before = len(info['dict'])
                info['dict'].clear()
                info['last_size'] = 0
                logger.info(f"已清理缓存 {name}，释放 {size_before} 个项目")

# 创建全局内存管理器实例
memory_manager = MemoryManager()

# 辅助函数：分片处理大型数据
def process_in_chunks(data_list: List, chunk_size: int, process_func: Callable, *args, **kwargs):
    """分片处理大型数据列表
    
    将大型数据列表分成多个小块进行处理，避免一次性加载过多数据导致内存溢出。
    
    Args:
        data_list: 要处理的数据列表
        chunk_size: 每个分片的大小
        process_func: 处理函数，接收数据分片作为第一个参数
        *args, **kwargs: 传递给处理函数的其他参数
    
    Returns:
        List: 合并后的处理结果
    """
    results = []
    total = len(data_list)
    
    for i in range(0, total, chunk_size):
        chunk = data_list[i:i + chunk_size]
        chunk_result = process_func(chunk, *args, **kwargs)
        
        if chunk_result:
            if isinstance(chunk_result, list):
                results.extend(chunk_result)
            else:
                results.append(chunk_result)
        
        # 主动触发垃圾回收
        if i % (chunk_size * 5) == 0:
            gc.collect()
    
    return results