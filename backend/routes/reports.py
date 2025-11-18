"""
报告管理路由
提供报告的增删改查接口
"""

from flask import Blueprint, request, jsonify, send_file
from backend.services.report_manager import report_manager
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('reports', __name__)

@bp.route('/list', methods=['GET'])
def list_reports():
    """获取报告列表"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        result = report_manager.list_reports(limit=limit, offset=offset)

        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f'Failed to list reports: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<report_id>', methods=['GET'])
def get_report(report_id):
    """获取报告详情"""
    try:
        report = report_manager.get_report(report_id)

        if report is None:
            return jsonify({
                'success': False,
                'error': 'Report not found'
            }), 404

        return jsonify({
            'success': True,
            'data': report
        })
    except Exception as e:
        logger.error(f'Failed to get report: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    """删除报告"""
    try:
        success = report_manager.delete_report(report_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Report not found or failed to delete'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Report deleted successfully'
        })
    except Exception as e:
        logger.error(f'Failed to delete report: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id):
    """下载报告"""
    try:
        report = report_manager.get_report(report_id)

        if report is None:
            return jsonify({
                'success': False,
                'error': 'Report not found'
            }), 404

        return send_file(
            report['path'],
            as_attachment=True,
            download_name=report['filename'],
            mimetype='text/markdown'
        )
    except Exception as e:
        logger.error(f'Failed to download report: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/search', methods=['GET'])
def search_reports():
    """搜索报告"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 50))

        if not query:
            return jsonify({
                'success': False,
                'error': 'Query parameter is required'
            }), 400

        reports = report_manager.search_reports(query=query, limit=limit)

        return jsonify({
            'success': True,
            'data': {
                'reports': reports,
                'total': len(reports),
                'query': query
            }
        })
    except Exception as e:
        logger.error(f'Failed to search reports: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
