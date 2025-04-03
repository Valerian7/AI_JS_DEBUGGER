import asyncio
import gc
from pyppeteer import launch
from modules.memory_manager import memory_manager

class CDPClient:
    """DevTools Protocol客户端
    
    该类封装了与浏览器通信的CDP会话，提供了浏览器启动、页面导航和CDP命令发送等功能。
    支持Chrome、Firefox和Edge浏览器，通过CDP协议，可以实现对JavaScript执行过程的精确控制和调试。
    
    优化点：
    - 实现增量数据收集和处理，避免一次性加载大量数据
    - 集成内存管理，自动监控和释放不必要的资源
    - 支持大型站点分析的数据分片处理
    """
    
    def __init__(self, browser, client):
        """初始化CDP客户端
        
        Args:
            browser: Pyppeteer浏览器实例
            client: CDP会话实例
        """
        self.browser = browser
        self.client = client
        self.data_buffer = {}
        self.buffer_size_limit = 50 * 1024 * 1024  # 50MB缓冲区限制
        
        # 注册内存清理回调
        memory_manager.register_cleanup_callback('cdp_client', self._cleanup_resources)

    @classmethod
    async def launch_browser_and_create_client(cls, target_url: str, executable_path: str = None, headless: bool = False, browser_type: str = "chrome"):
        """启动浏览器并创建CDP会话
        
        Args:
            target_url: 要导航到的目标URL
            executable_path: 浏览器可执行文件的路径，如果为None则使用系统默认路径
            headless: 是否以无头模式启动浏览器，默认为False（有界面模式）
            browser_type: 浏览器类型，支持"chrome"、"firefox"和"edge"，默认为"chrome"
            
        Returns:
            CDPClient: 配置好的CDP客户端实例
            
        Raises:
            Exception: 浏览器启动或CDP会话创建失败时抛出异常
        """
        # 启动内存监控
        memory_manager.start_monitoring()
        # 配置浏览器启动选项
        args = ['--disable-web-security']  # 禁用同源策略，允许跨域请求
        
        # 根据浏览器类型添加特定的启动参数
        if browser_type == "firefox":
            # Firefox特定参数
            args.extend(['--remote-debugging-port=9222'])
        elif browser_type == "edge":
            # Edge特定参数
            args.extend(['--remote-debugging-port=9222'])
        else:  # 默认为Chrome
            # Chrome特定参数
            args.extend(['--no-sandbox', '--disable-setuid-sandbox'])
        
        browser_options = {
            'headless': headless,  # 是否以无头模式运行
            'defaultViewport': None,  # 使用默认视口大小
            'args': args,  # 浏览器启动参数
            'product': browser_type if browser_type in ["chrome", "firefox"] else "chrome"  # 设置浏览器类型
        }
        
        if executable_path:
            browser_options['executablePath'] = executable_path

        # 启动浏览器
        browser = await launch(browser_options)
        # 创建新页面
        page = await browser.newPage()
        # 导航到目标URL
        await page.goto(target_url)
        # 创建CDP会话
        client = await page.target.createCDPSession()
        # 将页面带到前台
        await client.send("Page.bringToFront")
        # 启用调试器
        await client.send("Debugger.enable")
        # 启用运行时
        await client.send("Runtime.enable")
        try:
            # 设置异步调用堆栈深度，用于更好地追踪异步调用
            await client.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 32})
        except Exception as e:
            print(f"⚠️ 设置异步调用堆栈深度出错: {e}")
        # 返回配置好的CDP客户端实例
        return cls(browser, client)

    async def send(self, method: str, params: dict):
        """发送CDP命令
        
        Args:
            method: CDP命令名称
            params: CDP命令参数
            
        Returns:
            dict: CDP命令执行结果
            
        Raises:
            Exception: CDP命令执行失败时抛出异常
        """
        return await self.client.send(method, params)

    async def close(self):
        """关闭浏览器和CDP会话
        
        关闭浏览器实例，释放相关资源
        """
        # 清理资源
        self._cleanup_resources()
        # 注销内存清理回调
        memory_manager.unregister_cleanup_callback('cdp_client')
        # 停止内存监控
        memory_manager.stop_monitoring()
        # 关闭浏览器
        await self.browser.close()
    
    def _cleanup_resources(self):
        """清理CDP客户端资源
        
        清空数据缓冲区，释放内存
        """
        self.data_buffer.clear()
        gc.collect()
    
    async def collect_data_incrementally(self, method: str, params: dict, batch_size: int = 100):
        """增量收集数据
        
        对于可能返回大量数据的CDP命令，使用分批处理方式收集数据，
        避免一次性加载过多数据导致内存溢出。
        
        Args:
            method: CDP命令名称
            params: CDP命令参数
            batch_size: 每批处理的数据量
            
        Returns:
            list: 收集到的数据列表
            
        Raises:
            Exception: 数据收集失败时抛出异常
        """
        try:
            # 初始化结果列表和分页参数
            all_results = []
            current_page = 0
            has_more = True
            buffer_size = 0
            
            # 添加分页参数
            paged_params = dict(params)
            paged_params['batchSize'] = batch_size
            
            # 分批获取数据
            while has_more and buffer_size < self.buffer_size_limit:
                paged_params['pageIndex'] = current_page
                response = await self.client.send(method, paged_params)
                
                # 提取结果
                batch_results = response.get('results', [])
                all_results.extend(batch_results)
                
                # 更新缓冲区大小估计（粗略估计）
                batch_size_estimate = len(str(batch_results)) * 2  # 字符数 * 2字节
                buffer_size += batch_size_estimate
                
                # 检查是否有更多数据
                has_more = response.get('hasMore', False)
                current_page += 1
                
                # 如果数据量过大，主动触发垃圾回收
                if current_page % 5 == 0:
                    gc.collect()
            
            return all_results
        except Exception as e:
            print(f"增量收集数据失败: {e}")
            raise
    
    async def process_large_script(self, script_id: str, process_func, chunk_size: int = 5000):
        """处理大型脚本
        
        对大型JavaScript文件进行分段处理，避免一次性加载整个文件导致内存溢出。
        
        Args:
            script_id: 脚本ID
            process_func: 处理函数，接收脚本内容片段作为参数
            chunk_size: 每段处理的字符数
            
        Returns:
            处理函数的返回结果
            
        Raises:
            Exception: 脚本处理失败时抛出异常
        """
        try:
            # 获取脚本源代码
            response = await self.client.send("Debugger.getScriptSource", {"scriptId": script_id})
            source = response.get("scriptSource", "")
            
            if not source:
                return None
                
            # 如果脚本较小，直接处理
            if len(source) <= chunk_size:
                return await process_func(source)
            
            # 对大型脚本进行分段处理
            results = []
            for i in range(0, len(source), chunk_size):
                chunk = source[i:i + chunk_size]
                chunk_result = await process_func(chunk)
                
                if chunk_result:
                    if isinstance(chunk_result, list):
                        results.extend(chunk_result)
                    else:
                        results.append(chunk_result)
                
                # 主动触发垃圾回收
                if i % (chunk_size * 3) == 0:
                    gc.collect()
            
            return results
        except Exception as e:
            print(f"处理大型脚本失败: {e}")
            raise
