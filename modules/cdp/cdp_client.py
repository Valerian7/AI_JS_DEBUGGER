import asyncio
import gc
import logging
from pathlib import Path
from typing import Optional, List
from pyppeteer import launch, connect
import aiohttp

logger = logging.getLogger(__name__)

class CDPClient:
    """DevTools Protocol客户端

    该类封装了与浏览器通信的CDP会话，提供了浏览器启动、页面导航和CDP命令发送等功能。
    支持Chrome和Edge浏览器，通过CDP协议，可以实现对JavaScript执行过程的精确控制和调试。

    优化点：
    - 实现增量数据收集和处理，避免一次性加载大量数据
    - 集成内存管理，自动监控和释放不必要的资源
    - 支持大型站点分析的数据分片处理
    """
    
    def __init__(self, browser, client, target_url: str = None):
        """初始化CDP客户端
        
        Args:
            browser: Pyppeteer浏览器实例
            client: CDP会话实例
        """
        self.browser = browser
        self.client = client
        self.data_buffer = {}
        self.target_url = target_url
        self.buffer_size_limit = 50 * 1024 * 1024  # 50MB缓冲区限制

    @classmethod
    async def launch_browser_and_create_client(cls, target_url: str, executable_path: str = None, headless: bool = False, browser_type: str = "chrome"):
        """启动浏览器并创建CDP会话

        Args:
            target_url: 要导航到的目标URL
            executable_path: 浏览器可执行文件的路径，如果为None则使用系统默认路径
            headless: 是否以无头模式启动浏览器，默认为False（有界面模式）
            browser_type: 浏览器类型，支持"chrome"和"edge"，默认为"chrome"

        Returns:
            CDPClient: 配置好的CDP客户端实例

        Raises:
            Exception: 浏览器启动或CDP会话创建失败时抛出异常
        """
        args = [
            '--disable-web-security',  # 禁用同源策略，允许跨域请求
            '--ignore-certificate-errors',  # 忽略SSL证书错误
            '--ignore-ssl-errors',  # 忽略SSL错误
            '--allow-insecure-localhost',  # 允许不安全的localhost连接
            '--disable-dev-shm-usage',  # 避免/dev/shm空间不足
        ]

        if browser_type == "edge":
            args.extend(['--remote-debugging-port=9222'])
        else:  # 默认为Chrome
            args.extend([
                '--disable-blink-features=AutomationControlled',  # 隐藏自动化控制
            ])
        
        browser_options = {
            'headless': headless,  # 是否以无头模式运行
            'defaultViewport': None,  # 使用默认视口大小
            'args': args,  # 浏览器启动参数
            'product': 'chrome'  # 设置浏览器类型(Chrome或Edge都使用chrome product)
        }
        
        if executable_path:
            browser_options['executablePath'] = executable_path

        browser = await launch(browser_options)
        pages = await browser.pages()
        page = pages[0] if pages else await browser.newPage()
        await page.goto(target_url)
        client = await page.target.createCDPSession()

        script_registry = {}

        def record_script(event):
            try:
                url = event.get("url") or ""
                script_id = event.get("scriptId")
                if not url or not script_id:
                    return
                entries = script_registry.setdefault(url, [])
                if script_id not in entries:
                    entries.append(script_id)
            except Exception:
                pass

        client._script_registry = script_registry  # type: ignore[attr-defined]
        client.on("Debugger.scriptParsed", record_script)

        await client.send("Page.bringToFront")
        try:
            await client.send("Page.enable")
        except Exception:
            pass
        try:
            await client.send("Network.enable")
        except Exception:
            pass
        await client.send("Debugger.enable")
        try:
            await client.send("Debugger.setBreakpointsActive", {"active": True})
            await asyncio.sleep(0.1)
        except Exception:
            pass
        await client.send("Runtime.enable")
        try:
            await client.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 32})
        except Exception as e:
            print(f"⚠️ 设置异步调用堆栈深度出错: {e}")
        try:
            await client.send("Security.enable")
            await client.send("Security.setIgnoreCertificateErrors", {"ignore": True})
        except Exception:
            pass
        return cls(browser, client, target_url)

    @staticmethod
    async def _fetch_json(url: str) -> Optional[dict]:
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except Exception:
            return None

    @classmethod
    async def _get_ws_endpoint_from_version(cls, port: int) -> Optional[str]:
        data = await cls._fetch_json(f"http://127.0.0.1:{port}/json/version")
        if data:
            return data.get("webSocketDebuggerUrl")
        return None

    @classmethod
    async def _get_ws_endpoint_from_targets(cls, port: int) -> Optional[str]:
        for path in ("/json/list", "/json"):
            data = await cls._fetch_json(f"http://127.0.0.1:{port}{path}")
            if isinstance(data, list):
                for entry in data:
                    ws_url = entry.get("webSocketDebuggerUrl")
                    if ws_url:
                        return ws_url
        return None

    @staticmethod
    def _endpoint_from_devtools_file(user_data_dir: Optional[str]) -> Optional[str]:
        """从DevToolsActivePort文件读取WebSocket端点

        Args:
            user_data_dir: 用户数据目录路径

        Returns:
            WebSocket端点URL，如果无法读取则返回None
        """
        if not user_data_dir:
            return None
        file_path = Path(user_data_dir) / "DevToolsActivePort"
        if not file_path.exists():
            logger.debug(f"DevToolsActivePort file not found: {file_path}")
            return None
        try:
            content = file_path.read_text(encoding='utf-8').strip()
            lines = content.splitlines()
            if len(lines) >= 2:
                port = lines[0].strip()
                ws_path = lines[1].strip().lstrip('/')
                if port.isdigit() and ws_path:
                    endpoint = f"ws://127.0.0.1:{port}/{ws_path}"
                    logger.debug(f"Read WebSocket endpoint from DevToolsActivePort: {endpoint}")
                    return endpoint
                else:
                    logger.debug(f"Invalid DevToolsActivePort content: port={port}, ws_path={ws_path}")
            else:
                logger.debug(f"DevToolsActivePort has insufficient lines: {len(lines)}")
        except Exception as e:
            logger.warning(f"Error reading DevToolsActivePort file: {e}")
            return None
        return None

    @staticmethod
    def _build_fallback_endpoints(port: int, browser_type: str) -> List[str]:
        """构建fallback WebSocket端点列表

        为不同浏览器类型构建可能的WebSocket端点。
        Chrome/Edge使用标准的CDP端点格式。

        Args:
            port: 调试端口
            browser_type: 浏览器类型

        Returns:
            WebSocket端点URL列表
        """
        lowered = (browser_type or "").lower()
        candidates = []

        if lowered in ("chrome", "chromium", "edge"):
            # Chrome/Chromium/Edge的标准端点
            candidates = [
                f"ws://127.0.0.1:{port}/devtools/browser",
                f"ws://127.0.0.1:{port}/devtools/browser/",
                # 添加更多可能的端点格式
                f"ws://127.0.0.1:{port}",
            ]
        else:
            # 未知浏览器类型，使用通用端点
            candidates = [
                f"ws://127.0.0.1:{port}/devtools/browser",
                f"ws://127.0.0.1:{port}",
            ]

        logger.debug(f"Built {len(candidates)} fallback endpoints for {browser_type}")
        return candidates

    @classmethod
    async def _gather_ws_candidates(cls, port: int, browser_type: str, user_data_dir: Optional[str]) -> List[str]:
        """收集所有可能的WebSocket端点候选

        按优先级顺序收集WebSocket端点:
        1. DevToolsActivePort文件中的端点
        2. /json/version接口返回的端点
        3. /json/list接口返回的端点
        4. Fallback端点列表

        Args:
            port: 调试端口
            browser_type: 浏览器类型
            user_data_dir: 用户数据目录

        Returns:
            WebSocket端点URL列表（按优先级排序）
        """
        candidates: List[str] = []

        # 优先使用DevToolsActivePort文件（最可靠）
        file_endpoint = cls._endpoint_from_devtools_file(user_data_dir)
        if file_endpoint:
            candidates.append(file_endpoint)
            logger.debug(f"Added endpoint from DevToolsActivePort: {file_endpoint}")

        # 尝试从/json/version获取端点
        version_endpoint = await cls._get_ws_endpoint_from_version(port)
        if version_endpoint:
            candidates.append(version_endpoint)
            logger.debug(f"Added endpoint from /json/version: {version_endpoint}")

        # 尝试从/json/list获取端点
        list_endpoint = await cls._get_ws_endpoint_from_targets(port)
        if list_endpoint:
            candidates.append(list_endpoint)
            logger.debug(f"Added endpoint from /json/list: {list_endpoint}")

        # 添加fallback端点
        fallback_endpoints = cls._build_fallback_endpoints(port, browser_type)
        candidates.extend(fallback_endpoints)

        logger.debug(f"Gathered {len(candidates)} WebSocket candidates for {browser_type} on port {port}")
        return candidates

    @classmethod
    async def connect_to_existing(cls, target_url: str, port: int = 9222, auto_navigate: bool = True,
                                  browser_type: str = "chrome", user_data_dir: Optional[str] = None,
                                  known_ws_endpoint: Optional[str] = None):
        """连接到已启动的浏览器实例并获取CDP会话

        Args:
            target_url: 目标URL（用于选择/打开目标页）
            port: 远程调试端口
            auto_navigate: 为True时在找不到目标页时自动导航到target_url
            browser_type: 浏览器类型
            user_data_dir: 用户数据目录（用于查找DevToolsActivePort文件）
            known_ws_endpoint: 已知的WebSocket端点
        """
        browser_url = f"http://127.0.0.1:{port}"
        browser = None
        errors = []

        chromium_aliases = {"chrome", "chromium", "edge"}
        browser_type_key = (browser_type or "").lower()

        ws_candidates: List[str] = []
        if known_ws_endpoint:
            ws_candidates.append(known_ws_endpoint.strip())
            logger.info(f"Using known WebSocket endpoint: {known_ws_endpoint}")

        # 收集所有可能的 WebSocket 端点
        gathered_candidates = await cls._gather_ws_candidates(port, browser_type_key, user_data_dir)
        ws_candidates.extend(gathered_candidates)

        logger.info(f"Attempting to connect to {browser_type} on port {port}")
        logger.debug(f"WebSocket candidates: {ws_candidates}")

        tried = set()
        for endpoint in ws_candidates:
            if not endpoint or endpoint in tried:
                continue
            tried.add(endpoint)
            try:
                logger.debug(f"Trying to connect via: {endpoint}")
                browser = await connect(browserWSEndpoint=endpoint, defaultViewport=None)
                logger.info(f"Successfully connected to browser via {endpoint}")
                break
            except Exception as conn_err:
                error_msg = f"{endpoint} -> {conn_err}"
                errors.append(error_msg)
                logger.debug(f"Connection failed: {error_msg}")

        if browser is None:
            try:
                if browser_type_key not in chromium_aliases:
                    raise RuntimeError("BrowserURL handshake not supported for this browser")
                logger.debug(f"Attempting browserURL connection: {browser_url}")
                browser = await connect(browserURL=browser_url, defaultViewport=None)
                logger.info(f"Successfully connected to browser via browserURL: {browser_url}")
            except Exception as final_err:
                error_msg = f"{browser_url} -> {final_err}"
                errors.append(error_msg)
                logger.error(f"All connection attempts failed. Errors: {errors}")

                # 为自定义路径Chrome提供更详细的错误信息
                detailed_error = (
                    f"无法连接到浏览器的远程调试端口 {port}。\n"
                    f"浏览器类型: {browser_type}\n"
                    f"尝试的端点: {len(tried)} 个\n"
                    f"详细错误:\n" + "\n".join(f"  - {err}" for err in errors)
                )

                if user_data_dir:
                    detailed_error += f"\n用户数据目录: {user_data_dir}"

                detailed_error += (
                    "\n\n可能的原因:\n"
                    "1. 浏览器未正确启动或已崩溃\n"
                    "2. 远程调试端口未开启或被占用\n"
                    "3. 浏览器启动参数不正确\n"
                    "4. 防火墙阻止了本地连接\n"
                    "5. 自定义路径的浏览器版本过旧或不兼容"
                )

                raise RuntimeError(detailed_error) from final_err
        pages = await browser.pages()
        page = None
        if target_url:
            for p in pages:
                try:
                    if p.url and (p.url == target_url or p.url.startswith(target_url)):
                        page = p
                        break
                except Exception:
                    continue
        if page is None:
            page = pages[0] if pages else await browser.newPage()
            if auto_navigate and target_url:
                await page.goto(target_url)
        client = await page.target.createCDPSession()
        await client.send("Page.bringToFront")
        async def safe_send(method, params=None):
            try:
                await client.send(method, params or {})
            except Exception:
                pass

        await asyncio.gather(
            safe_send("Page.enable"),
            safe_send("Network.enable"),
            safe_send("Runtime.enable"),
            safe_send("Console.enable"),  # 启用 Console domain 用于捕获 Hook 输出
            safe_send("Security.enable"),
            safe_send("Debugger.enable")
        )

        try:
            await client.send("Security.setIgnoreCertificateErrors", {"ignore": True})
        except Exception:
            pass

        try:
            await client.send("Debugger.setBreakpointsActive", {"active": True})
        except Exception:
            pass
        try:
            await client.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 32})
        except Exception:
            pass

        try:
            from modules.hooks import get_hook_manager
            hook_manager = get_hook_manager()
            hook_script = hook_manager.get_combined_hook_script()

            if hook_script:
                immediate_exec_supported = True
                try:
                    await client.send("Page.addScriptToEvaluateOnNewDocument", {
                        "source": hook_script,
                        "runImmediately": True
                    })
                except Exception as inject_err:
                    immediate_exec_supported = False
                    print(f"⚠️ runImmediately 注入失败，退回兼容模式: {inject_err}")
                    await client.send("Page.addScriptToEvaluateOnNewDocument", {
                        "source": hook_script
                    })

                print(f"✓ Injected {len(hook_manager.get_hook_filenames())} hook script(s)")

                if not immediate_exec_supported:
                    await client.send("Runtime.evaluate", {
                        "expression": hook_script,
                        "returnByValue": False
                    })
        except Exception as e:
            print(f"Warning: Failed to inject hook scripts: {e}")

        return cls(browser, client, target_url)

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
        self._cleanup_resources()
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
            all_results = []
            current_page = 0
            has_more = True
            buffer_size = 0
            
            paged_params = dict(params)
            paged_params['batchSize'] = batch_size
            
            while has_more and buffer_size < self.buffer_size_limit:
                paged_params['pageIndex'] = current_page
                response = await self.client.send(method, paged_params)
                
                batch_results = response.get('results', [])
                all_results.extend(batch_results)
                
                batch_size_estimate = len(str(batch_results)) * 2  # 字符数 * 2字节
                buffer_size += batch_size_estimate
                
                has_more = response.get('hasMore', False)
                current_page += 1
                
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
            response = await self.client.send("Debugger.getScriptSource", {"scriptId": script_id})
            source = response.get("scriptSource", "")
            
            if not source:
                return None
                
            if len(source) <= chunk_size:
                return await process_func(source)
            
            results = []
            for i in range(0, len(source), chunk_size):
                chunk = source[i:i + chunk_size]
                chunk_result = await process_func(chunk)
                
                if chunk_result:
                    if isinstance(chunk_result, list):
                        results.extend(chunk_result)
                    else:
                        results.append(chunk_result)
                
                if i % (chunk_size * 3) == 0:
                    gc.collect()
            
            return results
        except Exception as e:
            print(f"处理大型脚本失败: {e}")
            raise
