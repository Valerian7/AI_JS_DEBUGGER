import asyncio
from pyppeteer import launch

class CDPClient:
    """Chrome DevTools Protocol客户端
    
    该类封装了与Chrome浏览器通信的CDP会话，提供了浏览器启动、页面导航和CDP命令发送等功能。
    通过CDP协议，可以实现对JavaScript执行过程的精确控制和调试。
    """
    
    def __init__(self, browser, client):
        """初始化CDP客户端
        
        Args:
            browser: Pyppeteer浏览器实例
            client: CDP会话实例
        """
        self.browser = browser
        self.client = client

    @classmethod
    async def launch_browser_and_create_client(cls, target_url: str, executable_path: str = None, headless: bool = False):
        """启动浏览器并创建CDP会话
        
        Args:
            target_url: 要导航到的目标URL
            executable_path: Chrome浏览器可执行文件的路径，如果为None则使用系统默认路径
            headless: 是否以无头模式启动浏览器，默认为False（有界面模式）
            
        Returns:
            CDPClient: 配置好的CDP客户端实例
            
        Raises:
            Exception: 浏览器启动或CDP会话创建失败时抛出异常
        """
        # 配置浏览器启动选项
        args = ['--disable-web-security']  # 禁用同源策略，允许跨域请求
        browser_options = {
            'headless': headless,  # 是否以无头模式运行
            'defaultViewport': None,  # 使用默认视口大小
            'args': args,  # 浏览器启动参数
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
        await self.browser.close()
