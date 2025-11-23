"""
系统监控路由
处理内存监控、系统状态等操作
"""

from flask import Blueprint, jsonify, current_app
import psutil
import gc
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('system', __name__)

@bp.route('/memory', methods=['GET'])
def get_memory_status():
    """获取内存使用状态"""
    try:
        memory = psutil.virtual_memory()

        process = psutil.Process()
        process_memory = process.memory_info()

        response = jsonify({
            'success': True,
            'data': {
                'system': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'process': {
                    'rss': process_memory.rss,  # Resident Set Size
                    'vms': process_memory.vms,  # Virtual Memory Size
                    'percent': process.memory_percent()
                },
                'warning_level': 'danger' if memory.percent > 85 else 'warning' if memory.percent > 70 else 'normal'
            }
        })
        response.headers['X-SILENT'] = '1'
        return response
    except Exception as e:
        logger.error(f'Failed to get memory status: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/memory/clear', methods=['POST'])
def clear_memory():
    """手动清理内存"""
    try:
        collected = gc.collect()

        memory_after = psutil.virtual_memory()
        process = psutil.Process()

        logger.info(f'Manual memory cleanup executed, collected {collected} objects')

        return jsonify({
            'success': True,
            'data': {
                'objects_collected': collected,
                'memory_after': {
                    'system_percent': memory_after.percent,
                    'process_percent': process.memory_percent()
                }
            }
        })
    except Exception as e:
        logger.error(f'Failed to clear memory: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/stats', methods=['GET'])
def get_system_stats():
    """获取系统统计信息"""
    try:
        # interval=None 非阻塞模式，返回自上次调用以来的系统 CPU 利用率
        # 首次调用可能返回 0.0，前端轮询时后续调用将返回准确值
        cpu_percent = psutil.cpu_percent(interval=None)
        disk_usage = psutil.disk_usage('/')

        return jsonify({
            'success': True,
            'data': {
                'cpu_percent': cpu_percent,
                'disk': {
                    'total': disk_usage.total,
                    'used': disk_usage.used,
                    'free': disk_usage.free,
                    'percent': disk_usage.percent
                }
            }
        })
    except Exception as e:
        logger.error(f'Failed to get system stats: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
