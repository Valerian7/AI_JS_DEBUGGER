"""
调试控制路由
处理调试会话的创建、控制等操作
"""

from flask import Blueprint, request, jsonify
import logging
import uuid
from datetime import datetime
import asyncio
import sys
import os
import time
import socket
import shutil

import psutil
from modules.debug.debug_processor import get_code_context
from backend.models import (
    session_manager,
    SessionStatus,
    BreakpointMode,
    BrowserType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

bp = Blueprint('debug', __name__)

last_debug_events = {}
last_debug_seq = {}


def _get_runtime_or_error(session_id: str):
    """获取运行时对象或返回错误响应

    Returns:
        tuple: (runtime, error_response) - 如果成功返回(runtime, None), 否则返回(None, error_response)
    """
    session = session_manager.get(session_id)
    if session is None:
        return None, (jsonify({'success': False, 'error': 'Session not found'}), 404)

    runtime = session_manager.get_runtime(session_id)
    if not runtime or not runtime.has_client():
        return None, (jsonify({'success': False, 'error': 'Client not ready'}), 400)

    return runtime, None

@bp.route('/session/create', methods=['POST'])
def create_session():
    """创建新的调试会话"""
    try:
        data = request.get_json()
        session_id = str(uuid.uuid4())

        session = session_manager.create(session_id, data)

        logger.info(f'Debug session created: {session_id}')

        return jsonify({
            'success': True,
            'data': {
                'session_id': session_id,
                'session': session.to_dict()
            }
        })
    except Exception as e:
        logger.error(f'Failed to create debug session: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取调试会话信息"""
    try:
        session = session_manager.get(session_id)
        if session is None:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        return jsonify({
            'success': True,
            'data': session.to_dict(include_runtime=True)
        })
    except Exception as e:
        logger.error(f'Failed to get debug session: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/session/<session_id>/start', methods=['POST'])
def start_session(session_id):
    """启动调试会话"""
    try:
        session = session_manager.require(session_id)

        import subprocess
        import threading

        executable_path = session.browser_executable_path
        target_url = session.target_url
        launch_url = target_url or 'about:blank'

        import tempfile
        user_data_dir = tempfile.mkdtemp(prefix="ai_debugger_")
        session.user_data_dir = user_data_dir

        import random
        debug_port = random.randint(9223, 9999)
        session.debug_port = debug_port

        try:
            if session.browser_type == BrowserType.CHROME:
                process = subprocess.Popen([
                    executable_path,
                    f'--remote-debugging-port={debug_port}',
                    '--no-first-run',
                    '--no-default-browser-check',
                    f'--user-data-dir={user_data_dir}',
                    '--disable-features=TranslateUI',
                    '--disable-extensions',
                    '--ignore-certificate-errors',  # 忽略SSL证书错误
                    '--ignore-ssl-errors',  # 忽略SSL错误
                    '--allow-insecure-localhost',
                    '--allow-running-insecure-content',
                    '--disable-web-security',  # 禁用同源策略
                    '--disable-blink-features=AutomationControlled',  # 隐藏自动化控制
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-breakpad',  # 禁用崩溃报告
                    '--disable-component-update',  # 禁用组件更新
                    '--disable-domain-reliability',
                    launch_url
                ])
            elif session.browser_type == BrowserType.FIREFOX:
                process = subprocess.Popen([
                    executable_path,
                    f'--remote-debugging-port={debug_port}',
                    launch_url
                ])
            else:
                process = subprocess.Popen([
                    executable_path,
                    f'--remote-debugging-port={debug_port}',
                    '--no-first-run',
                    f'--user-data-dir={user_data_dir}',
                    launch_url
                ])

            session.process_pid = process.pid
            session.update_status(SessionStatus.RUNNING)
            logger.info(f'Browser launched successfully for session: {session_id} on port {debug_port}')

            from backend.app import socketio
            socketio.emit('browser_launched', {
                'session_id': session_id,
                'debug_port': debug_port
            }, room=session_id)

            def wait_for_debug_port(port: int, timeout: float = 3.0) -> bool:
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=1):
                            return True
                    except OSError:
                        time.sleep(0.2)
                return False

            def run_debugging():
                if not wait_for_debug_port(debug_port):
                    logger.error(f'Debug port {debug_port} not ready in time for session {session_id}')
                    session.update_status(SessionStatus.ERROR, 'Browser debug port not ready')
                    return
                try:
                    from modules.cdp.cdp_client import CDPClient
                    from modules.debug.debug_processor import set_breakpoint, set_xhr_breakpoint, set_xhr_new_breakpoint
                    from ai_debugger.ai_debugger import continuous_debugging
                    from backend.app import socketio

                    import asyncio

                    async def debug_task():
                        client = None
                        try:
                            client = await CDPClient.connect_to_existing(
                                target_url,
                                port=debug_port,
                                auto_navigate=False
                            )
                            session_manager.set_runtime(session_id, asyncio.get_running_loop(), client)

                            if session.is_xhr_mode:
                                xhr_url = session.config.xhr_url or ''
                                await set_xhr_breakpoint(client.client, xhr_url)
                                socketio.emit('breakpoint_set', {
                                    'session_id': session_id,
                                    'mode': 'xhr',
                                    'url_pattern': xhr_url
                                }, room=session_id)
                                js_ready_event = asyncio.Event()
                                xhr_task = asyncio.create_task(
                                    set_xhr_new_breakpoint(client.client, xhr_url, js_ready_event)
                                )
                                async def notify_xhr_ready():
                                    try:
                                        await xhr_task
                                        socketio.emit('xhr_stack_ready', {
                                            'session_id': session_id,
                                            'message': 'XHR模式已回溯堆栈，请重新触发断点'
                                        }, room=session_id)
                                    except Exception as e:
                                        socketio.emit('xhr_stack_ready', {
                                            'session_id': session_id,
                                            'error': str(e)
                                        }, room=session_id)
                                asyncio.create_task(notify_xhr_ready())
                                try:
                                    await client.client.send("Page.reload", {"ignoreCache": True})
                                except Exception:
                                    pass
                            elif session.is_js_mode:
                                js_file = session.config.js_file
                                if js_file and session.config.effective_line is not None:
                                    await set_breakpoint(
                                        client.client,
                                        js_file,
                                        session.config.line_0based,
                                        session.config.column_0based
                                    )
                                    socketio.emit('breakpoint_set', {
                                        'session_id': session_id,
                                        'mode': 'js',
                                        'file': js_file,
                                        'line': session.config.effective_line,
                                        'column': session.config.column_0based
                                    }, room=session_id)

                            ai_provider = session.ai_provider
                            def on_event(name, payload):
                                try:
                                    seq = last_debug_seq.get(session_id, 0) + 1
                                    last_debug_seq[session_id] = seq
                                    data = {
                                        'session_id': session_id,
                                        'ts': time.time(),
                                        'seq': seq,
                                        **(payload or {})
                                    }
                                    socketio.emit(f'debug_{name}', data, room=session_id)
                                    if name == 'paused':
                                        last_debug_events[session_id] = data
                                except Exception as e:
                                    logger.error(f'Failed to emit socket event: {e}')
                            if session.is_xhr_mode:
                                await continuous_debugging(
                                    client,
                                    breakpoint_mode=session.breakpoint_mode.value,
                                    duration=600,
                                    model_type=ai_provider,
                                    js_ready_event=js_ready_event,
                                    auto_reload_on_start=True,  # XHR模式需要reload
                                    on_event=on_event,
                                    session_config=session.config  # 传递会话配置
                                )
                            else:
                                await continuous_debugging(
                                    client,
                                    breakpoint_mode=session.breakpoint_mode.value,
                                    duration=600,
                                    model_type=ai_provider,
                                    auto_reload_on_start=True,  # 注册监听器后再reload
                                    on_event=on_event,
                                    session_config=session.config,  # 传递会话配置
                                    initial_navigate_url=target_url
                                )

                        except Exception as e:
                            logger.error(f'Debugging error for session {session_id}: {e}')
                            session.update_status(SessionStatus.ERROR, str(e))
                        finally:
                            try:
                                if client:
                                    await client.close()
                            finally:
                                session_manager.clear_runtime(session_id)

                    asyncio.run(debug_task())

                except Exception as e:
                    logger.error(f'Failed to run debugging for session {session_id}: {e}')
                    session.update_status(SessionStatus.ERROR, str(e))
                finally:
                    if session.status in (SessionStatus.RUNNING, SessionStatus.CREATED):
                        session.update_status(SessionStatus.COMPLETED)

            debug_thread = threading.Thread(target=run_debugging)
            debug_thread.daemon = True
            debug_thread.start()

        except Exception as e:
            logger.error(f'Failed to launch browser: {e}')
            session.update_status(SessionStatus.ERROR, f'Failed to launch browser: {str(e)}')
            return jsonify({
                'success': False,
                'error': f'Failed to launch browser: {str(e)}'
            }), 500

        logger.info(f'Debug session started: {session_id}')

        return jsonify({
            'success': True,
            'data': session.to_dict(include_runtime=True),
            'message': '调试会话已启动，正在执行断点调试'
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        logger.error(f'Failed to start debug session: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id):
    """停止调试会话"""
    try:
        session = session_manager.get(session_id)
        if session is None:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        runtime = session_manager.get_runtime(session_id)
        if runtime and runtime.has_client():
            try:
                fut = asyncio.run_coroutine_threadsafe(runtime.client.close(), runtime.loop)
                fut.result(timeout=3)
            except Exception as e:
                logger.warning(f'Failed to close runtime client for session {session_id}: {e}')
            finally:
                session_manager.clear_runtime(session_id)
        else:
            session_manager.clear_runtime(session_id)

        browser_closed = False
        if session.process_pid:
            try:
                proc = psutil.Process(session.process_pid)
                children = proc.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                proc.terminate()
                _, alive = psutil.wait_procs([proc], timeout=3)
                for p in alive:
                    try:
                        p.kill()
                    except Exception:
                        pass
                browser_closed = True
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                browser_closed = True
            except Exception as e:
                logger.warning(f'Failed to terminate browser process for session {session_id}: {e}')
            finally:
                session.process_pid = None

        if session.user_data_dir:
            try:
                shutil.rmtree(session.user_data_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f'Failed to remove user data dir for session {session_id}: {e}')
            finally:
                session.user_data_dir = None
        session.debug_port = None

        session.update_status(SessionStatus.STOPPED)
        from backend.app import socketio
        socketio.emit('debug_stopped', {'session_id': session_id, 'browser_closed': browser_closed}, room=session_id)
        logger.info(f'Debug session stopped: {session_id}')
        return jsonify({'success': True, 'data': session.to_dict(), 'browser_closed': browser_closed})
    except Exception as e:
        logger.error(f'Failed to stop debug session: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/session/<session_id>/delete', methods=['DELETE'])
def delete_session(session_id):
    """删除调试会话"""
    try:
        if not session_manager.delete(session_id):
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        logger.info(f'Debug session deleted: {session_id}')

        return jsonify({
            'success': True,
            'message': 'Session deleted successfully'
        })
    except Exception as e:
        logger.error(f'Failed to delete debug session: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/sessions', methods=['GET'])
def list_sessions():
    """获取所有调试会话列表"""
    try:
        sessions = session_manager.list_all()
        sessions_sorted = sorted(
            sessions,
            key=lambda s: getattr(s, 'updated_at', ''),
            reverse=True
        )
        sessions_list = [s.to_dict() for s in sessions_sorted]

        return jsonify({
            'success': True,
            'data': {
                'sessions': sessions_list,
                'total': len(sessions_list)
            }
        })
    except Exception as e:
        logger.error(f'Failed to list debug sessions: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/session/<session_id>/last', methods=['GET'])
def get_last_event(session_id):
    """获取该会话的最后一次暂停事件（WS 失败时的轮询兜底）"""
    try:
        evt = last_debug_events.get(session_id)
        if not evt:
            return jsonify({'success': True, 'data': None})
        return jsonify({'success': True, 'data': evt})
    except Exception as e:
        logger.error(f'Failed to get last event: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/continue', methods=['POST'])
def debug_continue(session_id):
    """继续执行"""
    try:
        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error

        fut = asyncio.run_coroutine_threadsafe(runtime.client.client.send('Debugger.resume'), runtime.loop)
        fut.result(timeout=2)
        from backend.app import socketio
        socketio.emit('debug_resumed', {'session_id': session_id, 'step': 'Debugger.resume'}, room=session_id)
        return jsonify({'success': True, 'message': 'Continue sent'})
    except Exception as e:
        logger.error(f'Failed to continue debug session: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/step-into', methods=['POST'])
def debug_step_into(session_id):
    """单步进入"""
    try:
        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error

        fut = asyncio.run_coroutine_threadsafe(runtime.client.client.send('Debugger.stepInto'), runtime.loop)
        fut.result(timeout=2)
        from backend.app import socketio
        socketio.emit('debug_resumed', {'session_id': session_id, 'step': 'Debugger.stepInto'}, room=session_id)
        return jsonify({'success': True, 'message': 'StepInto sent'})
    except Exception as e:
        logger.error(f'Failed to step into: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/step-out', methods=['POST'])
def debug_step_out(session_id):
    """单步跳出"""
    try:
        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error

        fut = asyncio.run_coroutine_threadsafe(runtime.client.client.send('Debugger.stepOut'), runtime.loop)
        fut.result(timeout=2)
        from backend.app import socketio
        socketio.emit('debug_resumed', {'session_id': session_id, 'step': 'Debugger.stepOut'}, room=session_id)
        return jsonify({'success': True, 'message': 'StepOut sent'})
    except Exception as e:
        logger.error(f'Failed to step out: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/analyze', methods=['POST'])
def analyze_session(session_id):
    """AI 分析调试会话的日志数据"""
    try:
        session = session_manager.get(session_id)
        if session is None:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        logger.info(f'Manual AI analysis requested for session: {session_id}')

        from modules.utils import get_debug_session_filename
        import os

        debug_file = get_debug_session_filename()
        if not debug_file or not os.path.exists(debug_file):
            return jsonify({
                'success': False,
                'error': '调试日志文件不存在，请先完成调试'
            }), 400

        from backend.services.ai_manager import ai_manager
        report_path = ai_manager.debugger_analyze(debug_file, provider=session.ai_provider)

        if report_path:
            return jsonify({
                'success': True,
                'message': '分析完成',
                'report_path': report_path
            })
        else:
            return jsonify({
                'success': False,
                'error': 'AI分析失败'
            }), 500

    except Exception as e:
        logger.error(f'Failed to analyze session: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/session/<session_id>/context', methods=['GET'])
def get_context_snippet(session_id):
    """基于脚本ID与位置返回上下文片段（仅展示上下文，不返回整文件）"""
    try:
        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error

        script_id = request.args.get('scriptId')
        line = int(request.args.get('line', '1'))
        column = int(request.args.get('column', '1'))

        line0 = max(0, line - 1)
        column0 = max(0, column - 1)
        fut = asyncio.run_coroutine_threadsafe(
            get_code_context(runtime.client.client, script_id, line0, column0), runtime.loop
        )
        ctx = fut.result(timeout=3)
        return jsonify({'success': True, 'data': ctx})
    except Exception as e:
        logger.error(f'Failed to get context: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/script/<script_id>/source', methods=['GET'])
def get_script_source_api(session_id, script_id):
    """获取脚本源码（用于前端选择调用栈时拉取源码）"""
    try:
        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error

        fut = asyncio.run_coroutine_threadsafe(
            runtime.client.client.send('Debugger.getScriptSource', {'scriptId': script_id}),
            runtime.loop
        )
        resp = fut.result(timeout=3)
        source = resp.get('scriptSource', '') if isinstance(resp, dict) else ''
        return jsonify({'success': True, 'data': {'source': source}})
    except Exception as e:
        logger.error(f'Failed to get script source: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/object/<path:object_id>/properties', methods=['GET'])
def get_object_properties_api(session_id, object_id):
    """按 objectId 获取对象属性（前端展开变量时调用）"""
    try:
        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error

        depth = int(request.args.get('depth', '1'))
        base_total = 15
        use_session_cfg = False
        try:
            session = session_manager.get(session_id)
            if session and getattr(session, 'config', None):
                cfg = session.config
                if getattr(cfg, 'scope_max_total_props', None) is not None:
                    base_total = int(cfg.scope_max_total_props)
                    use_session_cfg = True
        except Exception:
            pass

        if not use_session_cfg:
            try:
                from backend.config import config as _cfg
                base_total = int(_cfg.get('debug.scope_max_total_props', base_total))
            except Exception:
                pass

        if base_total <= 0:
            base_total = 15

        def simplify_props(result_list, level=0):
            out = []
            if not isinstance(result_list, list):
                return out
            max_props = base_total if level == 0 else max(5, base_total // 2)
            for prop in result_list[:max_props]:
                name = prop.get('name')
                val = prop.get('value') or {}
                vtype = val.get('type') or 'undefined'
                entry = {'name': name, 'value': {'type': vtype}}
                if vtype in ('string', 'number', 'boolean'):
                    entry['value']['value'] = val.get('value')
                elif vtype == 'object':
                    entry['value']['objectId'] = val.get('objectId')
                    entry['value']['subtype'] = val.get('subtype')
                out.append(entry)
            return out

        fut = asyncio.run_coroutine_threadsafe(
            runtime.client.client.send('Runtime.getProperties', {
                'objectId': object_id,
                'ownProperties': True,
                'generatePreview': False
            }), runtime.loop
        )
        resp = fut.result(timeout=4)
        base = simplify_props(resp.get('result') or [], 0)
        return jsonify({'success': True, 'data': {'properties': base}})
    except Exception as e:
        logger.error(f'Failed to get properties: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/session/<session_id>/frame/<int:frame_index>/scopes', methods=['GET'])
def get_frame_scopes(session_id, frame_index):
    """获取最后一次暂停事件中某个帧的轻量作用域（仅首个作用域，最多12属性）"""
    try:
        evt = last_debug_events.get(session_id)
        if not evt:
            return jsonify({'success': False, 'error': 'No paused event'}), 404
        frames = evt.get('callFrames') or []
        if frame_index < 0 or frame_index >= len(frames):
            return jsonify({'success': False, 'error': 'Frame index out of range'}), 400
        frame = frames[frame_index]

        runtime, error = _get_runtime_or_error(session_id)
        if error:
            return error
        scopes = []
        sc_list = frame.get('scopeChain') or []
        if sc_list:
            sc = sc_list[0]
            oid = (sc.get('object') or {}).get('objectId')
            props = []
            if oid:
                fut = asyncio.run_coroutine_threadsafe(
                    runtime.client.client.send('Runtime.getProperties', {
                        'objectId': oid,
                        'ownProperties': True,
                        'generatePreview': False
                    }), runtime.loop
                )
                resp = fut.result(timeout=4)
                for p in (resp.get('result') or [])[:12]:
                    nm = p.get('name')
                    vv = p.get('value') or {}
                    tp = vv.get('type') or 'undefined'
                    if tp in ('string','number','boolean'):
                        props.append({'name': nm, 'value': {'type': tp, 'value': vv.get('value')}})
                    else:
                        props.append({'name': nm, 'value': {'type': 'object', 'value': None, 'objectId': vv.get('objectId')}})
            scopes.append({'type': sc.get('type',''), 'object': {'properties': props}})
        return jsonify({'success': True, 'data': {'scopeChain': scopes}})
    except Exception as e:
        logger.error(f'Failed to get frame scopes: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
