"""
Flask 应用主入口
AI_JS_DEBUGGER Web GUI Application
"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import logging


class _SilentEndpointFilter(logging.Filter):
    """过滤无需输出到终端的请求日志"""

    def __init__(self, silent_patterns=None):
        super().__init__()
        self.silent_patterns = silent_patterns or []

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if not message:
            return True
        return not any(pattern in message for pattern in self.silent_patterns)

app = Flask(__name__,
           static_folder='static',
           template_folder='templates')

app.config['SECRET_KEY'] = 'ai-js-debugger-secret-key-change-in-production'
app.config['JSON_AS_ASCII'] = False  # 支持中文 JSON

CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(_SilentEndpointFilter(['/system/memory']))

from backend.routes import api, debug, reports, system
from backend.routes.websocket import init_websocket

app.register_blueprint(api.bp, url_prefix='/api')
app.register_blueprint(debug.bp, url_prefix='/debug')
app.register_blueprint(reports.bp, url_prefix='/api/reports')
app.register_blueprint(system.bp, url_prefix='/system')

init_websocket(socketio)

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0'
    })

@app.errorhandler(404)
def not_found(error):
    """404 错误处理"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500 错误处理"""
    logger.error(f'Internal Server Error: {error}')
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500

def create_app():
    """应用工厂函数"""
    return app, socketio

if __name__ == '__main__':
    logger.info('Starting AI_JS_DEBUGGER Flask Application...')
    socketio.run(app,
                host='0.0.0.0',
                port=5000,
                debug=True,
                use_reloader=True)
