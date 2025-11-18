"""
AI 统一管理模块
使用 litellm 统一管理所有 AI 提供商
"""

import json
import logging
import os
from contextlib import contextmanager
from threading import RLock
from typing import Dict, Any, List, Optional
import litellm
from litellm import completion
from backend.config import config

logger = logging.getLogger(__name__)

litellm.set_verbose = False

class AIManager:
    """AI 管理器类，统一处理所有 AI 提供商的调用"""

    def __init__(self):
        """初始化 AI 管理器"""
        self.provider_mapping = {
            'qwen': 'qwen',
            'openai': 'openai',
            'gpt': 'openai',
            'deepseek': 'deepseek',
            'ernie': 'custom',  # 文心一言需要自定义处理
            'spark': 'custom'   # 讯飞星火需要自定义处理
        }
        self._proxy_lock = RLock()

    def get_model_name(self, provider: str, model: str) -> str:
        """
        获取 litellm 格式的模型名称

        Args:
            provider: AI 提供商
            model: 模型名称

        Returns:
            litellm 格式的模型名称
        """
        if provider == 'qwen':
            return model
        elif provider in ['openai', 'gpt']:
            return model
        elif provider == 'deepseek':
            return f"deepseek/{model}"
        else:
            return model

    def get_debug_instruction(self, debug_info: str, provider: Optional[str] = None,
                              context_history: Optional[List[str]] = None) -> str:
        """
        获取调试指令（决定下一步调试操作）

        Args:
            debug_info: 调试信息
            provider: AI 提供商，默认使用配置中的默认提供商
            context_history: 最近调试上下文列表（按时间顺序排列）

        Returns:
            调试指令: step_into, step_out, 或 step_over
        """
        try:
            ai_config = config.get_ai_config(provider)

            provider_name = ai_config.get('provider')
            api_key = ai_config.get('api_key')
            model = ai_config.get('model')
            base_url = ai_config.get('base_url')

            if not api_key:
                logger.error(f'API key not configured for provider: {provider_name}')
                return 'step_over'  # 默认操作

            compressed_info = " ".join(debug_info.split())

            system_prompt = self._get_debug_instruction_prompt()
            user_prompt = f'当前调试信息：{compressed_info}'

            messages: List[Dict[str, str]] = [
                {'role': 'system', 'content': system_prompt}
            ]

            if context_history:
                trimmed_history = context_history[-3:]
                context_text = "\n\n".join(
                    f"上下文 #{idx + 1}:\n{ctx}"
                    for idx, ctx in enumerate(trimmed_history)
                    if ctx
                )
                if context_text:
                    messages.append({
                        'role': 'user',
                        'content': f'以下为最近的调试上下文，请结合理解：\n{context_text}'
                    })

            messages.append({'role': 'user', 'content': user_prompt})

            model_name = self.get_model_name(provider_name, model)

            kwargs = {
                'model': model_name,
                'messages': messages,
                'api_key': api_key
            }

            if base_url:
                kwargs['api_base'] = base_url
                kwargs['custom_llm_provider'] = 'openai'

            logger.info(f'Calling AI model: {model_name}')

            with self._proxy_context(ai_config):
                response = completion(**kwargs)

            content = response.choices[0].message.content
            logger.info(f'AI response: {content}')

            try:
                result = json.loads(content)
            except Exception:
                lower = (content or '').lower()
                result = {
                    'step_into': 'step into' in lower or 'step_into' in lower,
                    'step_out': 'step out' in lower or 'step_out' in lower
                }

            if result.get('step_into'):
                return 'step_into'
            elif result.get('step_out'):
                return 'step_out'
            else:
                return 'step_over'

        except Exception as e:
            logger.error(f'Failed to get debug instruction: {e}')
            return 'step_over'  # 出错时默认使用 step_over

    def debugger_analyze(self, debug_data_path: str, provider: Optional[str] = None, target_url: Optional[str] = None) -> str:
        """
        分析调试数据并生成报告

        Args:
            debug_data_path: 调试数据文件路径
            provider: AI 提供商，默认使用配置中的默认提供商

        Returns:
            分析报告文件路径
        """
        try:
            ai_config = config.get_ai_config(provider)

            provider_name = ai_config.get('provider')
            api_key = ai_config.get('api_key')
            model = ai_config.get('model')
            analysis_model = ai_config.get('analysis_model') or model
            base_url = ai_config.get('base_url')

            if not api_key:
                logger.error(f'API key not configured for provider: {provider_name}')
                return ''

            with open(debug_data_path, 'r', encoding='utf-8') as f:
                debug_data = f.read()

            system_prompt = self._get_analyzer_prompt()

            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f'请分析以下调试数据：\n\n{debug_data}'}
            ]

            if provider_name == 'qwen':
                model_name = analysis_model if analysis_model else 'qwen-long'
            else:
                model_name = self.get_model_name(provider_name, analysis_model)

            kwargs = {
                'model': model_name,
                'messages': messages,
                'api_key': api_key
            }

            if base_url:
                kwargs['api_base'] = base_url
                kwargs['custom_llm_provider'] = 'openai'

            logger.info(f'Analyzing debug data with model: {model_name}')

            with self._proxy_context(ai_config):
                try:
                    response = completion(**kwargs)
                except Exception as e:
                    logger.warning(f'Long-context model failed ({model_name}), falling back to configured model: {e}')
                    model_name = self.get_model_name(provider_name, model)
                    kwargs['model'] = model_name
                    response = completion(**kwargs)

            analysis_result = response.choices[0].message.content

            import os
            from pathlib import Path
            from datetime import datetime

            report_dir = Path(debug_data_path).parent.parent / 'report'
            report_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            report_path = report_dir / f'analysis-{timestamp}.md'

            header = ''
            if target_url:
                header = f"目标 URL: {target_url}\n\n"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(header + analysis_result)

            logger.info(f'Analysis report saved to: {report_path}')

            return str(report_path)

        except Exception as e:
            logger.error(f'Failed to analyze debug data: {e}')
            return ''

    def test_connection(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        测试 AI 服务连接

        Args:
            provider: AI 提供商

        Returns:
            测试结果字典
        """
        try:
            ai_config = config.get_ai_config(provider)

            provider_name = ai_config.get('provider')
            api_key = ai_config.get('api_key')
            model = ai_config.get('model')
            base_url = ai_config.get('base_url')

            if not api_key:
                return {
                    'success': False,
                    'error': 'API key not configured'
                }

            messages = [
                {'role': 'user', 'content': 'Hello, this is a connection test.'}
            ]

            model_name = self.get_model_name(provider_name, model)

            kwargs = {
                'model': model_name,
                'messages': messages,
                'api_key': api_key,
                'max_tokens': 50
            }

            if base_url:
                kwargs['api_base'] = base_url
                kwargs['custom_llm_provider'] = 'openai'

            with self._proxy_context(ai_config):
                response = completion(**kwargs)

            return {
                'success': True,
                'provider': provider_name,
                'model': model,
                'response': response.choices[0].message.content[:100]
            }

        except Exception as e:
            logger.error(f'Connection test failed: {e}')
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def _get_debug_instruction_prompt() -> str:
        """获取调试指令提示词（仅从配置读取，不在此文件内置文案）"""
        p = config.get('prompts.debug', '')
        return p or ''

    @staticmethod
    def _get_analyzer_prompt() -> str:
        """获取分析器提示词（仅从配置读取，不在此文件内置文案）"""
        p = config.get('prompts.analysis', '')
        return p or ''

    def _resolve_proxy_cfg(self, ai_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        proxy_id = ai_config.get('proxy_id') or config.get('ai.proxies.default')
        if not proxy_id:
            return None
        return config.get_ai_proxy(proxy_id)

    @staticmethod
    def _build_proxy_url(proxy_cfg: Dict[str, Any]) -> Optional[str]:
        if not proxy_cfg:
            return None
        host = proxy_cfg.get('host')
        port = proxy_cfg.get('port')
        if not host or not port:
            return None
        scheme = (proxy_cfg.get('type') or 'http').lower()
        auth = ''
        username = proxy_cfg.get('username')
        if username:
            password = proxy_cfg.get('password', '')
            auth = f"{username}:{password}@" if password else f"{username}@"
        return f"{scheme}://{auth}{host}:{port}"

    @contextmanager
    def _proxy_context(self, ai_config: Dict[str, Any]):
        proxy_cfg = self._resolve_proxy_cfg(ai_config)
        proxy_url = self._build_proxy_url(proxy_cfg)
        if not proxy_url:
            yield None
            return

        env_keys = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']
        with self._proxy_lock:
            originals = {key: os.environ.get(key) for key in env_keys}
            try:
                for key in env_keys:
                    os.environ[key] = proxy_url
                yield proxy_url
            finally:
                for key, value in originals.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

ai_manager = AIManager()
