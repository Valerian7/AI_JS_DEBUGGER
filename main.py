import sys
import os
import platform
import asyncio
import gc
import psutil
from modules.cdp.cdp_client import CDPClient
from ai_debugger.ai_debugger import continuous_debugging
from modules.debug.debug_processor import set_breakpoint, set_xhr_breakpoint, set_xhr_new_breakpoint
from modules.memory_manager import memory_manager

# 本模块实现了JavaScript调试器的主要入口点
# 支持两种调试模式：
# 1. JS断点模式：直接在指定的JS文件、行和列设置断点
# 2. XHR断点模式：监听XHR请求，并在请求发生时设置断点

async def main():
    """主函数：启动浏览器，设置断点，并执行AI辅助的调试过程
    
    支持两种调试模式：
    1. JS断点模式：直接在指定的JS文件、行和列设置断点
    2. XHR断点模式：监听XHR请求，并在请求发生时自动设置断点
    
    整个调试过程最长持续10分钟(600秒)，可通过continuous_debugging的duration参数调整
    
    优化点：
    - 添加内存监控和资源管理
    - 实现大型站点分析的内存优化
    - 自动清理不必要的资源
    """
    # 初始化内存管理器
    print("初始化内存管理器...")
    memory_manager.start_monitoring()
    
    # 获取初始内存使用情况
    memory_info = memory_manager.get_memory_info()
    print(f"初始内存使用: {memory_info['percent']:.1f}%, {memory_info['used_mb']:.1f}MB / {memory_info['total_mb']:.1f}MB")
    # 创建事件对象，用于XHR模式下的任务协调
    js_breakpoint_ready = asyncio.Event()
    
    # 获取用户输入的目标网站URL
    target_url = input("请输入待分析站点链接：")
    
    # 自动检测操作系统并选择合适的浏览器路径
    def get_browser_path(browser_type="chrome"):
        """根据操作系统类型和浏览器类型获取浏览器可执行文件路径
        
        Args:
            browser_type: 浏览器类型，支持"chrome"、"firefox"和"edge"，默认为"chrome"
            
        Returns:
            str: 浏览器可执行文件路径，如果找不到则返回None
        """
        system = platform.system()
        
        # 定义各操作系统下常见的浏览器安装路径
        browser_paths = {
            "Windows": {
                "chrome": [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                ],
                "firefox": [
                    r"C:\Program Files\Mozilla Firefox\firefox.exe",
                    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
                ],
                "edge": [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
                ]
            },
            "Darwin": {  # macOS
                "chrome": [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                ],
                "firefox": [
                    "/Applications/Firefox.app/Contents/MacOS/firefox",
                    "~/Applications/Firefox.app/Contents/MacOS/firefox"
                ],
                "edge": [
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                    "~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
                ]
            },
            "Linux": {
                "chrome": [
                    "/usr/bin/google-chrome",
                    "/usr/bin/chromium-browser",
                    "/usr/bin/chromium"
                ],
                "firefox": [
                    "/usr/bin/firefox"
                ],
                "edge": [
                    "/usr/bin/microsoft-edge"
                ]
            }
        }
        
        # 获取当前操作系统对应的浏览器路径列表
        if system in browser_paths and browser_type in browser_paths[system]:
            paths = browser_paths[system][browser_type]
            
            # 检查路径是否存在
            for path in paths:
                # 展开用户目录(~)
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    return expanded_path
        
        # 如果找不到浏览器，返回None
        return None
    
    # 获取浏览器路径，优先尝试Chrome，如果找不到则尝试Firefox和Edge
    executable_path = get_browser_path("chrome")
    if not executable_path:
        executable_path = get_browser_path("firefox")
    if not executable_path:
        executable_path = get_browser_path("edge")
    
    # 如果所有浏览器都找不到，提示用户手动输入路径
    if not executable_path:
        print("⚠️ 未能自动检测到浏览器，请手动输入浏览器可执行文件路径")
        executable_path = input("浏览器可执行文件路径: ")
    else:
        print(f"✅ 已自动检测到浏览器路径: {executable_path}")
    
    # 启动浏览器并创建 CDP 会话
    client = await CDPClient.launch_browser_and_create_client(
        target_url, 
        executable_path=executable_path, 
        headless=False,
        browser_type=browser_type
    )
    
    # 获取用户选择的断点模式
    breakpoint_mode = input("请选择断点模式(js/xhr): ")
    
    # 获取用户选择的浏览器类型
    browser_type = input("请选择使用的浏览器类型(chrome/firefox/edge)，默认为chrome: ") or "chrome"
    
    # 获取用户选择的大模型类型
    model_type = input("请选择使用的大模型API(qwen/gpt/deepseek/ernie/spark)，默认为qwen: ") or "qwen"

    if breakpoint_mode == "xhr":  # XHR断点模式
        xhr_url = input("请输入XHR请求URL(不填写则监听所有请求): ")
        await set_xhr_breakpoint(client.client, xhr_url)

        # 重置事件状态，确保事件初始状态为未触发
        js_breakpoint_ready.clear()
        
        # 创建两个异步任务：
        # 1. XHR断点处理任务：监听XHR请求并设置新的JS断点
        xhr_task = asyncio.create_task(
            set_xhr_new_breakpoint(client.client, xhr_url, js_breakpoint_ready)
        )
        
        # 2. AI调试任务：等待js_breakpoint_ready事件被触发后开始执行
        # 当XHR请求被捕获并设置了新的JS断点后，js_breakpoint_ready事件会被设置
        ai_debug_task = asyncio.create_task(
            continuous_debugging(client, breakpoint_mode=breakpoint_mode, duration=600, 
                                js_ready_event=js_breakpoint_ready, model_type=model_type)
        )
        
        # 任务协调与错误处理部分
        try:
            # 等待任一任务完成（使用FIRST_COMPLETED模式）
            # 这允许我们在任一任务完成时立即响应，而不必等待所有任务
            done, pending = await asyncio.wait(
                [xhr_task, ai_debug_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 特殊情况处理：如果XHR任务完成但AI调试任务仍在运行
            # 这种情况通常发生在XHR断点已成功设置，但AI调试尚未完成时
            if xhr_task in done and ai_debug_task in pending:
                try:
                    # 等待AI调试任务完成，因为它是主要的分析任务
                    await ai_debug_task
                except Exception as e:
                    print(f"AI调试任务出错: {e}")
            
            # 清理：确保取消所有未完成的任务，防止资源泄漏
            for task in pending:
                if not task.done():
                    task.cancel()
                    try:
                        # 设置超时，确保取消操作不会无限期等待
                        await asyncio.wait_for(task, timeout=2)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        # 忽略取消和超时异常，这是预期行为
                        pass
                        
        except Exception as e:
            # 捕获并记录XHR模式执行过程中的任何异常
            print(f"执行XHR模式时发生错误: {e}")
            # 确保取消所有任务，防止资源泄漏
            for task in [xhr_task, ai_debug_task]:
                if not task.done():
                    task.cancel()

    else:  # JS断点模式
        # 获取用户输入的JS文件路径和断点位置
        js_file = input("请输入JS文件路径: ")
        line = int(input("请输入断点行数: "))
        column = int(input("请输入断点列数: "))
        
        # 设置JS断点
        await set_breakpoint(client.client, js_file, line, column)
        
        # 启动AI调试过程，持续最多10分钟
        await continuous_debugging(client, duration=600, model_type=model_type)
    
    # 清理资源：关闭浏览器和CDP会话，停止内存监控
    memory_manager.stop_monitoring()
    
    # 打印最终内存使用情况
    memory_info = memory_manager.get_memory_info()
    print(f"程序结束，最终内存使用: {memory_info['percent']:.1f}%, {memory_info['used_mb']:.1f}MB")
    
    # 强制执行垃圾回收
    gc.collect()
    print("关闭浏览器...")
    await client.close()
    print("调试会话已结束")

if __name__ == "__main__":
    try:
        # Python 3.10及以上版本使用asyncio.run()运行异步函数
        # 较低版本使用传统的事件循环方法
        if sys.version_info >= (3, 10):
            asyncio.run(main())
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
    except KeyboardInterrupt:
        # 处理用户通过Ctrl+C中断程序的情况
        print("用户中断了程序执行")
    except Exception as e:
        # 捕获并记录所有其他未处理的异常
        print(f"执行过程中出现错误: {e}")
    finally:
        # 无论程序如何结束，都确保显示此消息
        print("脚本执行完毕")