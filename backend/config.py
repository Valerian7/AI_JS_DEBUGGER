"""
配置管理模块
负责加载和管理应用配置
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from copy import deepcopy
import uuid

logger = logging.getLogger(__name__)

BUILTIN_AI_PROVIDERS: Dict[str, Dict[str, Any]] = {
    'openai': {
        'display_name': 'OpenAI GPT',
        'api_key': '',
        'model': 'gpt-4o-mini',
        'analysis_model': 'gpt-4o',
        'base_url': 'https://api.openai.com/v1',
        'logo': '/static/assets/provider-logos/openai.svg',
        'available_models': ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini'],
        'proxy_id': None
    },
    'claude': {
        'display_name': 'Claude',
        'api_key': '',
        'model': 'claude-3-5-sonnet-latest',
        'analysis_model': 'claude-3-5-haiku-latest',
        'base_url': 'https://api.anthropic.com/v1',
        'logo': '/static/assets/provider-logos/claude.svg',
        'available_models': ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest', 'claude-3-opus'],
        'proxy_id': None
    },
    'deepseek': {
        'display_name': 'DeepSeek',
        'api_key': '',
        'model': 'deepseek-chat',
        'analysis_model': 'deepseek-reasoner',
        'base_url': 'https://api.deepseek.com/v1',
        'logo': '/static/assets/provider-logos/deepseek.svg',
        'available_models': ['deepseek-chat', 'deepseek-reasoner'],
        'proxy_id': None
    },
    'qwen': {
        'display_name': '通义千问',
        'api_key': '',
        'model': 'qwen-plus-2025-01-25',
        'analysis_model': 'qwen-long',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'logo': '/static/assets/provider-logos/qwen.svg',
        'available_models': ['qwen-plus-2025-01-25', 'qwen-turbo', 'qwen-long'],
        'proxy_id': None
    },
    'kimi': {
        'display_name': 'Kimi (Moonshot)',
        'api_key': '',
        'model': 'moonshot-v1-8k',
        'analysis_model': 'moonshot-v1-32k',
        'base_url': 'https://api.moonshot.cn/v1',
        'logo': '/static/assets/provider-logos/kimi.svg',
        'available_models': ['moonshot-v1-8k', 'moonshot-v1-32k'],
        'proxy_id': None
    },
    'glm': {
        'display_name': '智谱 GLM',
        'api_key': '',
        'model': 'glm-4-plus',
        'analysis_model': 'glm-4-air',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'logo': '/static/assets/provider-logos/glm.svg',
        'available_models': ['glm-4-plus', 'glm-4-air', 'glm-4-flash'],
        'proxy_id': None
    },
    'minimax': {
        'display_name': 'MiniMax',
        'api_key': '',
        'model': 'abab6.5-chat',
        'analysis_model': 'abab6.5s-chat',
        'base_url': 'https://api.minimax.chat/v1',
        'logo': '/static/assets/provider-logos/minimax.svg',
        'available_models': ['abab6.5-chat', 'abab6.5s-chat'],
        'proxy_id': None
    },
    'kat': {
        'display_name': '快手 KAT',
        'api_key': '',
        'model': 'kat-8k',
        'analysis_model': 'kat-32k',
        'base_url': 'https://api.kuaishou.com/kat/v1',
        'logo': '/static/assets/provider-logos/kat.svg',
        'available_models': ['kat-8k', 'kat-32k'],
        'proxy_id': None,
        'vanchin_endpoint_id': ''
    }
}

class Config:
    """配置管理类"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，默认为项目根目录的 config.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config.yaml'

        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}

        self.load_config()

    def load_config(self) -> None:
        """从 YAML 文件加载配置"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info(f'Configuration loaded from {self.config_path}')
            else:
                logger.warning(f'Configuration file not found: {self.config_path}')
                self.config = self.get_default_config()
                self.save_config()
        except Exception as e:
            logger.error(f'Failed to load configuration: {e}')
            self.config = self.get_default_config()
        finally:
            changed = False
            if self.ensure_builtin_providers():
                changed = True
            if self.ensure_hook_config():
                changed = True
            if changed:
                self.save_config()

    def save_config(self) -> None:
        """保存配置到 YAML 文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            logger.info(f'Configuration saved to {self.config_path}')
        except Exception as e:
            logger.error(f'Failed to save configuration: {e}')

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """返回默认配置"""
        providers = {name: deepcopy(meta) for name, meta in BUILTIN_AI_PROVIDERS.items()}
        return {
            'ai': {
                'default_provider': 'qwen',
                'providers': providers,
                'proxies': {
                    'default': None,
                    'items': {}
                }
            },
            'hooks': {
                'enabled': True,
                'enabled_files': []
            },
            'browser': {
                'default': 'chrome',
                'chrome_path': None,  # 自动检测
                'edge_path': None
            },
            'debug': {
                'auto_save': True,
                'save_interval': 300,  # 秒
                'log_level': 'INFO',
                'max_duration': 600,  # 最大调试时长（秒）
                'context_chars': 150,  # 上下文代码左右字符数
                'scope_max_depth': 2,  # 断点后递归获取对象属性深度
                'scope_max_total_props': 15  # 断点后递归获取对象属性总数量
            },
            'ui': {
                'theme': 'auto',  # auto, light, dark
                'language': 'zh'  # zh, en
            },
            'prompts': {
                'debug': """任务：你是一个JavaScript逆向分析专家，负责根据当前断点的调试信息分析加密相关代码并决定最优调试策略。

可选操作：
- step_into: 单步进入（进入函数内部）
- step_out: 单步跳出（跳出当前函数）
- step_over: 单步跳过（执行当前行，停在下一行）

分析重点：
1. 加密函数识别：
   - 函数名包含encrypt/decrypt/AES/RSA/DES/MD5/SHA/Hash/Crypto/签名/code等关键词
   - JavaScript特有加密：btoa/atob(Base64)、TextEncoder/TextDecoder、crypto.subtle等Web API
   - 位运算加密：XOR(^)、位移(<<,>>)、按位与(&)、按位或(|)等操作
2. 可疑函数调用：
   - 网络请求相关：fetch/XMLHttpRequest/axios/$.ajax/sendData*/getToken*/getSign*/request*
   - 数据处理相关：JSON.parse/stringify、URLSearchParams、FormData操作
3. 加密库识别：
   - 主流库：CryptoJS/WebCrypto/forge/jsencrypt/crypto-js/sjcl/noble-*
   - 自定义库：检测_加密函数命名模式、特定算法实现特征
4. 数据转换操作：
   - 编码转换：Base64/HEX/UTF-8/encodeURIComponent/escape
   - 字符串操作：toString/fromCharCode/charCodeAt/padStart/padEnd/split/join
   - 数组操作：TypedArray(Uint8Array等)、Array.from、map/reduce用于字节处理
5. 混淆代码识别：
   - 动态执行：eval/Function构造函数/setTimeout+字符串/new Function()
   - 字符串拼接：大量的字符串拼接、字符编码转换、数组join操作
   - 控制流扁平化：大型switch-case结构、状态机模式、大量条件判断
   - 变量混淆：单字符变量、数字变量名、无意义变量名
6. 可疑参数：IV/key/salt/mode/data/padding/secret/token/sign/signature等加密参数

精确决策规则：
   -step_over：首次遇到加密函数调用或eval/Function动态代码
   -step_over：在加密函数内部的非核心步骤或复杂混淆代码
   -step_out：嵌套超过3层或陷入重复循环时

输出格式（必须是有效的JSON）：
{
  "step_into": false,
  "step_out": false,
  "step_over": true,
  "reason": "简短说明原因"
}

注意：三个操作中只能有一个为 true""",
                'analysis': """任务：你是一个JavaScript逆向分析专家，负责分析调试数据，请根据调试过程中收集的信息，分析出以下内容

1. 加解密方法识别：
   - 识别所有加密/解密函数及其调用链
   - 分析加密算法类型（对称/非对称/哈希等）
   - 识别自定义加密算法和混淆技术

2. 密钥提取：
   - 提取所有加密密钥、IV、salt等参数
   - 分析密钥生成/派生逻辑
   - 识别密钥存储位置（本地存储/Cookie/内存）

3. 关键代码分析：
   - 提取核心加解密逻辑，简化并注释
   - 分析混淆代码的实际功能
   - 识别动态执行代码（eval/Function）的实际内容

4. 编写mitmproxy脚本：
   - 实现请求/响应数据的解密和加密
   - 处理特殊头部和参数
   - 确保脚本简洁高效

请保持分析简洁，不需要加固建议，专注于核心加解密逻辑和mitmproxy脚本实现。"""
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点分隔的嵌套键）

        Args:
            key: 配置键，如 'ai.default_provider'
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值（支持点分隔的嵌套键）

        Args:
            key: 配置键，如 'ai.default_provider'
            value: 配置值
        """
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def ensure_builtin_providers(self) -> bool:
        """确保配置中包含内置的 AI 提供商与代理结构"""
        changed = False
        ai_section = self.config.setdefault('ai', {})
        providers = ai_section.setdefault('providers', {})
        for name, meta in BUILTIN_AI_PROVIDERS.items():
            if name not in providers:
                providers[name] = deepcopy(meta)
                changed = True
            else:
                target = providers[name]
                for key, value in meta.items():
                    if key not in target:
                        target[key] = deepcopy(value)
                        changed = True
        proxies = ai_section.setdefault('proxies', {'default': None, 'items': {}})
        if 'default' not in proxies:
            proxies['default'] = None
            changed = True
        if 'items' not in proxies:
            proxies['items'] = {}
            changed = True
        return changed

    def ensure_hook_config(self) -> bool:
        """确保 Hook 配置存在"""
        changed = False
        hooks_cfg = self.config.setdefault('hooks', {})
        if 'enabled' not in hooks_cfg:
            hooks_cfg['enabled'] = True
            changed = True
        if hooks_cfg.get('enabled_files') is None:
            hooks_cfg['enabled_files'] = []
            changed = True
        if 'enabled_files' not in hooks_cfg:
            hooks_cfg['enabled_files'] = []
            changed = True
        return changed

    def get_ai_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 AI 提供商配置

        Args:
            provider: AI 提供商名称，默认使用配置中的默认提供商

        Returns:
            AI 提供商配置字典
        """
        if provider is None:
            provider = self.get('ai.default_provider', 'qwen')

        provider_config = self.get(f'ai.providers.{provider}', {})

        return {
            'provider': provider,
            **provider_config
        }

    def update_ai_config(self, provider: str, api_key: Optional[str] = None, model: Optional[str] = None,
                        base_url: Optional[str] = None, analysis_model: Optional[str] = None,
                        available_models: Optional[list] = None, proxy_id: Optional[str] = None,
                        extra: Optional[Dict[str, Any]] = None) -> None:
        """
        更新 AI 提供商配置

        Args:
            provider: AI 提供商名称
            api_key: API 密钥
            model: 模型名称
            base_url: API 基础 URL
        """
        if api_key:
            self.set(f'ai.providers.{provider}.api_key', api_key)

        if model:
            self.set(f'ai.providers.{provider}.model', model)

        if analysis_model:
            self.set(f'ai.providers.{provider}.analysis_model', analysis_model)

        if base_url is not None:
            self.set(f'ai.providers.{provider}.base_url', base_url)

        if available_models is not None:
            self.set(f'ai.providers.{provider}.available_models', available_models)

        if proxy_id is not None:
            self.set(f'ai.providers.{provider}.proxy_id', proxy_id or None)

        if extra:
            for key, value in extra.items():
                self.set(f'ai.providers.{provider}.{key}', value)

        self.save_config()

    def list_ai_proxies(self) -> Dict[str, Dict[str, Any]]:
        """返回所有 AI 网络代理"""
        return deepcopy(self.get('ai.proxies.items', {}) or {})

    def get_ai_proxy(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        proxies = self.get('ai.proxies.items', {}) or {}
        return proxies.get(proxy_id)

    def set_ai_proxy(self, proxy_id: Optional[str], data: Dict[str, Any]) -> str:
        proxies = self.get('ai.proxies.items', {}) or {}
        if not proxy_id:
            proxy_id = uuid.uuid4().hex
        proxies[proxy_id] = data
        self.set('ai.proxies.items', proxies)
        self.save_config()
        return proxy_id

    def delete_ai_proxy(self, proxy_id: str) -> None:
        proxies = self.get('ai.proxies.items', {}) or {}
        if proxy_id in proxies:
            del proxies[proxy_id]
            self.set('ai.proxies.items', proxies)
            providers = self.get('ai.providers', {}) or {}
            for name, cfg in providers.items():
                if cfg.get('proxy_id') == proxy_id:
                    cfg['proxy_id'] = None
            self.set('ai.providers', providers)
            self.save_config()

    def delete_ai_config(self, provider: str) -> None:
        """
        删除 AI 提供商（从配置中移除该提供商，而不是清空其字段）

        Args:
            provider: AI 提供商名称
        """
        providers = self.get('ai.providers', {}) or {}
        if provider in providers:
            del providers[provider]
            self.set('ai.providers', providers)

        current_default = self.get('ai.default_provider')
        if current_default == provider:
            new_default = None
            for name, cfg in providers.items():
                if cfg.get('api_key'):
                    new_default = name
                    break
            self.set('ai.default_provider', new_default)

        self.save_config()

config = Config()
