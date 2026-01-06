"""
Area Linting System

Provides lint rules and checks for area maintenance.
"""

import re
import requests
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum


class Severity(Enum):
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


@dataclass
class LintRule:
    id: str
    name: str
    description: str
    severity: Severity
    auto_fixable: bool
    fix_action: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d['severity'] = self.severity.value
        return d


@dataclass
class LintResult:
    rule: LintRule
    message: str
    current_value: Optional[str] = None

    def to_dict(self):
        return {
            'rule_id': self.rule.id,
            'rule_name': self.rule.name,
            'description': self.rule.description,
            'severity': self.rule.severity.value,
            'auto_fixable': self.rule.auto_fixable,
            'fix_action': self.rule.fix_action,
            'message': self.message,
            'current_value': self.current_value
        }


# Define lint rules
LINT_RULES = {
    'icon-legacy-url': LintRule(
        id='icon-legacy-url',
        name='Legacy Icon URL',
        description='Icon is not hosted on the standard static.btcmap.org location',
        severity=Severity.WARNING,
        auto_fixable=True,
        fix_action='migrate_icon'
    ),
    'icon-missing': LintRule(
        id='icon-missing',
        name='Missing Icon',
        description='No icon:square tag is set for this area',
        severity=Severity.ERROR,
        auto_fixable=False
    ),
    'verified-stale': LintRule(
        id='verified-stale',
        name='Verification Stale',
        description='Area has not been verified in over 12 months',
        severity=Severity.WARNING,
        auto_fixable=True,
        fix_action='bump_verified'
    ),
}


def get_area_id_from_area(area: dict) -> str:
    """Extract the numeric or string ID from an area object."""
    return str(area.get('id', ''))


def check_icon_legacy_url(area: dict) -> Optional[LintResult]:
    """Check if icon URL is in the standard format."""
    tags = area.get('tags', {})
    icon_url = tags.get('icon:square', '')
    
    if not icon_url:
        return None  # Handled by icon-missing rule
    
    area_id = get_area_id_from_area(area)
    
    # Expected pattern: https://static.btcmap.org/images/areas/{id}.{ext}
    expected_pattern = rf'^https://static\.btcmap\.org/images/areas/{re.escape(area_id)}\.\w+$'
    
    if not re.match(expected_pattern, icon_url):
        return LintResult(
            rule=LINT_RULES['icon-legacy-url'],
            message=f'Icon URL does not match expected format',
            current_value=icon_url
        )
    
    return None


def check_icon_missing(area: dict) -> Optional[LintResult]:
    """Check if icon:square tag is missing."""
    tags = area.get('tags', {})
    icon_url = tags.get('icon:square', '')
    
    if not icon_url or icon_url == 'pending-upload':
        return LintResult(
            rule=LINT_RULES['icon-missing'],
            message='No icon is set for this area',
            current_value=None
        )
    
    return None


def check_verified_stale(area: dict) -> Optional[LintResult]:
    """Check if area verification is older than 12 months."""
    tags = area.get('tags', {})
    
    # Check verified:date tag first
    verified_date_str = tags.get('verified:date', '')
    
    if verified_date_str:
        try:
            verified_date = datetime.strptime(verified_date_str, '%Y-%m-%d')
        except ValueError:
            try:
                verified_date = datetime.fromisoformat(verified_date_str.replace('Z', '+00:00'))
            except ValueError:
                verified_date = None
    else:
        # Fall back to updated_at
        updated_at_str = area.get('updated_at', '')
        if updated_at_str:
            try:
                verified_date = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            except ValueError:
                verified_date = None
        else:
            verified_date = None
    
    if verified_date is None:
        return LintResult(
            rule=LINT_RULES['verified-stale'],
            message='No verification date found',
            current_value=None
        )
    
    # Remove timezone info for comparison if present
    if hasattr(verified_date, 'tzinfo') and verified_date.tzinfo is not None:
        verified_date = verified_date.replace(tzinfo=None)
    
    twelve_months_ago = datetime.now() - timedelta(days=365)
    
    if verified_date < twelve_months_ago:
        return LintResult(
            rule=LINT_RULES['verified-stale'],
            message=f'Last verified {verified_date.strftime("%Y-%m-%d")}, over 12 months ago',
            current_value=verified_date_str or area.get('updated_at', '')
        )
    
    return None


def lint_area(area: dict) -> list[LintResult]:
    """Run all lint checks on an area and return results."""
    results = []
    
    # Run all check functions
    checks = [
        check_icon_missing,
        check_icon_legacy_url,
        check_verified_stale,
    ]
    
    for check_fn in checks:
        result = check_fn(area)
        if result is not None:
            results.append(result)
    
    return results


def lint_area_dict(area: dict) -> list[dict]:
    """Run lint checks and return results as dictionaries."""
    results = lint_area(area)
    return [r.to_dict() for r in results]


# ============================================
# Auto-fix Functions
# ============================================

def fix_migrate_icon(area_id: str, rpc_call_fn, get_area_fn) -> dict:
    """
    Migrate an area's icon from legacy URL to standard format.
    
    Args:
        area_id: The area ID
        rpc_call_fn: Function to make RPC calls
        get_area_fn: Function to get area by ID
    
    Returns:
        dict with 'success' and optional 'error' keys
    """
    try:
        # Get the area
        area = get_area_fn(area_id)
        if not area:
            return {'success': False, 'error': 'Area not found'}
        
        icon_url = area.get('tags', {}).get('icon:square', '')
        if not icon_url:
            return {'success': False, 'error': 'No icon URL to migrate'}
        
        # Check if already in correct format
        numeric_id = str(area.get('id', ''))
        expected_pattern = rf'^https://static\.btcmap\.org/images/areas/{re.escape(numeric_id)}\.\w+$'
        if re.match(expected_pattern, icon_url):
            return {'success': True, 'message': 'Icon already in correct format'}
        
        # Download the image
        response = requests.get(icon_url, timeout=30)
        response.raise_for_status()
        
        # Determine extension from content-type
        content_type = response.headers.get('Content-Type', '')
        ext_map = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/webp': 'webp',
            'image/gif': 'gif',
        }
        ext = ext_map.get(content_type.split(';')[0].strip(), 'png')
        
        # Convert to base64
        import base64
        icon_base64 = base64.b64encode(response.content).decode('utf-8')
        
        # Call set_area_icon RPC
        result = rpc_call_fn('set_area_icon', {
            'id': area_id,
            'icon_base64': icon_base64,
            'icon_ext': ext
        })
        
        if 'error' in result:
            return {'success': False, 'error': result['error'].get('message', 'RPC error')}
        
        return {'success': True, 'message': 'Icon migrated successfully'}
    
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Failed to download icon: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


def fix_bump_verified(area_id: str, rpc_call_fn) -> dict:
    """
    Bump the verified:date tag to today's date.
    
    Args:
        area_id: The area ID
        rpc_call_fn: Function to make RPC calls
    
    Returns:
        dict with 'success' and optional 'error' keys
    """
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        result = rpc_call_fn('set_area_tag', {
            'id': area_id,
            'name': 'verified:date',
            'value': today
        })
        
        if 'error' in result:
            return {'success': False, 'error': result['error'].get('message', 'RPC error')}
        
        return {'success': True, 'message': f'Verified date set to {today}'}
    
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


# Map fix actions to functions
FIX_ACTIONS = {
    'migrate_icon': fix_migrate_icon,
    'bump_verified': fix_bump_verified,
}


# ============================================
# Global Lint Cache
# ============================================

class LintCache:
    """In-memory cache for global lint results."""
    
    def __init__(self):
        self.results = []  # List of {area_id, area_name, area_type, is_deleted, issues: [...]}
        self.last_sync = None
        self.last_sync_cursor = None  # For incremental sync
        self.is_syncing = False
        self.sync_progress = {'current': 0, 'total': 0}
    
    def clear(self):
        self.results = []
        self.last_sync = None
        self.last_sync_cursor = None
    
    def get_summary(self, type_filter: str = None, include_deleted: bool = False) -> dict:
        """Get summary statistics."""
        # Filter results for summary
        filtered_results = self.results
        if type_filter:
            filtered_results = [r for r in filtered_results if r['area_type'] == type_filter]
        if not include_deleted:
            filtered_results = [r for r in filtered_results if not r.get('is_deleted', False)]
        
        areas_with_issues = len([r for r in filtered_results if r['issues']])
        total_issues = sum(len(r['issues']) for r in filtered_results)
        
        issues_by_rule = {}
        issues_by_severity = {'error': 0, 'warning': 0, 'info': 0}
        areas_by_type = {}
        
        for area_result in filtered_results:
            # Count by type
            area_type = area_result.get('area_type', 'unknown')
            areas_by_type[area_type] = areas_by_type.get(area_type, 0) + 1
            
            for issue in area_result['issues']:
                rule_id = issue['rule_id']
                issues_by_rule[rule_id] = issues_by_rule.get(rule_id, 0) + 1
                issues_by_severity[issue['severity']] += 1
        
        # Count deleted separately
        deleted_count = len([r for r in self.results if r.get('is_deleted', False)])
        
        return {
            'total_areas': len(filtered_results),
            'total_all_areas': len(self.results),
            'deleted_areas': deleted_count,
            'areas_with_issues': areas_with_issues,
            'total_issues': total_issues,
            'issues_by_rule': issues_by_rule,
            'issues_by_severity': issues_by_severity,
            'areas_by_type': areas_by_type,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'is_syncing': self.is_syncing,
            'sync_progress': self.sync_progress
        }
    
    def get_results(self, rule_filter: str = None, severity_filter: str = None, 
                    type_filter: str = None, include_deleted: bool = False,
                    issues_only: bool = True) -> list[dict]:
        """Get filtered results."""
        filtered = []
        
        for area_result in self.results:
            # Filter by deleted status
            if not include_deleted and area_result.get('is_deleted', False):
                continue
            
            # Filter by area type
            if type_filter and area_result.get('area_type') != type_filter:
                continue
            
            issues = area_result['issues']
            
            # Filter issues
            if rule_filter:
                issues = [i for i in issues if i['rule_id'] == rule_filter]
            if severity_filter:
                issues = [i for i in issues if i['severity'] == severity_filter]
            
            # Skip areas with no matching issues if issues_only
            if issues_only and not issues:
                continue
            
            filtered.append({
                'area_id': area_result['area_id'],
                'area_name': area_result['area_name'],
                'area_type': area_result['area_type'],
                'is_deleted': area_result.get('is_deleted', False),
                'issues': issues
            })
        
        return filtered
    
    def update_area(self, area_id: str, area: dict):
        """Update lint results for a single area."""
        is_deleted = area.get('deleted_at') is not None
        
        # Only run lint checks on non-deleted areas
        if is_deleted:
            issues = []
        else:
            issues = lint_area_dict(area)
        
        area_result = {
            'area_id': str(area.get('id', area_id)),
            'area_name': area.get('tags', {}).get('name', 'Unknown'),
            'area_type': area.get('tags', {}).get('type', 'unknown'),
            'is_deleted': is_deleted,
            'issues': issues
        }
        
        # Update or add
        for i, r in enumerate(self.results):
            if r['area_id'] == area_result['area_id']:
                self.results[i] = area_result
                return
        
        self.results.append(area_result)


# Global cache instance
lint_cache = LintCache()
