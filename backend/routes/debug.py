"""
调试控制路由
处理调试会话的创建、控制等操作
"""

from flask import Blueprint, request, jsonify
import logging
import re
import uuid
from datetime import datetime
import asyncio
import sys
import os
import time
import socket
import shutil
from pathlib import Path
from urllib.parse import urlparse

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

        try:
            executable_path = session.browser_executable_path
        except FileNotFoundError as e:
            error_msg = str(e)
            logger.error(error_msg)
            session.update_status(SessionStatus.ERROR, error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        if not executable_path:
            error_msg = f'未能解析 {session.browser_type.value} 可执行文件路径'
            logger.error(error_msg)
            session.update_status(SessionStatus.ERROR, error_msg)
            return jsonify({'success': False, 'error': error_msg}), 400
        target_url = session.target_url
        launch_url = target_url or 'about:blank'

        import tempfile
        user_data_dir = tempfile.mkdtemp(prefix="ai_debugger_")
        session.user_data_dir = user_data_dir

        import random
        debug_port = 0 if session.browser_type == BrowserType.CHROME else random.randint(9223, 9999)
        session.debug_port = debug_port

        session.devtools_ws_endpoint = None

        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'text': True,
            'bufsize': 1
        }
        if os.name == 'posix':
            popen_kwargs['start_new_session'] = True
        elif os.name == 'nt':
            creation_flag = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', None)
            if creation_flag is not None:
                popen_kwargs['creationflags'] = creation_flag

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
                ], **popen_kwargs)
            else:  # Edge
                process = subprocess.Popen([
                    executable_path,
                    f'--remote-debugging-port={debug_port}',
                    '--no-first-run',
                    f'--user-data-dir={user_data_dir}',
                    '--ignore-certificate-errors',
                    '--ignore-ssl-errors',
                    '--allow-insecure-localhost',
                    '--disable-web-security',
                    launch_url
                ], **popen_kwargs)

            session.process_pid = process.pid
            session.process_group_id = process.pid if os.name == 'posix' else None

            def _resolve_devtools_endpoint(wait_seconds: float = 4.0):
                """尝试从DevToolsActivePort文件或stdout解析真实的调试端点和端口"""
                nonlocal debug_port
                resolved_ws = session.devtools_ws_endpoint
                devtools_file = Path(user_data_dir) / "DevToolsActivePort"
                deadline = time.time() + wait_seconds

                while time.time() < deadline:
                    if not resolved_ws:
                        resolved_ws = session.devtools_ws_endpoint

                    if not resolved_ws and devtools_file.exists():
                        try:
                            content = devtools_file.read_text(encoding='utf-8').splitlines()
                            if len(content) >= 2:
                                port_line = content[0].strip()
                                ws_path = content[1].strip().lstrip('/')
                                if port_line.isdigit() and ws_path:
                                    debug_port = int(port_line)
                                    session.debug_port = debug_port
                                    resolved_ws = f"ws://127.0.0.1:{port_line}/{ws_path}"
                                    session.devtools_ws_endpoint = resolved_ws
                        except Exception as read_err:
                            logger.debug(f'Failed to read DevToolsActivePort: {read_err}')

                    if resolved_ws:
                        try:
                            parsed_port = urlparse(resolved_ws).port
                            if parsed_port:
                                debug_port = parsed_port
                                session.debug_port = parsed_port
                        except Exception:
                            pass
                        break

                    time.sleep(0.2)

                return resolved_ws

            def _capture_browser_output():
                nonlocal debug_port
                if not process.stdout:
                    return
                token_pattern = re.compile(
                    r"devtools listening on\s+(ws://[^\s]+)(?:\s+with token\s+([A-Za-z0-9-]+))?",
                    re.IGNORECASE
                )
                try:
                    for raw_line in iter(process.stdout.readline, ''):
                        if not raw_line:
                            break
                        line = raw_line.strip()
                        if not line:
                            continue
                        logger.debug(f'[Browser:{session_id}] {line}')
                        lowered = line.lower()

                        match = token_pattern.search(line)
                        if match:
                            endpoint = match.group(1).strip()
                            token = match.group(2)
                            if token and "token=" not in endpoint:
                                sep = '&' if '?' in endpoint else '?'
                                endpoint = f"{endpoint}{sep}token={token}"
                            if '[::1]' in endpoint:
                                endpoint = endpoint.replace('[::1]', '127.0.0.1')
                            session.devtools_ws_endpoint = endpoint
                            try:
                                parsed_port = urlparse(endpoint).port
                                if parsed_port:
                                    debug_port = parsed_port
                                    session.debug_port = parsed_port
                            except Exception:
                                pass
                            continue

                        if 'listening on ws://' in lowered:
                            parts = line.split('ws://', 1)
                            if len(parts) == 2:
                                endpoint = 'ws://' + parts[1].strip()
                                if '[::1]' in endpoint:
                                    endpoint = endpoint.replace('[::1]', '127.0.0.1')
                                session.devtools_ws_endpoint = endpoint
                except Exception as output_err:
                    logger.debug(f'Browser output reader ended: {output_err}')
                finally:
                    try:
                        process.stdout.close()
                    except Exception:
                        pass

            output_thread = threading.Thread(target=_capture_browser_output, daemon=True)
            output_thread.start()

            resolved_endpoint = _resolve_devtools_endpoint()
            if resolved_endpoint:
                logger.info(f'Session {session_id}: Resolved DevTools endpoint: {resolved_endpoint}')
            else:
                logger.debug(f'Session {session_id}: DevTools endpoint not resolved from file/stdout within timeout')

            resolved_endpoint = _resolve_devtools_endpoint(wait_seconds=6.0)
            if resolved_endpoint:
                logger.info(f'Session {session_id}: Resolved DevTools endpoint: {resolved_endpoint}')
                try:
                    parsed_port = urlparse(resolved_endpoint).port
                    if parsed_port:
                        debug_port = parsed_port
                        session.debug_port = parsed_port
                except Exception:
                    pass
            else:
                logger.debug(f'Session {session_id}: DevTools endpoint not resolved from file/stdout within timeout')

            session.update_status(SessionStatus.RUNNING)
            logger.info(f'Browser launched successfully for session: {session_id} on port {debug_port}')

            from backend.app import socketio
            socketio.emit('browser_launched', {
                'session_id': session_id,
                'debug_port': session.debug_port or debug_port
            }, room=session_id)

            def wait_for_debug_port(port: int, timeout: float = 3.0) -> bool:
                if not port or port <= 0:
                    return True
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=1):
                            return True
                    except OSError:
                        time.sleep(0.2)
                return False

            port_timeout = 6.0 if session.browser_type == BrowserType.CHROME else 12.0

            def run_debugging():
                effective_port = session.debug_port or debug_port

                if not wait_for_debug_port(effective_port, timeout=port_timeout):
                    error_msg = f'调试端口 {effective_port} 在 {port_timeout}秒 内未就绪'
                    logger.error(f'Session {session_id}: {error_msg}')
                    session.update_status(SessionStatus.ERROR, error_msg)
                    socketio.emit('debug_error', {
                        'session_id': session_id,
                        'error': error_msg,
                        'details': f'浏览器类型: {session.browser_type.value}, 端口: {effective_port}'
                    }, room=session_id)
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
                            # 在连接前再尝试解析一次端点，等待 DevToolsActivePort 或 stdout token 就绪
                            resolved_before_connect = _resolve_devtools_endpoint(wait_seconds=5.0)
                            if resolved_before_connect:
                                try:
                                    parsed_port = urlparse(resolved_before_connect).port
                                    if parsed_port:
                                        session.debug_port = parsed_port
                                except Exception:
                                    pass

                            effective_port_inner = session.debug_port or debug_port
                            if resolved_before_connect:
                                logger.info(f'Session {session_id}: Resolved DevTools endpoint before connect: {resolved_before_connect}')

                            logger.info(f'Session {session_id}: Attempting to connect to {session.browser_type.value} on port {effective_port_inner}')
                            logger.info(f'Session {session_id}: User data dir: {session.user_data_dir}')
                            logger.info(f'Session {session_id}: Known WS endpoint: {session.devtools_ws_endpoint}')

                            client = await CDPClient.connect_to_existing(
                                target_url,
                                port=effective_port_inner,
                                auto_navigate=False,
                                browser_type=session.browser_type.value,
                                user_data_dir=session.user_data_dir,
                                known_ws_endpoint=session.devtools_ws_endpoint
                            )
                            logger.info(f'Session {session_id}: Successfully connected to CDP')
                            session_manager.set_runtime(session_id, asyncio.get_running_loop(), client)

                            if session.is_xhr_mode:
                                logger.info(f'Session {session_id}: Setting up XHR mode breakpoints')
                                xhr_url = session.config.xhr_url or ''

                                # 先设置XHR断点监听器
                                await set_xhr_breakpoint(client.client, xhr_url)
                                logger.info(f'Session {session_id}: XHR breakpoint set for: {xhr_url}')

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

                                # XHR模式不需要立即reload,等待XHR请求自然触发
                                logger.info(f'Session {session_id}: XHR breakpoint ready, waiting for requests...')

                            elif session.is_js_mode:
                                logger.info(f'Session {session_id}: Setting up JS mode breakpoints')
                                js_file = session.config.js_file
                                if js_file and session.config.effective_line is not None:
                                    # 直接使用setBreakpointByUrl - CDP会在脚本加载时自动设置断点
                                    # 不需要等待脚本加载,也不需要监听器
                                    logger.info(f'Session {session_id}: Setting breakpoint: {js_file}:{session.config.effective_line}')

                                    try:
                                        await set_breakpoint(
                                            client.client,
                                            js_file,
                                            session.config.line_0based,
                                            session.config.column_0based
                                        )
                                        logger.info(f'Session {session_id}: Breakpoint configured, will activate on script load')

                                        socketio.emit('breakpoint_set', {
                                            'session_id': session_id,
                                            'mode': 'js',
                                            'file': js_file,
                                            'line': session.config.effective_line,
                                            'column': session.config.column_0based,
                                            'status': 'configured'
                                        }, room=session_id)

                                    except Exception as bp_err:
                                        logger.error(f'Session {session_id}: Failed to set breakpoint: {bp_err}')
                                        socketio.emit('breakpoint_error', {
                                            'session_id': session_id,
                                            'error': str(bp_err)
                                        }, room=session_id)
                                        raise

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
                            error_msg = str(e)
                            logger.error(f'Debugging error for session {session_id}: {error_msg}', exc_info=True)

                            # 为特定错误提供更友好的消息
                            if '无法连接到浏览器' in error_msg or 'Failed to connect' in error_msg:
                                error_msg = (
                                    f"{error_msg}\n\n"
                                    "可能的解决方案:\n"
                                    "1. 确认浏览器已成功启动\n"
                                    "2. 检查浏览器可执行文件路径是否正确\n"
                                    "3. 确保没有其他程序占用调试端口\n"
                                    "4. 尝试使用浏览器的默认安装路径"
                                )

                            session.update_status(SessionStatus.ERROR, error_msg)
                            socketio.emit('debug_error', {
                                'session_id': session_id,
                                'error': error_msg
                            }, room=session_id)
                        finally:
                            try:
                                if client:
                                    await client.close()
                            finally:
                                session_manager.clear_runtime(session_id)

                    asyncio.run(debug_task())

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f'Failed to run debugging for session {session_id}: {error_msg}', exc_info=True)
                    session.update_status(SessionStatus.ERROR, error_msg)
                    socketio.emit('debug_error', {
                        'session_id': session_id,
                        'error': error_msg
                    }, room=session_id)
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

        def terminate_by_profile(profile_dir: str) -> bool:
            matched = []
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline') or []
                    if any(profile_dir in (arg or '') for arg in cmdline):
                        matched.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if not matched:
                return False
            for proc in matched:
                try:
                    proc.terminate()
                except Exception:
                    pass
            _, alive = psutil.wait_procs(matched, timeout=3)
            for proc in alive:
                try:
                    proc.kill()
                except Exception:
                    pass
            return True

        if not browser_closed and session.user_data_dir:
            if terminate_by_profile(session.user_data_dir):
                browser_closed = True

        if session.user_data_dir:
            try:
                shutil.rmtree(session.user_data_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f'Failed to remove user data dir for session {session_id}: {e}')
            finally:
                session.user_data_dir = None
        session.debug_port = None
        session.process_group_id = None
        session.devtools_ws_endpoint = None

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
