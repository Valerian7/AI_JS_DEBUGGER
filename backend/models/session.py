"""
调试会话数据模型
使用dataclass提供类型安全和优雅的数据访问
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from threading import RLock
import os


class SessionStatus(Enum):
    """会话状态枚举"""
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class BreakpointMode(Enum):
    """断点模式枚举"""
    JS = "js"
    XHR = "xhr"


class BrowserType(Enum):
    """浏览器类型枚举"""
    CHROME = "chrome"
    EDGE = "edge"


@dataclass
class BreakpointConfig:
    """断点配置"""
    js_file: Optional[str] = None
    line: Optional[int] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    column_number: Optional[int] = None
    xhr_url: Optional[str] = None
    scope_max_depth: int = 5  # 作用域变量提取深度
    scope_max_total_props: int = 15  # 作用域变量提取总数量

    @property
    def effective_line(self) -> Optional[int]:
        """获取有效的行号（兼容不同字段名）"""
        return self.line or self.line_number

    @property
    def effective_column(self) -> Optional[int]:
        """获取有效的列号（兼容不同字段名）"""
        return self.column or self.column_number

    @property
    def line_0based(self) -> int:
        """获取0-based行号（CDP使用）"""
        line = self.effective_line
        return max(0, int(line) - 1) if line is not None else 0

    @property
    def column_0based(self) -> int:
        """获取0-based列号（CDP使用）"""
        col = self.effective_column
        return max(0, int(col) - 1) if col is not None else 0


@dataclass
class DebugSession:
    """调试会话数据类"""
    id: str
    target_url: str
    breakpoint_mode: BreakpointMode
    browser_type: BrowserType = BrowserType.CHROME
    ai_provider: str = "qwen"
    config: BreakpointConfig = field(default_factory=BreakpointConfig)
    status: SessionStatus = SessionStatus.CREATED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    debug_port: Optional[int] = field(default=None, repr=False)
    process_pid: Optional[int] = field(default=None, repr=False)
    process_group_id: Optional[int] = field(default=None, repr=False)
    user_data_dir: Optional[str] = field(default=None, repr=False)
    devtools_ws_endpoint: Optional[str] = field(default=None, repr=False)
    error: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], session_id: str) -> 'DebugSession':
        """从字典创建会话对象"""
        breakpoint_mode = data.get('breakpoint_mode', 'js')
        if isinstance(breakpoint_mode, str):
            breakpoint_mode = BreakpointMode(breakpoint_mode)

        browser_type = data.get('browser_type', 'chrome')
        if isinstance(browser_type, str):
            browser_type = BrowserType(browser_type)

        config_data = data.get('config', {})
        if isinstance(config_data, dict):
            config = BreakpointConfig(**config_data)
        else:
            config = config_data

        return cls(
            id=session_id,
            target_url=data.get('target_url', ''),
            breakpoint_mode=breakpoint_mode,
            browser_type=browser_type,
            ai_provider=data.get('ai_provider', 'qwen'),
            config=config
        )

    def to_dict(self, include_runtime: bool = False) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        result = {
            'id': self.id,
            'target_url': self.target_url,
            'breakpoint_mode': self.breakpoint_mode.value,
            'browser_type': self.browser_type.value,
            'ai_provider': self.ai_provider,
            'config': asdict(self.config),
            'status': self.status.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

        if include_runtime:
            result.update({
                'debug_port': self.debug_port,
                'process_pid': self.process_pid,
                'user_data_dir': self.user_data_dir,
                'error': self.error
            })

        return result

    def update_status(self, status: SessionStatus, error: Optional[str] = None):
        """更新会话状态"""
        self.status = status
        self.updated_at = datetime.now().isoformat()
        if error:
            self.error = error

    @property
    def is_running(self) -> bool:
        """检查会话是否正在运行"""
        return self.status == SessionStatus.RUNNING

    @property
    def is_js_mode(self) -> bool:
        """检查是否为JS断点模式"""
        return self.breakpoint_mode == BreakpointMode.JS

    @property
    def is_xhr_mode(self) -> bool:
        """检查是否为XHR断点模式"""
        return self.breakpoint_mode == BreakpointMode.XHR

    @property
    def browser_executable_path(self) -> Optional[str]:
        """获取浏览器可执行路径，优先使用自定义配置"""
        from modules.utils import get_browser_path
        from backend.config import config as app_config

        browser_key = self.browser_type.value
        browser_cfg = app_config.get('browser', {}) or {}

        env_override = os.environ.get(f'AI_DEBUGGER_{browser_key.upper()}_PATH')
        custom_path = browser_cfg.get(f'{browser_key}_path')

        for source, raw_path in (('environment', env_override), ('config', custom_path)):
            if not raw_path:
                continue
            expanded_path = os.path.expanduser(raw_path.strip())
            if os.path.exists(expanded_path):
                return expanded_path
            raise FileNotFoundError(f'{browser_key} 路径无效（来源：{source}），请确认 {expanded_path} 是否存在')

        auto_path = get_browser_path(browser_key)
        if auto_path:
            return auto_path

        raise FileNotFoundError(f'未找到 {browser_key} 浏览器，请在设置中配置可执行文件路径')


@dataclass
class SessionRuntime:
    """会话运行时数据（不可序列化的对象）"""
    loop: Any = None
    client: Any = None

    def has_client(self) -> bool:
        """检查是否有CDP客户端"""
        return self.client is not None and self.loop is not None


class SessionManager:
    """会话管理器 - 提供优雅的会话访问接口"""

    def __init__(self):
        self._sessions: Dict[str, DebugSession] = {}
        self._runtimes: Dict[str, SessionRuntime] = {}
        self._lock = RLock()

    def create(self, session_id: str, data: Dict[str, Any]) -> DebugSession:
        """创建新会话"""
        with self._lock:
            session = DebugSession.from_dict(data, session_id)
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Optional[DebugSession]:
        """获取会话（返回None而不是抛出异常）"""
        with self._lock:
            return self._sessions.get(session_id)

    def require(self, session_id: str) -> DebugSession:
        """获取会话（如果不存在则抛出异常）"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        return session

    def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        with self._lock:
            return session_id in self._sessions

    def delete(self, session_id: str) -> bool:
        """删除会话"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._runtimes.pop(session_id, None)
                return True
            return False

    def list_all(self) -> list[DebugSession]:
        """列出所有会话"""
        with self._lock:
            return list(self._sessions.values())

    def get_runtime(self, session_id: str) -> Optional[SessionRuntime]:
        """获取运行时数据"""
        with self._lock:
            return self._runtimes.get(session_id)

    def set_runtime(self, session_id: str, loop, client):
        """设置运行时数据"""
        with self._lock:
            self._runtimes[session_id] = SessionRuntime(loop=loop, client=client)

    def clear_runtime(self, session_id: str):
        """清除运行时数据"""
        with self._lock:
            self._runtimes.pop(session_id, None)


session_manager = SessionManager()
