"""
报告管理服务
负责管理调试报告的存储、检索和删除
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ReportManager:
    """报告管理器"""

    def __init__(self, reports_dir: Optional[Path] = None):
        """
        初始化报告管理器

        Args:
            reports_dir: 报告存储目录，默认为项目根目录/result/report
        """
        if reports_dir is None:
            base_dir = Path(__file__).parent.parent.parent
            reports_dir = base_dir / 'result' / 'report'

        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.reports_dir / 'reports_metadata.json'
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """加载报告元数据"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {'reports': []}
        except Exception as e:
            logger.error(f'Failed to load metadata: {e}')
            return {'reports': []}

    def _save_metadata(self) -> None:
        """保存报告元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'Failed to save metadata: {e}')

    def list_reports(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        获取报告列表

        Args:
            limit: 每页数量
            offset: 偏移量

        Returns:
            报告列表和总数
        """
        try:
            reports = []

            for report_file in self.reports_dir.glob('*.md'):
                if report_file.name == 'reports_metadata.json':
                    continue

                report_info = self._get_report_info(report_file)
                if report_info:
                    reports.append(report_info)

            reports.sort(key=lambda x: x['created_at'], reverse=True)

            total = len(reports)
            paginated_reports = reports[offset:offset + limit]

            return {
                'reports': paginated_reports,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        except Exception as e:
            logger.error(f'Failed to list reports: {e}')
            return {'reports': [], 'total': 0, 'limit': limit, 'offset': offset}

    def _get_report_info(self, report_file: Path) -> Optional[Dict[str, Any]]:
        """
        获取报告信息

        Args:
            report_file: 报告文件路径

        Returns:
            报告信息字典
        """
        try:
            filename = report_file.stem

            parts = filename.split('-')
            if len(parts) >= 6:
                try:
                    year = int(parts[-6])
                    month = int(parts[-5])
                    day = int(parts[-4])
                    hour = int(parts[-3])
                    minute = int(parts[-2])
                    second = int(parts[-1])

                    created_at = datetime(year, month, day, hour, minute, second)
                except (ValueError, IndexError):
                    created_at = datetime.fromtimestamp(report_file.stat().st_mtime)
            else:
                created_at = datetime.fromtimestamp(report_file.stat().st_mtime)

            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
                preview = content[:200] if len(content) > 200 else content

            target_url = 'Unknown'
            lines = content.split('\n')
            for line in lines:
                line_lower = line.lower().replace(' ', '')
                if '目标url' in line_lower or 'targeturl' in line_lower:
                    if ':' in line:
                        target_url = line.split(':', 1)[1].strip()
                        if target_url and target_url != 'Unknown':
                            break

            return {
                'id': report_file.stem,
                'filename': report_file.name,
                'path': str(report_file),
                'created_at': created_at.isoformat(),
                'size': report_file.stat().st_size,
                'target_url': target_url,
                'preview': preview,
                'type': 'analysis' if 'analysis' in filename else 'debug_data'
            }
        except Exception as e:
            logger.error(f'Failed to get report info for {report_file}: {e}')
            return None

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        获取报告详情

        Args:
            report_id: 报告 ID（文件名不含扩展名）

        Returns:
            报告详情
        """
        try:
            report_file = self.reports_dir / f'{report_id}.md'

            if not report_file.exists():
                logger.warning(f'Report not found: {report_id}')
                return None

            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()

            report_info = self._get_report_info(report_file)
            if report_info:
                report_info['content'] = content

            return report_info
        except Exception as e:
            logger.error(f'Failed to get report {report_id}: {e}')
            return None

    def delete_report(self, report_id: str) -> bool:
        """
        删除报告

        Args:
            report_id: 报告 ID

        Returns:
            是否删除成功
        """
        try:
            report_file = self.reports_dir / f'{report_id}.md'

            if not report_file.exists():
                logger.warning(f'Report not found: {report_id}')
                return False

            report_file.unlink()
            logger.info(f'Report deleted: {report_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to delete report {report_id}: {e}')
            return False

    def search_reports(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索报告

        Args:
            query: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的报告列表
        """
        try:
            reports = []

            for report_file in self.reports_dir.glob('*.md'):
                if report_file.name == 'reports_metadata.json':
                    continue

                if query.lower() in report_file.name.lower():
                    report_info = self._get_report_info(report_file)
                    if report_info:
                        reports.append(report_info)
                    continue

                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            report_info = self._get_report_info(report_file)
                            if report_info:
                                reports.append(report_info)
                except:
                    pass

            return reports[:limit]
        except Exception as e:
            logger.error(f'Failed to search reports: {e}')
            return []

report_manager = ReportManager()
