import asyncio
import gc
import psutil
import os
from modules.debug.debug_processor import process_debugger_paused
from modules.utils import compress_debug_info, async_write_to_file, get_debug_session_filename
from modules.memory_manager import memory_manager, process_in_chunks

# 使用API工厂类获取相应的API模块
from ai_debugger.api.api_factory import get_api_module


async def continuous_debugging(client, breakpoint_mode="js", duration=300, js_ready_event=None, model_type="qwen"):
    """
    AI 引导的连续调试循环
    
    该函数实现了一个自动化的调试循环，通过AI分析断点处的代码和变量状态，
    自动决定下一步调试操作（步入、步出或步过），并记录调试信息用于后续分析。
    
    Args:
        client: CDP客户端实例
        breakpoint_mode: 断点模式，可选值为"js"或"xhr"，默认为"js"
        duration: 调试持续时间（秒），默认为300秒
        js_ready_event: 在XHR模式下用于协调任务的事件对象，默认为None
        model_type: 使用的大模型类型，可选值为"qwen"、"gpt"、"deepseek"、"ernie"或"spark"，默认为"qwen"
        
    Returns:
        无返回值
        
    注意:
        - 在XHR模式下，函数会等待js_ready_event被设置后才开始调试
        - 调试信息会被记录到文件中，用于后续AI分析
        - 如果长时间未触发断点，函数会自动结束并生成分析报告
        - 内存优化：实现了增量数据收集和处理，自动监控内存使用情况
    """
    # 重置调试会话全局变量，确保每次调用都创建新的调试会话文件
    import modules.utils
    modules.utils._debug_session_filename = None
    
    # 启动内存监控
    memory_manager.start_monitoring()
    
    # 注册脚本源代码缓存以进行监控
    memory_manager.register_cache('script_source_cache', modules.utils.script_source_cache)
    
    # 注册内存清理回调函数
    memory_manager.register_cleanup_callback('ai_debugger', lambda: gc.collect())
    
    # 根据model_type获取相应的API模块
    api_module = get_api_module(model_type)
    
    async def await_debugger_paused():
        """内部函数：等待调试器暂停事件
        
        创建一个Future对象并注册Debugger.paused事件监听器，
        当断点触发时，监听器会设置Future的结果，从而解除阻塞。
        
        优化点：
        - 添加内存使用监控
        - 确保资源正确释放，防止内存泄漏
        
        Returns:
            dict: 包含断点触发信息的事件对象
            
        Raises:
            asyncio.CancelledError: 如果等待过程被取消
            Exception: 等待过程中发生其他错误
        """
        # 创建Future对象，用于异步等待断点触发
        future = asyncio.get_event_loop().create_future()
        
        # 定义断点暂停事件处理函数
        def paused_handler(event):
            # 只有在Future未完成时才设置结果，防止多次触发
            if not future.done():
                future.set_result(event)
            
        # 使用once方法注册监听器，确保回调只执行一次
        # 这避免了多次触发同一个断点时的重复处理
        client.client.once("Debugger.paused", paused_handler)
        
        try:
            # 阻塞等待，直到断点被触发或超时
            return await future
        except asyncio.CancelledError:
            # 如果任务被取消（如超时或用户中断），确保移除监听器
            # 这防止了内存泄漏和意外的回调执行
            client.client.remove_listener("Debugger.paused", paused_handler)
            # 主动触发垃圾回收，释放资源
            gc.collect()
            raise
        except Exception as e:
            print(f"等待断点暂停时出错: {e}")
            # 确保移除监听器
            client.client.remove_listener("Debugger.paused", paused_handler)
            # 主动触发垃圾回收，释放资源
            gc.collect()
            raise

    async def debugging_loop():
        """内部函数：实现AI引导的调试循环
        
        该函数实现了调试的主循环逻辑：
        1. 等待断点触发
        2. 收集断点处的调试信息
        3. 使用AI分析调试信息并决定下一步操作
        4. 执行AI决定的调试命令
        5. 重复上述步骤直到超时或出错
        
        优化点：
        - 添加内存使用监控和自动清理机制
        - 实现增量数据收集和处理
        - 定期清理不必要的缓存数据
        - 对大型调试信息进行分片处理
        
        Returns:
            无返回值
            
        Raises:
            asyncio.CancelledError: 如果调试任务被取消
            Exception: 调试过程中发生其他错误
        """
        debug_event = None
        debug_count = 0
        
        try:
            if breakpoint_mode == 'xhr' and js_ready_event:
                # 在XHR模式下，等待JS断点真正触发的事件
                # 这是因为XHR断点触发后，会设置新的JS断点，需要等待新断点准备就绪
                print("等待XHR模式下的JS断点触发...")
                await js_ready_event.wait()
                print("✅ 收到JS断点已触发的通知，开始AI分析流程")
                
            first_pause = True
            while True:
                try:
                    # 每次循环前检查内存使用情况
                    memory_info = memory_manager.get_memory_info()
                    if memory_info['percent'] > 80:
                        print(f"⚠️ 内存使用率较高: {memory_info['percent']:.1f}%，触发主动清理")
                        memory_manager.force_cleanup()
                    
                    # 每10次断点处理后，清理脚本源代码缓存
                    if debug_count > 0 and debug_count % 10 == 0:
                        cache_size = len(modules.utils.script_source_cache)
                        if cache_size > 20:
                            print(f"清理脚本源代码缓存，当前大小: {cache_size}")
                            # 保留最近使用的20个脚本
                            keys_to_remove = list(modules.utils.script_source_cache.keys())[:-20]
                            for key in keys_to_remove:
                                modules.utils.script_source_cache.pop(key, None)
                            # 主动触发垃圾回收
                            gc.collect()
                    
                    # 每次循环都需要获取最新的断点事件
                    # 设置20秒超时，避免无限等待
                    print("\n等待断点触发...")
                    debug_event = await asyncio.wait_for(await_debugger_paused(), timeout=20)
                    print("断点已触发！")
                    debug_count += 1

                    divider = "=" * 60  # 用于日志分隔
                    
                    # 执行AI分析逻辑
                    # 1. 处理断点暂停事件，收集变量、调用栈等调试信息
                    debug_info = await process_debugger_paused(debug_event, client.client)
                    
                    # 2. 压缩调试信息，替换分隔符，便于存储和传输
                    compressed_debug_info = compress_debug_info(debug_info).replace(divider, "||")
                    
                    # 3. 异步写入调试信息到文件，不阻塞主线程
                    write_task = asyncio.create_task(async_write_to_file(compressed_debug_info))
                    
                    # 4. 主动触发垃圾回收，释放debug_info和compressed_debug_info占用的内存
                    debug_info = None  # 释放引用
                    gc.collect()
                    
                    # 等待写入完成后再获取指令，确保写入和指令获取的一致性
                    await write_task
                    
                    # 5. 使用线程池调用AI模型分析调试信息，获取下一步操作指令
                    # 对于大型调试信息，可能需要分片处理
                    instruction = ""
                    if len(compressed_debug_info) > 100000:  # 如果调试信息超过100KB
                        print("调试信息较大，使用分片处理...")
                        # 分片处理大型调试信息
                        chunk_size = 50000  # 50KB一个分片
                        chunks = [compressed_debug_info[i:i+chunk_size] 
                                 for i in range(0, len(compressed_debug_info), chunk_size)]
                        
                        # 只处理前两个分片（通常包含最重要的信息）
                        if len(chunks) > 2:
                            print(f"调试信息过大，只处理前 {len(chunks[:2])}/{len(chunks)} 个分片")
                            compressed_debug_info = "\n".join(chunks[:2])
                    
                    # 调用AI模型分析
                    instruction = await asyncio.to_thread(api_module.get_debug_instruction, compressed_debug_info)
                    compressed_debug_info = None  # 释放引用
                    gc.collect()
                    
                    print("🤖 AI 指令:", instruction)

                    # 6. 根据AI指令决定下一步调试操作
                    if "step_into" in instruction.lower():
                        step_cmd = "Debugger.stepInto"  # 步入函数内部
                    elif "step_out" in instruction.lower():
                        step_cmd = "Debugger.stepOut"   # 步出当前函数
                    else:
                        step_cmd = "Debugger.stepOver"  # 步过（执行当前行并停在下一行）

                    print(f"执行调试命令：{step_cmd}")
                    
                    # 7. 执行调试命令，添加错误处理，确保连接关闭时不会抛出异常
                    try:
                        await client.client.send(step_cmd)
                    except Exception as e:
                        print(f"发送调试命令时出错: {e}")
                        # 出错时退出调试循环
                        break
                        
                    print("=" * 60)

                except asyncio.TimeoutError:
                    # 8. 处理超时情况：长时间未触发断点，认为调试已完成
                    print("长时间未触发断点，调试结束")
                    if modules.utils._debug_session_filename != None:
                        # 9. 生成调试分析报告
                        print("✅ 正在分析加解密信息")
                        # 调用AI分析模块处理收集到的调试信息
                        output_path = api_module.debugger_analyze(modules.utils._debug_session_filename)
                        print("✅ 分析完成，报告已输出至：", output_path)
                        # 清理资源并退出
                        print("关闭浏览器...")
                        await client.close()
                        print("调试会话已结束")
                        exit()  # 直接退出程序
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
            # 确保清理资源
            memory_manager.unregister_cleanup_callback('ai_debugger')
            # 打印最终内存使用情况
            memory_info = memory_manager.get_memory_info()
            print(f"调试结束，最终内存使用: {memory_info['percent']:.1f}%, {memory_info['used_mb']:.1f}MB")

    # 创建调试循环任务并启动
    debug_task = asyncio.create_task(debugging_loop())
    try:
        # 设置调试持续时间，超过此时间后自动结束调试
        # 这是一个安全机制，确保调试不会无限期运行
        await asyncio.sleep(duration)
    except asyncio.CancelledError:
        # 处理外部取消请求（如用户中断）
        print("调试任务被取消")
        raise
    finally:
        # 资源清理：确保调试任务被正确取消和清理
        if not debug_task.done():
            # 取消尚未完成的调试任务
            debug_task.cancel()
            try:
                # 给予任务2秒时间进行清理
                await asyncio.wait_for(debug_task, timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                # 忽略取消和超时异常，这是预期行为
                pass
            except Exception as e:
                # 记录其他清理过程中的错误
                print(f"取消调试任务时发生错误: {e}")
        # 注意：此时调试任务已结束，但浏览器关闭由调用方负责