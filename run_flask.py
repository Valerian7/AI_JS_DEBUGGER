#!/usr/bin/env python3
"""
Flask 应用启动脚本
用于启动 AI_JS_DEBUGGER Web GUI 应用
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app, socketio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info('='*60)
    logger.info('AI_JS_DEBUGGER Flask Web Application')
    logger.info('='*60)
    logger.info('启动服务中...')
    logger.info('访问地址: http://localhost:5001')
    logger.info('Press Ctrl+C to stop the server')
    logger.info('='*60)

    socketio.run(
        app,
        host='127.0.0.1',
        port=5001,
        debug=False,
        use_reloader=False,
        log_output=True,
        allow_unsafe_werkzeug=True 
    )
