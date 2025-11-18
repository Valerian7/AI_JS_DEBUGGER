"""
RESTful API 路由
提供配置管理、系统状态等接口
"""

from flask import Blueprint, request, jsonify
from backend.config import config, BUILTIN_AI_PROVIDERS
import logging
import requests
from uuid import uuid4
from typing import Any, Dict, Optional
import json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__)
HOOKS_DIR = Path(__file__).parent.parent.parent / 'hooks'

@bp.route('/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    try:
        return jsonify({
            'success': True,
            'data': config.config
        })
    except Exception as e:
        logger.error(f'Failed to get config: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/config', methods=['POST'])
def update_config():
    """更新全局配置（目前支持 debug.* 参数）"""
    try:
        data = request.get_json() or {}
        dbg = data.get('debug') or {}
        allowed = {
            'auto_save': bool,
            'save_interval': int,
            'max_duration': int,
            'context_chars': int,
            'scope_max_depth': int,
            'scope_max_total_props': int
        }
        changed = False
        for k, caster in allowed.items():
            if k in dbg and dbg[k] is not None:
                try:
                    v = caster(dbg[k])
                except Exception:
                    v = dbg[k]
                config.set(f'debug.{k}', v)
                changed = True
        if changed:
            config.save_config()
        return jsonify({'success': True, 'message': 'Configuration updated'})
    except Exception as e:
        logger.error(f'Failed to update config: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/config/ai', methods=['GET'])
def get_ai_config():
    """获取 AI 配置"""
    try:
        provider = request.args.get('provider')
        ai_config = config.get_ai_config(provider)

        if 'api_key' in ai_config and ai_config['api_key']:
            key = ai_config['api_key']
            if len(key) > 8:
                ai_config['api_key'] = key[:4] + '****' + key[-4:]

        return jsonify({
            'success': True,
            'data': ai_config
        })
    except Exception as e:
        logger.error(f'Failed to get AI config: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/config/ai', methods=['POST'])
def update_ai_config():
    """更新 AI 配置"""
    try:
        data = request.get_json()

        provider = data.get('provider')
        api_key = data.get('api_key')
        model = data.get('model')
        analysis_model = data.get('analysis_model')
        base_url = data.get('base_url')
        available_models = data.get('available_models')
        proxy_id = data.get('proxy_id')
        extra = {}
        if 'vanchin_endpoint_id' in data:
            extra['vanchin_endpoint_id'] = data.get('vanchin_endpoint_id')

        if not provider:
            return jsonify({
                'success': False,
                'error': 'Provider is required'
            }), 400

        config.update_ai_config(
            provider,
            api_key,
            model,
            base_url,
            analysis_model,
            available_models=available_models,
            proxy_id=proxy_id,
            extra=extra
        )

        return jsonify({
            'success': True,
            'message': 'AI configuration updated successfully'
        })
    except Exception as e:
        logger.error(f'Failed to update AI config: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/config/browser', methods=['GET'])
def get_browser_config():
    """获取浏览器配置"""
    try:
        browser_config = config.get('browser', {})

        return jsonify({
            'success': True,
            'data': browser_config
        })
    except Exception as e:
        logger.error(f'Failed to get browser config: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/config/browser', methods=['POST'])
def update_browser_config():
    """更新浏览器配置"""
    try:
        data = request.get_json()

        for key, value in data.items():
            config.set(f'browser.{key}', value)

        config.save_config()

        return jsonify({
            'success': True,
            'message': 'Browser configuration updated successfully'
        })
    except Exception as e:
        logger.error(f'Failed to update browser config: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/hooks', methods=['GET'])
def get_hook_config():
    """获取 Hook 配置和可用脚本列表"""
    try:
        hook_cfg = config.get('hooks', {}) or {}
        enabled = bool(hook_cfg.get('enabled', True))
        enabled_files = hook_cfg.get('enabled_files') or []

        files = []
        try:
            HOOKS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        entries = []
        if HOOKS_DIR.exists():
            for file_path in sorted(HOOKS_DIR.glob('*.js')):
                stat = file_path.stat()
                entries.append({
                    'name': file_path.name,
                    'size': stat.st_size,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        enabled_set = set(enabled_files) if enabled_files else {item['name'] for item in entries}
        for item in entries:
            item['selected'] = item['name'] in enabled_set
        files = entries

        return jsonify({
            'success': True,
            'data': {
                'enabled': enabled,
                'files': files
            }
        })
    except Exception as e:
        logger.error(f'Failed to get hook config: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/hooks', methods=['POST'])
def update_hook_config_api():
    """更新 Hook 配置"""
    try:
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', True))
        files = data.get('enabled_files') or []
        if not isinstance(files, list):
            return jsonify({'success': False, 'error': 'enabled_files must be a list'}), 400

        valid_names = set()
        if HOOKS_DIR.exists():
            valid_names = {path.name for path in HOOKS_DIR.glob('*.js')}
        sanitized = []
        for name in files:
            if not isinstance(name, str):
                continue
            if valid_names and name not in valid_names:
                continue
            sanitized.append(name)

        deduped = []
        seen = set()
        for name in sanitized:
            if name in seen:
                continue
            seen.add(name)
            deduped.append(name)

        config.set('hooks.enabled', enabled)
        config.set('hooks.enabled_files', deduped)
        config.save_config()

        return jsonify({'success': True, 'message': 'Hook 配置已更新'})
    except Exception as e:
        logger.error(f'Failed to update hook config: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/config/prompts', methods=['GET'])
def get_prompts_config():
    """获取提示词配置"""
    try:
        prompts = config.get('prompts', {}) or {}
        return jsonify({'success': True, 'data': prompts})
    except Exception as e:
        logger.error(f'Failed to get prompts config: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/config/prompts', methods=['POST'])
def update_prompts_config():
    """更新提示词配置（断点调试与AI分析）"""
    try:
        data = request.get_json() or {}
        debug_prompt = data.get('debug')
        analysis_prompt = data.get('analysis')
        if debug_prompt is not None:
            config.set('prompts.debug', str(debug_prompt))
        if analysis_prompt is not None:
            config.set('prompts.analysis', str(analysis_prompt))
        config.save_config()
        return jsonify({'success': True, 'message': 'Prompts updated'})
    except Exception as e:
        logger.error(f'Failed to update prompts config: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/providers', methods=['GET'])
def get_providers():
    """获取所有可用的 AI 提供商列表"""
    try:
        providers = config.get('ai.providers', {})

        provider_list = []
        for name, cfg in providers.items():
            meta = BUILTIN_AI_PROVIDERS.get(name, {})
            provider_list.append({
                'name': name,
                'model': cfg.get('model'),
                'analysis_model': cfg.get('analysis_model') or cfg.get('model'),
                'configured': bool(cfg.get('api_key')),
                'custom': bool(cfg.get('custom')) or (name not in BUILTIN_AI_PROVIDERS),
                'display_name': cfg.get('display_name') or meta.get('display_name') or name,
                'logo': cfg.get('logo') or meta.get('logo'),
                'available_models': cfg.get('available_models') or meta.get('available_models') or [],
                'base_url': cfg.get('base_url') or meta.get('base_url'),
                'proxy_id': cfg.get('proxy_id'),
                'vanchin_endpoint_id': cfg.get('vanchin_endpoint_id') or ''
            })

        return jsonify({
            'success': True,
            'data': {
                'providers': provider_list,
                'default': config.get('ai.default_provider')
            }
        })
    except Exception as e:
        logger.error(f'Failed to get providers: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/ai/proxies', methods=['GET'])
def get_ai_proxies():
    """获取 AI 网络代理列表"""
    try:
        proxies = config.list_ai_proxies()
        proxy_list = []
        for pid, cfg in proxies.items():
            proxy_list.append({
                'id': pid,
                'name': cfg.get('name'),
                'type': cfg.get('type'),
                'host': cfg.get('host'),
                'port': cfg.get('port'),
                'username': cfg.get('username'),
                'use_auth': bool(cfg.get('username'))
            })
        return jsonify({'success': True, 'data': {'proxies': proxy_list}})
    except Exception as e:
        logger.error(f'Failed to list proxies: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/ai/proxies/<proxy_id>', methods=['GET'])
def get_ai_proxy_detail(proxy_id):
    """获取单个代理的完整配置"""
    try:
        proxy_cfg = config.get_ai_proxy(proxy_id)
        if not proxy_cfg:
            return jsonify({'success': False, 'error': 'Proxy not found'}), 404
        data = {
            'id': proxy_id,
            'name': proxy_cfg.get('name'),
            'type': proxy_cfg.get('type'),
            'host': proxy_cfg.get('host'),
            'port': proxy_cfg.get('port'),
            'username': proxy_cfg.get('username'),
            'has_password': bool(proxy_cfg.get('password'))
        }
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f'Failed to get proxy detail: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/ai/proxies', methods=['POST'])
def save_ai_proxy():
    """创建或更新 AI 代理"""
    try:
        data = request.get_json() or {}
        required = ['name', 'type', 'host', 'port']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        existing = config.get_ai_proxy(data.get('id')) if data.get('id') else None
        password = data.get('password') if 'password' in data else None
        if password is None and existing:
            password_value = existing.get('password', '')
        else:
            password_value = password or ''

        proxy_data = {
            'name': data['name'],
            'type': data['type'],
            'host': data['host'],
            'port': int(data['port']),
            'username': data.get('username') or '',
            'password': password_value
        }
        proxy_id = config.set_ai_proxy(data.get('id'), proxy_data)
        return jsonify({'success': True, 'data': {'id': proxy_id}})
    except Exception as e:
        logger.error(f'Failed to save proxy: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/ai/proxies/<proxy_id>', methods=['DELETE'])
def delete_ai_proxy(proxy_id):
    """删除 AI 网络代理"""
    try:
        config.delete_ai_proxy(proxy_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f'Failed to delete proxy: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

def build_proxy_dict(proxy_cfg: Optional[Dict[str, Any]]):
    if not proxy_cfg:
        return None
    auth = ''
    if proxy_cfg.get('username'):
        pwd = proxy_cfg.get('password', '')
        auth = f"{proxy_cfg['username']}:{pwd}@"
    proxy_url = f"{proxy_cfg.get('type', 'http')}://{auth}{proxy_cfg['host']}:{proxy_cfg['port']}"
    return {
        'http': proxy_url,
        'https': proxy_url
    }

@bp.route('/ai/proxies/test', methods=['POST'])
def test_ai_proxy():
    """测试代理可用性"""
    try:
        data = request.get_json() or {}
        if data.get('id'):
            proxy_cfg = config.get_ai_proxy(data['id'])
            if not proxy_cfg:
                return jsonify({'success': False, 'error': 'Proxy not found'}), 404
        else:
            required = ['name', 'type', 'host', 'port']
            for field in required:
                if not data.get(field):
                    return jsonify({'success': False, 'error': f'{field} is required'}), 400
            proxy_cfg = {
                'type': data['type'],
                'host': data['host'],
                'port': int(data['port']),
                'username': data.get('username') or '',
                'password': data.get('password') or ''
            }
        proxies = build_proxy_dict(proxy_cfg)
        try:
            resp = requests.get('https://www.baidu.com', proxies=proxies, timeout=8)
            if resp.status_code == 200:
                return jsonify({'success': True, 'message': '代理连接成功'})
            return jsonify({'success': False, 'error': f'HTTP {resp.status_code}'}), 400
        except requests.exceptions.ProxyError:
            return jsonify({'success': False, 'error': '代理认证失败或无法连接'}), 400
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': '代理连接超时'}), 400
    except Exception as e:
        logger.error(f'Failed to test proxy: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/test-ai', methods=['POST'])
def test_ai_connection():
    """测试 AI 连接"""
    try:
        data = request.get_json()
        provider = data.get('provider')
        override_model = data.get('model')
        override_key = data.get('api_key')
        override_base = data.get('base_url')
        override_proxy = data.get('proxy_id')

        if not provider:
            return jsonify({
                'success': False,
                'error': 'Provider is required'
            }), 400

        ai_config = config.get_ai_config(provider)
        api_key = (override_key or '').strip() or ai_config.get('api_key')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key not configured'
            }), 400

        model_name = (override_model or '').strip() or ai_config.get('model')
        if not model_name:
            return jsonify({
                'success': False,
                'error': 'Model is required'
            }), 400

        base_url = (override_base or '').strip() or ai_config.get('base_url')
        if not base_url:
            base_url = BUILTIN_AI_PROVIDERS.get(provider, {}).get('base_url')
        if not base_url:
            return jsonify({'success': False, 'error': 'Base URL 未配置'}), 400

        proxy_id = override_proxy or data.get('proxy_id') or ai_config.get('proxy_id')
        proxy_cfg = config.get_ai_proxy(proxy_id) if proxy_id else None
        proxies = build_proxy_dict(proxy_cfg)
        vanchin_endpoint = data.get('vanchin_endpoint_id') or ai_config.get('vanchin_endpoint_id')

        try:
            if provider == 'claude':
                endpoint = base_url.rstrip('/')
                url = f'{endpoint}/messages'
                payload = {
                    'model': model_name,
                    'max_tokens': 32,
                    'messages': [{'role': 'user', 'content': 'ping'}]
                }
                headers = {
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json'
                }
                resp = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=12)
            else:
                endpoint = base_url.rstrip('/')
                url = f'{endpoint}/chat/completions'
                payload = {
                    'model': model_name,
                    'messages': [{'role': 'user', 'content': 'ping'}]
                }
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                if provider == 'kat' and vanchin_endpoint:
                    headers['X-Vanchin-Endpoint-ID'] = vanchin_endpoint
                resp = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=12)

            if resp.status_code == 200:
                return jsonify({'success': True, 'message': '连接测试成功'})
            elif resp.status_code in (401, 403):
                return jsonify({'success': False, 'error': 'API Key 无效或权限不足'}), 400
            else:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text
                return jsonify({'success': False, 'error': f'API 返回状态 {resp.status_code}: {detail}'}), 400

        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': '连接超时，检查 API 地址或代理'}), 400
        except requests.exceptions.ProxyError:
            return jsonify({'success': False, 'error': '代理连接失败或认证错误'}), 400
        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'error': '无法连接到 API 服务器'}), 400
        except Exception as e:
            logger.error(f'AI test failed: {e}')
            return jsonify({'success': False, 'error': str(e)}), 400

    except Exception as e:
        logger.error(f'Failed to test AI connection: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/providers/add', methods=['POST'])
def add_custom_provider():
    """添加自定义 AI 提供商"""
    try:
        data = request.get_json()
        provider_name = data.get('name')
        provider_config = data.get('config', {})

        if not provider_name:
            return jsonify({
                'success': False,
                'error': 'Provider name is required'
            }), 400

        existing_providers = config.get('ai.providers', {})
        if provider_name in existing_providers:
            return jsonify({
                'success': False,
                'error': f'Provider {provider_name} already exists'
            }), 400

        config.set(f'ai.providers.{provider_name}', {
            'api_key': provider_config.get('api_key', ''),
            'model': provider_config.get('model', ''),
            'base_url': provider_config.get('base_url', ''),
            'custom': True  # Mark as custom provider
        })
        config.save_config()

        return jsonify({
            'success': True,
            'message': f'Provider {provider_name} added successfully'
        })
    except Exception as e:
        logger.error(f'Failed to add custom provider: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/config/ai/<provider>', methods=['DELETE'])
def delete_ai_provider(provider):
    """删除 AI 提供商（直接从配置中移除该提供商）"""
    try:
        config.delete_ai_config(provider)

        return jsonify({
            'success': True,
            'message': f'{provider} configuration deleted successfully'
        })
    except Exception as e:
        logger.error(f'Failed to delete AI provider config: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/config/ai/default', methods=['POST'])
def set_default_ai_provider():
    """设置默认 AI 提供商"""
    try:
        data = request.get_json()
        provider = data.get('provider')

        if not provider:
            return jsonify({
                'success': False,
                'error': 'Provider is required'
            }), 400

        providers = config.get('ai.providers', {})
        if provider not in providers:
            return jsonify({
                'success': False,
                'error': f'Provider {provider} not found'
            }), 404

        if not providers[provider].get('api_key'):
            return jsonify({
                'success': False,
                'error': f'Provider {provider} is not configured'
            }), 400

        config.set('ai.default_provider', provider)
        config.save_config()

        return jsonify({
            'success': True,
            'message': f'{provider} set as default provider'
        })
    except Exception as e:
        logger.error(f'Failed to set default AI provider: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
