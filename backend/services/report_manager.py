# -*- coding: utf-8 -*-
"""
Report Management Service
Responsible for storing, retrieving, and deleting debug reports.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ReportManager:
    """Report Manager"""

    def __init__(self, reports_dir: Optional[Path] = None):
        """
        Initialize Report Manager

        Args:
            reports_dir: Report storage directory, defaults to project_root/result/report
        """
        if reports_dir is None:
            base_dir = Path(__file__).parent.parent.parent
            reports_dir = base_dir / 'result' / 'report'

        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.reports_dir / 'reports_metadata.json'
        
        # Memory cache, stores report info dict, Key is filename (without extension)
        self.reports_cache: Dict[str, Dict[str, Any]] = {}
        self._init_cache()

    def _init_cache(self):
        """
        Initialize cache
        First try to load from metadata file, then sync with filesystem to handle new files or metadata loss.
        """
        # 1. Try to load from metadata file
        loaded_meta = self._load_metadata()
        for r in loaded_meta.get('reports', []):
            if 'id' in r:
                self.reports_cache[r['id']] = r
        
        # 2. Sync with filesystem (handle first run or metadata loss)
        self._sync_cache_with_filesystem()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load report metadata file"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {'reports': []}
        except Exception as e:
            logger.error(f'Failed to load metadata file: {e}')
            return {'reports': []}

    def _save_metadata(self) -> None:
        """
        Save report metadata to file
        Convert current memory cache to list, sort by creation time descending, and save.
        """
        try:
            # Convert cache to list for saving
            reports_list = list(self.reports_cache.values())
            # Sort by creation time descending
            reports_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            data = {'reports': reports_list}
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'Failed to save metadata: {e}')

    def _sync_cache_with_filesystem(self):
        """
        Sync cache with filesystem
        1. Found new file -> Parse and add to cache
        2. File deleted -> Remove from cache
        Updates cache when file modification time is newer than cache record.
        """
        try:
            current_files = set()
            cache_changed = False

            # Scan directory
            for report_file in self.reports_dir.glob('*.md'):
                if report_file.name == 'reports_metadata.json':
                    continue
                
                report_id = report_file.stem
                current_files.add(report_id)

                # If not in cache, update it
                if report_id not in self.reports_cache:
                    info = self._get_report_info(report_file)
                    if info:
                        self.reports_cache[report_id] = info
                        cache_changed = True

            # Check for deleted files
            cached_ids = list(self.reports_cache.keys())
            for rid in cached_ids:
                if rid not in current_files:
                    del self.reports_cache[rid]
                    cache_changed = True

            if cache_changed:
                self._save_metadata()

        except Exception as e:
            logger.error(f"Error syncing cache with filesystem: {e}")

    def list_reports(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get list of reports (with cache sync)

        Args:
            limit: Items per page
            offset: Offset

        Returns:
            List of reports and total count
        """
        try:
            # Sync quickly on every list request (mainly to capture newly generated files)
            # Since _sync_cache_with_filesystem only does I/O for new files, it is fast
            self._sync_cache_with_filesystem()

            reports = list(self.reports_cache.values())
            # Sort by creation time descending
            reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)

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
        Get report info (Optimized I/O)

        Args:
            report_file: Path to report file

        Returns:
            Report info dictionary
        """
        try:
            filename = report_file.stem
            stat = report_file.stat()

            # Try to parse time from filename
            parts = filename.split('-')
            created_at = None
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
                    pass
            
            if not created_at:
                created_at = datetime.fromtimestamp(stat.st_mtime)

            # Optimization: Only read file header (first 2KB) to get metadata and preview
            # Avoid reading entire large files
            preview = ""
            target_url = "Unknown"
            
            with open(report_file, 'r', encoding='utf-8') as f:
                head_content = f.read(2048)
                preview = head_content[:200].replace('\n', ' ')
                
                # Simple parsing attempt
                lines = head_content.split('\n')
                for line in lines:
                    line_lower = line.lower().replace(' ', '')
                    if '目标url' in line_lower or 'targeturl' in line_lower:
                        if ':' in line:
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                val = parts[1].strip()
                                if val and val.lower() != 'unknown':
                                    target_url = val
                                    break

            return {
                'id': report_file.stem,
                'filename': report_file.name,
                'path': str(report_file),
                'created_at': created_at.isoformat(),
                'size': stat.st_size,
                'target_url': target_url,
                'preview': preview,
                'type': 'analysis' if 'analysis' in filename else 'debug_data'
            }
        except Exception as e:
            logger.error(f'Failed to get report info for {report_file}: {e}')
            return None

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Get report details

        Args:
            report_id: Report ID (filename without extension)

        Returns:
            Report details
        """
        try:
            report_file = self.reports_dir / f'{report_id}.md'

            if not report_file.exists():
                logger.warning(f'Report not found: {report_id}')
                # If file doesn't exist but cache has it, clean cache
                if report_id in self.reports_cache:
                    del self.reports_cache[report_id]
                    self._save_metadata()
                return None

            # Read full content
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Prioritize metadata from cache
            report_info = self.reports_cache.get(report_id)
            if not report_info:
                report_info = self._get_report_info(report_file)

            if report_info:
                # Return a copy to avoid polluting cache
                info_copy = report_info.copy()
                info_copy['content'] = content
                return info_copy
            
            return {'content': content} # Fallback

        except Exception as e:
            logger.error(f'Failed to get report {report_id}: {e}')
            return None

    def delete_report(self, report_id: str) -> bool:
        """
        Delete report

        Args:
            report_id: Report ID

        Returns:
            True if deleted successfully
        """
        try:
            report_file = self.reports_dir / f'{report_id}.md'

            if not report_file.exists():
                logger.warning(f'Report not found: {report_id}')
                # If file doesn't exist but cache has it, clean cache
                if report_id in self.reports_cache:
                    del self.reports_cache[report_id]
                    self._save_metadata()
                return False

            report_file.unlink()
            
            # Update cache
            if report_id in self.reports_cache:
                del self.reports_cache[report_id]
                self._save_metadata()

            logger.info(f'Report deleted: {report_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to delete report {report_id}: {e}')
            return False

    def search_reports(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search reports

        Args:
            query: Search keyword
            limit: Max results

        Returns:
            List of matching reports
        """
        try:
            self._sync_cache_with_filesystem()
            
            results = []
            query_lower = query.lower()

            # 1. Prioritize cache search (filename, URL)
            for rid, info in self.reports_cache.items():
                if query_lower in info['filename'].lower() or \
                   query_lower in info.get('target_url', '').lower():
                    results.append(info)
            
            if len(results) >= limit:
                return results[:limit]

            # 2. If cache results are insufficient, continue scanning file content
            # Simple implementation: Scan file content to supplement results
            for rid, info in self.reports_cache.items():
                if info in results: # Already matched
                    continue 
                
                try:
                    # Only read file when needed
                    with open(info['path'], 'r', encoding='utf-8') as f:
                        # Memory optimization: Read simple full content here
                        content = f.read()
                        if query_lower in content.lower():
                            results.append(info)
                            if len(results) >= limit:
                                break
                except:
                    pass
            
            return results[:limit]
        except Exception as e:
            logger.error(f'Failed to search reports: {e}')
            return []

report_manager = ReportManager()
