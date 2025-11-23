import asyncio
import gc
import psutil
import os
from collections import deque
from modules.debug.debug_processor import process_debugger_paused, get_script_source, get_code_context
from modules.utils import compress_debug_info, async_write_to_file, get_debug_session_filename

from backend.services.ai_manager import AIManager
from backend.config import config as backend_config


async def continuous_debugging(client, breakpoint_mode="js", duration=300, js_ready_event=None, model_type="qwen", auto_reload_on_start=True, on_event=None, session_config=None, initial_navigate_url=None):
    """
    AI 引导的连续调试循环

    该函数实现了一个自动化的调试循环，通过AI分析断点处的代码和变量状态，
    自动决定下一步调试操作（步入、步出或步过），并记录调试信息用于后续分析。
    """
    import modules.utils
    modules.utils._debug_session_filename = None
    
    
    ai_manager = AIManager()

    pending_initial_navigation = initial_navigate_url
    hook_logs = []  # 存储 Hook 捕获的日志
    analysis_report_path = None  # 记录最近一次分析报告路径
    recent_context = deque(maxlen=3)  # 记录最近三条调试上下文，用于AI调用

    def handle_console_message(*args, **kwargs):
        """处理 Console API 调用事件"""
        try:
            params = args[0] if args else {}
            log_type = params.get("type", "log")
            args_list = params.get("args", [])

            texts = []
            for arg in args_list:
                if "value" in arg:
                    texts.append(str(arg["value"]))
                elif "description" in arg:
                    texts.append(str(arg["description"]))
                elif arg.get("type") == "object":
                    texts.append(f"[Object: {arg.get('className', 'Object')}]")
                else:
                    texts.append(str(arg))

            line = " ".join(texts)

            if "[debug]" in line:
                timestamp = params.get("timestamp", 0) / 1000  # CDP timestamp 是毫秒
                hook_logs.append({
                    "type": log_type,
                    "text": line,
                    "timestamp": timestamp
                })
        except Exception as e:
            print(f"处理 Console 事件失败: {e}")
            import traceback
            traceback.print_exc()

    def handle_log_entry(*args, **kwargs):
        """处理 Log.entryAdded 事件"""
        try:
            params = args[0] if args else {}
            entry = params.get("entry", {})
            text = entry.get("text", "")
            level = entry.get("level", "info")

            if "[debug]" in text:
                timestamp = entry.get("timestamp", 0) / 1000
                hook_logs.append({
                    "type": level,
                    "text": text,
                    "timestamp": timestamp
                })
        except Exception as e:
            print(f"处理 Log 事件失败: {e}")

    try:
        client.client.on("Runtime.consoleAPICalled", handle_console_message)
        client.client.on("Log.entryAdded", handle_log_entry)
        print("✓ Hook 监听器已注册")
    except Exception as e:
        print(f"注册 Hook 监听器失败: {e}")
        import traceback
        traceback.print_exc()

    def _scope_prop_limit(level: int = 0) -> int:
        """根据会话配置和层级计算变量预览数量"""
        base = None
        if session_config and getattr(session_config, 'scope_max_total_props', None):
            base = int(session_config.scope_max_total_props)
        if base is None:
            try:
                base = int(backend_config.get('debug.scope_max_total_props', 15))
            except Exception:
                base = 15
        if base <= 0:
            base = 15
        return max(5, base // 2) if level > 0 else base

    async def build_scope_snapshot(scope: dict, level: int = 0) -> dict:
        """为作用域生成带属性的快照，便于前端展示变量"""
        try:
            obj = scope.get('object', {}) if scope else {}
            object_id = obj.get('objectId')
            props = []
            limit = _scope_prop_limit(level)
            if object_id:
                try:
                    resp = await client.client.send('Runtime.getProperties', {
                        'objectId': object_id,
                        'ownProperties': True,
                        'generatePreview': False
                    })
                    for prop in (resp.get('result') or [])[:limit]:
                        name = prop.get('name')
                        val = prop.get('value') or {}
                        vtype = val.get('type') or 'undefined'
                        entry = {'name': name, 'value': {'type': vtype}}
                        if vtype in ('string', 'number', 'boolean'):
                            entry['value']['value'] = val.get('value')
                        elif vtype == 'object':
                            entry['value']['objectId'] = val.get('objectId')
                            entry['value']['subtype'] = val.get('subtype')
                        props.append(entry)
                except Exception:
                    pass
            payload = {
                'type': scope.get('type', '') if scope else '',
                'object': {'objectId': object_id or ''}
            }
            if props:
                payload['object']['properties'] = props
            return payload
        except Exception:
            return {'type': scope.get('type', '') if scope else '', 'object': {}}

    async def await_debugger_paused(trigger_reload: bool = False, resume: bool = False, initial_navigate: str = None):
        """内部函数：等待调试器暂停事件
        
        创建一个Future对象并注册Debugger.paused事件监听器，
        当断点触发时，监听器会设置Future的结果，从而解除阻塞。

        """
        future = asyncio.get_event_loop().create_future()
        
        def paused_handler(event):
            if not future.done():
                future.set_result(event)
            
        client.client.once("Debugger.paused", paused_handler)
        
        if initial_navigate:
            try:
                await client.client.send("Page.navigate", {
                    "url": initial_navigate,
                    "transitionType": "typed"
                })
            except Exception as e:
                print(f"触发首次导航失败: {e}")
        elif trigger_reload:
            try:
                await client.client.send("Page.reload", {"ignoreCache": True})
            except Exception as e:
                print(f"触发首次页面重载失败: {e}")
        if resume:
            try:
                await client.client.send("Debugger.resume")
            except Exception as e:
                print(f"恢复执行失败: {e}")
        
        try:
            return await future
        except asyncio.CancelledError:
            client.client.remove_listener("Debugger.paused", paused_handler)
            raise
        except Exception as e:
            print(f"等待断点暂停时出错: {e}")
            client.client.remove_listener("Debugger.paused", paused_handler)
            raise

    async def debugging_loop():
        """内部函数：实现AI引导的调试循环
        
        该函数实现了调试的主循环逻辑：
        1. 等待断点触发
        2. 收集断点处的调试信息
        3. 使用AI分析调试信息并决定下一步操作
        4. 执行AI决定的调试命令
        5. 重复上述步骤直到超时或出错
        """
        nonlocal pending_initial_navigation, hook_logs, analysis_report_path
        debug_event = None
        debug_count = 0

        try:
            if breakpoint_mode == 'xhr' and js_ready_event:
                print("等待XHR模式下的新JS断点准备...")
                await js_ready_event.wait()
                print("✅ 新JS断点已准备，将在首次循环中注册监听后再恢复执行")

            first_pause = True
            while True:
                try:
                    
                    print("\n等待断点触发...")

                    # 确定是否需要导航/reload
                    nav_url = pending_initial_navigation if (first_pause and pending_initial_navigation) else None
                    # JS模式: 首次需要导航或reload以加载脚本
                    # XHR模式: 不需要reload,等待XHR请求自然触发
                    trigger_reload = (first_pause and breakpoint_mode == 'js' and auto_reload_on_start and not nav_url)
                    resume_flag = (first_pause and breakpoint_mode == 'xhr')

                    # 首次加载给更多时间(60秒),后续断点保持30秒超时
                    timeout_duration = 60.0 if first_pause else 30.0

                    debug_event = await asyncio.wait_for(
                        await_debugger_paused(
                            trigger_reload=trigger_reload,
                            resume=resume_flag,
                            initial_navigate=nav_url
                        ),
                        timeout=timeout_duration
                    )
                    if nav_url:
                        pending_initial_navigation = None
                    print("断点已触发！")
                    debug_count += 1
                    first_pause = False

                    divider = "=" * 60  # 用于日志分隔
                    
                    debug_info = await process_debugger_paused(debug_event, client.client, session_config)

                    if debug_info is None:
                        try:
                            await client.client.send("Debugger.resume")
                        except Exception:
                            pass
                        continue  # 跳过当前循环，等待下一次暂停

                    try:
                        top = debug_event.get('callFrames', [{}])[0]
                        loc = top.get('location', {}) if top else {}
                        function_name = top.get('functionName') if top else ''
                        script_id = loc.get('scriptId') if loc else None
                        line = (loc.get('lineNumber') or 0) + 1
                        col = (loc.get('columnNumber') or 0) + 1
                        script_url = top.get('url') if top else ''
                        src = ''
                        scopes_payload = []
                        if script_id:
                            try:
                                src = await get_script_source(client.client, script_id)
                            except Exception:
                                src = ''
                        try:
                            scope_chain = top.get('scopeChain', []) if top else []
                            for idx_scope, scope in enumerate(scope_chain[:2]):
                                scopes_payload.append(await build_scope_snapshot(scope, idx_scope))
                        except Exception:
                            scopes_payload = []
                        context_lines = []
                        context_text = ''
                        try:
                            if script_id is not None:
                                ctx = await get_code_context(client.client, script_id, (loc.get('lineNumber') or 0), (loc.get('columnNumber') or 0))
                                context_lines = ctx.get('context_lines', [])
                                context_text = ctx.get('context_text', '')
                        except Exception:
                            context_lines = []
                            context_text = ''

                        frames_payload = []
                        try:
                            for idx_f, f in enumerate((debug_event.get('callFrames') or [])):
                                floc = f.get('location', {})
                                item = {
                                    'functionName': f.get('functionName') or '(anonymous)',
                                    'url': f.get('url') or '',
                                    'lineNumber': (floc.get('lineNumber') or 0) + 1,
                                    'columnNumber': (floc.get('columnNumber') or 0) + 1,
                                    'scriptId': (floc or {}).get('scriptId'),
                                    'callFrameId': f.get('callFrameId')
                                }
                                try:
                                    sc_list = []
                                    for level, sc in enumerate((f.get('scopeChain') or [])[:1]):
                                        sc_list.append(await build_scope_snapshot(sc, level))
                                    item['scopeChain'] = sc_list
                                except Exception:
                                    item['scopeChain'] = []
                                frames_payload.append(item)
                        except Exception:
                            frames_payload = []

                        if on_event:
                            on_event('paused', {
                                'location': {
                                    'functionName': function_name,
                                    'scriptId': script_id,
                                    'scriptUrl': script_url,
                                    'lineNumber': line,
                                    'columnNumber': col
                                },
                                'source': src,
                                'scopeChain': scopes_payload,
                                'context': context_lines,
                                'context_text': context_text,
                                'callFrames': frames_payload
                            })
                    except Exception:
                        pass
                    
                    compressed_debug_info = compress_debug_info(debug_info).replace(divider, "||")

                    asyncio.create_task(async_write_to_file(compressed_debug_info))

                    debug_info = None
                    
                    instruction = ""
                    if len(compressed_debug_info) > 100000:  # 如果调试信息超过100KB
                        print("调试信息较大，使用分片处理...")
                        chunk_size = 50000  # 50KB一个分片
                        chunks = [compressed_debug_info[i:i+chunk_size] 
                                 for i in range(0, len(compressed_debug_info), chunk_size)]
                        
                        if len(chunks) > 2:
                            print(f"调试信息过大，只处理前 {len(chunks[:2])}/{len(chunks)} 个分片")
                            compressed_debug_info = "\n".join(chunks[:2])
                    
                    history_payload = list(recent_context)
                    current_context_entry = compressed_debug_info
                    try:
                        instruction = await asyncio.to_thread(
                            ai_manager.get_debug_instruction,
                            compressed_debug_info,
                            model_type,
                            history_payload
                        )
                    except Exception as e:
                        if on_event:
                            on_event('ai_error', {'message': str(e)})
                        instruction = 'step_over'
                    finally:
                        if current_context_entry:
                            recent_context.append(current_context_entry[:2000])
                    compressed_debug_info = None
                    
                    print("🤖 AI 指令:", instruction)

                    if "step_into" in instruction.lower():
                        step_cmd = "Debugger.stepInto"  # 步入函数内部
                    elif "step_out" in instruction.lower():
                        step_cmd = "Debugger.stepOut"   # 步出当前函数
                    else:
                        step_cmd = "Debugger.stepOver"  # 步过（执行当前行并停在下一行）

                    print(f"执行调试命令：{step_cmd}")
                    
                    try:
                        await client.client.send(step_cmd)
                        if on_event:
                            on_event('resumed', {'step': step_cmd})
                    except Exception as e:
                        msg = str(e)
                        if 'while paused' in msg:
                            print("当前非暂停状态，跳过本次步调，继续等待下一次暂停")
                            continue
                        print(f"发送调试命令时出错: {e}")
                        if on_event:
                            on_event('error', {'message': str(e)})
                        break
                        
                    print("=" * 60)

                except asyncio.TimeoutError:
                    print("长时间未触发断点，调试结束")

                    if hook_logs and modules.utils._debug_session_filename:
                        try:
                            with open(modules.utils._debug_session_filename, 'a', encoding='utf-8') as f:
                                f.write("\n\n")
                                f.write("=" * 60 + "\n")
                                f.write("🎣 Hook 捕获的加解密信息\n")
                                f.write("=" * 60 + "\n\n")
                                for log_entry in hook_logs:
                                    f.write(f"[{log_entry['type']}] {log_entry['text']}\n")
                            print(f"✓ 已将 {len(hook_logs)} 条 Hook 日志写入调试文件")

                            if on_event:
                                for log_entry in hook_logs:
                                    on_event('hook_log', {
                                        'type': log_entry['type'],
                                        'text': log_entry['text'],
                                        'timestamp': log_entry['timestamp']
                                    })
                        except Exception as e:
                            print(f"写入 Hook 日志失败: {e}")

                    if modules.utils._debug_session_filename != None:
                        print("✅ 正在分析加解密信息")
                        target_url = getattr(client, 'target_url', None)
                        output_path = ai_manager.debugger_analyze(modules.utils._debug_session_filename, provider=model_type, target_url=target_url)
                        if output_path:
                            print("✅ 分析完成，报告已输出至：", output_path)
                            analysis_report_path = output_path
                            if on_event:
                                on_event('analysis_done', {'report': output_path})
                        else:
                            print("⚠️ 分析失败，未生成报告")
                            if on_event:
                                on_event('analysis_failed', {})
                        break
                    break  # 如果没有调试会话文件，只退出循环
                except Exception as e:
                    print(f"调试循环中发生错误: {e}")
                    break
        except asyncio.CancelledError:
            print("调试任务被取消")
            raise
        except Exception as e:
            print(f"调试主循环发生错误: {e}")
            raise
        finally:
            payload = {'report': analysis_report_path} if analysis_report_path else {}
            if on_event:
                try:
                    on_event('stopped', payload)
                except Exception:
                    pass

    debug_task = asyncio.create_task(debugging_loop())
    try:
        await asyncio.wait_for(debug_task, timeout=duration)
    except asyncio.TimeoutError:
        print("调试超过最大时长，准备取消调试任务")
    except asyncio.CancelledError:
        print("调试任务被取消")
        raise
    except Exception as e:
        print(f"调试任务异常结束: {e}")
        raise
    finally:
        if not debug_task.done():
            debug_task.cancel()
            try:
                await asyncio.wait_for(debug_task, timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                print(f"取消调试任务时发生错误: {e}")
