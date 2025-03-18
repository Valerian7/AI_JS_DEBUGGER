import asyncio
from pyppeteer import launch

class CDPClient:
    def __init__(self, browser, client):
        self.browser = browser
        self.client = client

    @classmethod
    async def launch_browser_and_create_client(cls, target_url: str, executable_path: str = None, headless: bool = False):
        args = ['--disable-web-security']
        browser_options = {
            'headless': headless,
            'defaultViewport': None,
            'args': args,
        }
        if executable_path:
            browser_options['executablePath'] = executable_path

        browser = await launch(browser_options)
        page = await browser.newPage()
        await page.goto(target_url)
        client = await page.target.createCDPSession()
        await client.send("Page.bringToFront")
        await client.send("Debugger.enable")
        await client.send("Runtime.enable")
        try:
            await client.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 32})
        except Exception as e:
            print(f"⚠️ 设置异步调用堆栈深度出错: {e}")
        return cls(browser, client)

    async def send(self, method: str, params: dict):
        return await self.client.send(method, params)

    async def close(self):
        await self.browser.close()
