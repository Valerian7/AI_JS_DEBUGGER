import asyncio
from modules.debug.debug_processor import process_debugger_paused
from modules.utils import compress_debug_info, async_write_to_file, get_debug_session_filename
from ai_debugger.api.qwen_api import get_debug_instruction, debugger_analyze


async def continuous_debugging(client, breakpoint_mode="js", duration=300, js_ready_event=None):
    """
    AI 引导的连续调试循环
    """
    # 重置调试会话全局变量
    import modules.utils
    modules.utils._debug_session_filename = None
    
    async def await_debugger_paused():
        future = asyncio.get_event_loop().create_future()
        
        # 保存监听器，以便后续移除
        def paused_handler(event):
            if not future.done():
                future.set_result(event)
            
        # 使用once，确保回调只执行一次
        client.client.once("Debugger.paused", paused_handler)
        
        try:
            return await future
        except asyncio.CancelledError:
            # 如果任务被取消，确保移除监听器
            client.client.remove_listener("Debugger.paused", paused_handler)
            raise
        except Exception as e:
            print(f"等待断点暂停时出错: {e}")
            raise

    async def debugging_loop():
        debug_event = None
        
        try:
            if breakpoint_mode == 'xhr' and js_ready_event:
                # 在XHR模式下，等待JS断点真正触发的事件
                print("等待XHR模式下的JS断点触发...")
                await js_ready_event.wait()
                print("✅ 收到JS断点已触发的通知，开始AI分析流程")
                
            first_pause = True
            while True:
                try:
                    # 每次循环都需要获取最新的断点事件
                    print("\n等待断点触发...")
                    debug_event = await asyncio.wait_for(await_debugger_paused(), timeout=20)
                    print("断点已触发！")

                    divider = "=" * 60
                    
                    # 执行AI分析逻辑
                    debug_info = await process_debugger_paused(debug_event, client.client)
                    compressed_debug_info = compress_debug_info(debug_info).replace(divider, "||")
                    write_task = asyncio.create_task(async_write_to_file(compressed_debug_info))
                    
                    # 等待写入完成后再获取指令，确保写入和指令获取的一致性
                    await write_task
                    instruction = await asyncio.to_thread(get_debug_instruction, compressed_debug_info)
                    print("🤖 AI 指令:", instruction)

                    if "step_into" in instruction.lower():
                        step_cmd = "Debugger.stepInto"
                    elif "step_out" in instruction.lower():
                        step_cmd = "Debugger.stepOut"
                    else:
                        step_cmd = "Debugger.stepOver"

                    print(f"执行调试命令：{step_cmd}")
                    
                    # 添加错误处理，确保连接关闭时不会抛出异常
                    try:
                        await client.client.send(step_cmd)
                    except Exception as e:
                        print(f"发送调试命令时出错: {e}")
                        break
                        
                    print("=" * 60)

                except asyncio.TimeoutError:
                    print("长时间未触发断点，调试结束")
                    if modules.utils._debug_session_filename != None:
                        print("✅ 正在分析加解密信息")
                        output_path = debugger_analyze(modules.utils._debug_session_filename)
                        print("✅ 分析完成，报告已输出至：", output_path)
                        print("关闭浏览器...")
                        await client.close()
                        print("调试会话已结束")
                        exit()
                    break
                except Exception as e:
                    print(f"调试循环中发生错误: {e}")
                    break
        except asyncio.CancelledError:
            print("调试任务被取消")
            raise
        except Exception as e:
            print(f"调试主循环发生错误: {e}")
            raise

    debug_task = asyncio.create_task(debugging_loop())
    try:
        await asyncio.sleep(duration)
    except asyncio.CancelledError:
        print("调试任务被取消")
        raise
    finally:
        # 确保任务被正确取消和清理
        if not debug_task.done():
            debug_task.cancel()
            try:
                await asyncio.wait_for(debug_task, timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                print(f"取消调试任务时发生错误: {e}")