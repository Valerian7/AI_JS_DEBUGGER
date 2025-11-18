"""
WebSocket 路由
处理实时调试信息推送
"""

from flask_socketio import emit, join_room, leave_room
from backend.routes.debug import last_debug_events
import logging

logger = logging.getLogger(__name__)


def init_websocket(socketio):
    """初始化 WebSocket 事件处理器"""

    @socketio.on('connect')
    def handle_connect():
        """客户端连接"""
        logger.info('Client connected')
        emit('connection_response', {
            'status': 'connected',
            'message': 'Successfully connected to server'
        })

    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接"""
        logger.info('Client disconnected')

    @socketio.on('join_debug_session')
    def handle_join_session(data):
        """加入调试会话房间"""
        session_id = data.get('session_id')
        if session_id:
            join_room(session_id)
            logger.info(f'Client joined debug session: {session_id}')
            emit('session_joined', {
                'session_id': session_id,
                'message': 'Joined debug session'
            })
            last_evt = last_debug_events.get(session_id)
            if last_evt:
                emit('debug_paused', last_evt)

    @socketio.on('leave_debug_session')
    def handle_leave_session(data):
        """离开调试会话房间"""
        session_id = data.get('session_id')
        if session_id:
            leave_room(session_id)
            logger.info(f'Client left debug session: {session_id}')
            emit('session_left', {
                'session_id': session_id,
                'message': 'Left debug session'
            })

    @socketio.on('ping')
    def handle_ping():
        """心跳检测"""
        emit('pong', {'timestamp': __import__('time').time()})
