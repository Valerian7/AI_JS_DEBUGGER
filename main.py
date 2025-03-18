import sys
import asyncio
from modules.cdp.cdp_client import CDPClient
from ai_debugger.ai_debugger import continuous_debugging
from modules.debug.debug_processor import set_breakpoint, set_xhr_breakpoint, set_xhr_new_breakpoint

async def main():
    js_breakpoint_ready = asyncio.Event()
    
    target_url = input("请输入待分析站点链接：")
    # Chrome 浏览器的路径
    executable_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    #executable_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    
    # 启动浏览器并创建 CDP 会话
    client = await CDPClient.launch_browser_and_create_client(
        target_url, 
        executable_path=executable_path, 
        headless=False
    )
    
    breakpoint_mode = input("请选择断点模式(js/xhr): ")

    if breakpoint_mode == "xhr":
        xhr_url = input("请输入XHR请求URL(不填写则监听所有请求): ")
        await set_xhr_breakpoint(client.client, xhr_url)

        # 重置事件状态
        js_breakpoint_ready.clear()
        
        # 创建两个任务：XHR断点处理和AI调试
        xhr_task = asyncio.create_task(
            set_xhr_new_breakpoint(client.client, xhr_url, js_breakpoint_ready)
        )
        
        # AI调试任务会等待js_breakpoint_ready事件
        ai_debug_task = asyncio.create_task(
            continuous_debugging(client, breakpoint_mode=breakpoint_mode, duration=600, 
                                js_ready_event=js_breakpoint_ready)
        )
        
        # 等待两个任务完成，添加错误处理
        try:
            # 等待第一个完成的任务
            done, pending = await asyncio.wait(
                [xhr_task, ai_debug_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 如果xhr_task完成但ai_debug_task还在运行，等待ai_debug_task
            if xhr_task in done and ai_debug_task in pending:
                try:
                    await ai_debug_task
                except Exception as e:
                    print(f"AI调试任务出错: {e}")
            
            # 确保取消所有未完成的任务
            for task in pending:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=2)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                        
        except Exception as e:
            print(f"执行XHR模式时发生错误: {e}")
            # 确保取消所有任务
            for task in [xhr_task, ai_debug_task]:
                if not task.done():
                    task.cancel()

    else:
        js_file = input("请输入JS文件路径: ")
        line = int(input("请输入断点行数: "))
        column = int(input("请输入断点列数: "))
        await set_breakpoint(client.client, js_file, line, column)
        await continuous_debugging(client, duration=600)
    
    print("关闭浏览器...")
    await client.close()
    print("调试会话已结束")

if __name__ == "__main__":
    try:
        if sys.version_info >= (3, 10):
            asyncio.run(main())
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("用户中断了程序执行")
    except Exception as e:
        print(f"执行过程中出现错误: {e}")
    finally:
        print("脚本执行完毕")