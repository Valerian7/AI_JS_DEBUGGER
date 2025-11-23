"""
Hook 脚本管理器
用于加载和管理 hooks 文件夹中的所有 Hook 脚本
"""

import os
import glob
import logging
from typing import List, Dict
from pathlib import Path
from backend.config import config as backend_config

logger = logging.getLogger(__name__)


class HookManager:
    """Hook 脚本管理器"""

    def __init__(self, hooks_dir: str = None):
        """
        初始化 Hook 管理器

        Args:
            hooks_dir: hooks 文件夹路径，默认为项目根目录下的 hooks 文件夹
        """
        if hooks_dir is None:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            hooks_dir = project_root / "hooks"

        self.hooks_dir = Path(hooks_dir)
        self.hooks: Dict[str, str] = {}
        self._loaded_signature = None

    def load_all_hooks(self) -> Dict[str, str]:
        """
        加载 hooks 文件夹中的所有 .js 文件

        Returns:
            字典，key 为文件名，value 为脚本内容
        """
        if not self.hooks_dir.exists():
            logger.warning(f"Hooks directory does not exist: {self.hooks_dir}")
            self.hooks.clear()
            self._loaded_signature = None
            return self.hooks

        js_files = sorted(self.hooks_dir.glob("*.js"))
        signature = []
        for path in js_files:
            try:
                stat = path.stat()
                signature.append((path.name, stat.st_mtime))
            except OSError:
                continue

        if self._loaded_signature == signature and self.hooks:
            return self.hooks

        self._loaded_signature = signature
        self.hooks.clear()

        for js_file in js_files:
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.hooks[js_file.name] = content
                    logger.info(f"✓ Loaded hook script: {js_file.name} ({len(content)} chars)")
            except Exception as e:
                logger.error(f"✗ Failed to load hook script {js_file.name}: {e}")

        return self.hooks

    def get_combined_hook_script(self) -> str:
        """
        获取所有 Hook 脚本合并后的内容

        Returns:
            合并后的脚本字符串
        """
        self.load_all_hooks()

        active_names = self._get_active_hook_names()
        if not active_names:
            return ""

        combined = "\n\n// ==================== Hook Scripts Separator ====================\n\n".join(
            self.hooks[name] for name in active_names if name in self.hooks
        )

        return combined

    def get_hook_filenames(self) -> List[str]:
        """
        获取所有已加载的 Hook 文件名列表

        Returns:
            文件名列表
        """
        if not self.hooks:
            self.load_all_hooks()
        return list(self.hooks.keys())

    def _get_active_hook_names(self) -> List[str]:
        """根据配置返回应该启用的 Hook 文件列表"""
        hook_cfg = backend_config.get('hooks', {}) or {}
        if not hook_cfg.get('enabled', True):
            return []
        enabled_files = hook_cfg.get('enabled_files') or []
        if not enabled_files:
            return list(self.hooks.keys())
        seen = set()
        ordered = []
        for name in enabled_files:
            if name in self.hooks and name not in seen:
                ordered.append(name)
                seen.add(name)
        return ordered


_hook_manager = None


def get_hook_manager() -> HookManager:
    """获取 Hook 管理器单例"""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager
