"""
Area Linting System

Provides lint rules and checks for area maintenance.
"""

import fnmatch
import re
import requests
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum
from shapely.geometry import shape, Point
from shapely import STRtree


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
    extra_data: Optional[dict] = None

    def to_dict(self):
        result = {
            'rule_id': self.rule.id,
            'rule_name': self.rule.name,
            'description': self.rule.description,
            'severity': self.rule.severity.value,
            'auto_fixable': self.rule.auto_fixable,
            'fix_action': self.rule.fix_action,
            'message': self.message,
            'current_value': self.current_value
        }
        if self.extra_data:
            result.update(self.extra_data)
        return result


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
    'url-alias-clash': LintRule(
        id='url-alias-clash',
        name='URL Alias Clash',
        description='Multiple areas share the same url_alias',
        severity=Severity.ERROR,
        auto_fixable=False
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
        self.results = []  # List of {area_id, area_name, area_type, is_deleted, country_id, country_name, issues: [...]}
        self.last_sync = None
        self.last_sync_cursor = None  # For incremental sync
        self.is_syncing = False
        self.sync_progress = {'current': 0, 'total': 0}
        self._country_index = None  # STRtree for country lookup
        self._country_geometries = []  # List of (area_id, area_name, geometry) tuples
    
    def clear(self):
        self.results = []
        self.last_sync = None
        self.last_sync_cursor = None
        self._country_index = None
        self._country_geometries = []
    
    def get_summary(self, rule_filter: Optional[str] = None, severity_filter: Optional[str] = None,
                    type_filter: Optional[str] = None, include_deleted: bool = False,
                    issues_only: bool = False, tag_filters: Optional[dict] = None,
                    country_id: Optional[str] = None) -> dict:
        """Get summary statistics."""
        # Filter results for summary (same logic as get_results)
        filtered_results = []
        
        for area_result in self.results:
            # Filter by deleted status
            if not include_deleted and area_result.get('is_deleted', False):
                continue
            
            # Filter by area type
            if type_filter and area_result.get('area_type') != type_filter:
                continue
            
            # Filter by country (only applies to non-country areas)
            if country_id and area_result.get('area_type') != 'country':
                if area_result.get('country_id') != country_id:
                    continue
            
            # Filter by tags
            if tag_filters:
                tags = area_result.get('tags', {})
                match = True
                for tag_name, tag_value in tag_filters.items():
                    area_tag_value = tags.get(tag_name)
                    if tag_value is None:
                        # Tag must exist (any value)
                        if area_tag_value is None:
                            match = False
                            break
                    else:
                        # Tag must match value (supports wildcards with *)
                        if area_tag_value is None:
                            match = False
                            break
                        area_tag_str = str(area_tag_value)
                        tag_value_str = str(tag_value)
                        
                        if '*' in tag_value_str:
                            # Wildcard matching using fnmatch
                            if not fnmatch.fnmatch(area_tag_str, tag_value_str):
                                match = False
                                break
                        else:
                            # Exact match
                            if area_tag_str != tag_value_str:
                                match = False
                                break
                if not match:
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
            
            # Create a copy with filtered issues for summary calculation
            filtered_results.append({
                **area_result,
                'issues': issues
            })
        
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
    
    def get_results(self, rule_filter: Optional[str] = None, severity_filter: Optional[str] = None, 
                    type_filter: Optional[str] = None, include_deleted: bool = False,
                    issues_only: bool = True, tag_filters: Optional[dict] = None,
                    country_id: Optional[str] = None) -> list[dict]:
        """Get filtered results.
        
        Args:
            tag_filters: Dict of {tag_name: tag_value} to filter by. 
                         Value can be None to match any value (tag exists),
                         or a string to match exact value.
            country_id: Filter non-country areas by their derived country_id.
        """
        filtered = []
        
        for area_result in self.results:
            # Filter by deleted status
            if not include_deleted and area_result.get('is_deleted', False):
                continue
            
            # Filter by area type
            if type_filter and area_result.get('area_type') != type_filter:
                continue
            
            # Filter by country (only applies to non-country areas)
            if country_id and area_result.get('area_type') != 'country':
                if area_result.get('country_id') != country_id:
                    continue
            
            # Filter by tags
            if tag_filters:
                tags = area_result.get('tags', {})
                match = True
                for tag_name, tag_value in tag_filters.items():
                    area_tag_value = tags.get(tag_name)
                    if tag_value is None:
                        # Tag must exist (any value)
                        if area_tag_value is None:
                            match = False
                            break
                    else:
                        # Tag must match value (supports wildcards with *)
                        if area_tag_value is None:
                            match = False
                            break
                        area_tag_str = str(area_tag_value)
                        tag_value_str = str(tag_value)
                        
                        if '*' in tag_value_str:
                            # Wildcard matching using fnmatch
                            if not fnmatch.fnmatch(area_tag_str, tag_value_str):
                                match = False
                                break
                        else:
                            # Exact match
                            if area_tag_str != tag_value_str:
                                match = False
                                break
                if not match:
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
                'country_id': area_result.get('country_id'),
                'country_name': area_result.get('country_name'),
                'tags': area_result.get('tags', {}),
                'issues': issues
            })
        
        return filtered
    
    def get_available_tags(self) -> list[str]:
        """Get list of all unique tag names across all areas."""
        # Tags to exclude from the list (system/internal tags)
        excluded_tags = {'geo_json'}
        
        all_tags = set()
        for area_result in self.results:
            tags = area_result.get('tags', {})
            for key in tags.keys():
                if key not in excluded_tags:
                    all_tags.add(key)
        return sorted(list(all_tags))
    
    def get_countries_with_communities(self) -> list[dict]:
        """Get list of countries that have at least one community in them.
        
        Returns:
            List of {id, name} dicts sorted alphabetically by name.
        """
        country_ids_with_communities = set()
        for area_result in self.results:
            if area_result.get('area_type') != 'country':
                country_id = area_result.get('country_id')
                if country_id:
                    country_ids_with_communities.add(country_id)
        
        # Get country names from cached results
        countries = []
        for area_result in self.results:
            if area_result.get('area_type') == 'country':
                if area_result['area_id'] in country_ids_with_communities:
                    countries.append({
                        'id': area_result['area_id'],
                        'name': area_result['area_name']
                    })
        
        return sorted(countries, key=lambda c: c['name'].lower())
    
    def build_country_index(self):
        """Build spatial index from country geometries for fast point-in-polygon lookups."""
        geometries = []
        self._country_geometries = []  # List of (area_id, area_name, geometry) tuples, indexed by position
        
        countries_with_geo = 0
        countries_total = 0
        
        for area_result in self.results:
            if area_result.get('area_type') != 'country':
                continue
            
            countries_total += 1
            geo_json = area_result.get('tags', {}).get('geo_json')
            if not geo_json:
                continue
            
            try:
                geom = shape(geo_json)
                if geom.is_valid:
                    countries_with_geo += 1
                    # Store by index position (STRtree.query returns indices in Shapely 2.x)
                    self._country_geometries.append((
                        area_result['area_id'],
                        area_result['area_name'],
                        geom
                    ))
                    geometries.append(geom)
            except Exception:
                # Skip invalid geometries
                continue
        
        print(f"Country index: {countries_with_geo}/{countries_total} countries have valid geo_json")
        
        if geometries:
            self._country_index = STRtree(geometries)
        else:
            self._country_index = None
    
    def derive_country_for_area(self, geo_json) -> tuple:
        """Find which country contains the centroid of the given geometry.
        
        Returns:
            Tuple of (country_id, country_name) or (None, 'Unknown') if not found.
        """
        if not self._country_index or not self._country_geometries or not geo_json:
            return (None, 'Unknown')
        
        try:
            geom = shape(geo_json)
            centroid = geom.centroid
            
            # Query the spatial index for candidate country indices
            # In Shapely 2.x, query() returns indices into the geometries list
            candidate_indices = self._country_index.query(centroid)
            
            for idx in candidate_indices:
                country_id, country_name, country_geom = self._country_geometries[idx]
                if country_geom.contains(centroid):
                    return (country_id, country_name)
            
            return (None, 'Unknown')
        except Exception:
            return (None, 'Unknown')
    
    def derive_countries_for_all_communities(self):
        """Derive country for all non-country areas based on their geo_json centroid."""
        self.build_country_index()
        
        countries_found = 0
        communities_processed = 0
        
        for area_result in self.results:
            if area_result.get('area_type') == 'country':
                # Countries don't have a country_id
                area_result['country_id'] = None
                area_result['country_name'] = None
                continue
            
            communities_processed += 1
            geo_json = area_result.get('tags', {}).get('geo_json')
            country_id, country_name = self.derive_country_for_area(geo_json)
            area_result['country_id'] = country_id
            area_result['country_name'] = country_name
            if country_id:
                countries_found += 1
        
        print(f"Country derivation: {countries_found}/{communities_processed} communities matched to countries")
    
    def detect_url_alias_clashes(self):
        """Detect areas with duplicate url_aliases and add lint issues."""
        # First, remove any existing url-alias-clash issues
        for area_result in self.results:
            area_result['issues'] = [
                issue for issue in area_result['issues']
                if issue['rule_id'] != 'url-alias-clash'
            ]
        
        url_alias_map = {}
        
        for area_result in self.results:
            if area_result.get('is_deleted', False):
                continue
            
            url_alias = area_result.get('tags', {}).get('url_alias')
            if url_alias:
                if url_alias not in url_alias_map:
                    url_alias_map[url_alias] = []
                url_alias_map[url_alias].append(area_result['area_id'])
        
        clashing_count = 0
        for url_alias, area_ids in url_alias_map.items():
            if len(area_ids) > 1:
                clashing_count += 1
                
                for current_area_id in area_ids:
                    clashing_area_ids = [aid for aid in area_ids if aid != current_area_id]
                    clashing_area_names = []
                    
                    for aid in clashing_area_ids:
                        for area_result in self.results:
                            if area_result['area_id'] == aid:
                                clashing_area_names.append(area_result['area_name'])
                                break
                    
                    clashing_issue = LintResult(
                        rule=LINT_RULES['url-alias-clash'],
                        message=f'Duplicate url_alias shared by {len(area_ids)} areas',
                        current_value=url_alias,
                        extra_data={
                            'clashing_area_ids': clashing_area_ids,
                            'clashing_area_names': clashing_area_names
                        }
                    ).to_dict()
                    
                    for area_result in self.results:
                        if area_result['area_id'] == current_area_id:
                            area_result['issues'].append(clashing_issue)
                            break
        
        print(f"URL alias clash detection: {clashing_count} clashes found")
    
    def update_area(self, area_id: str, area: dict):
        """Update lint results for a single area."""
        is_deleted = area.get('deleted_at') is not None
        
        # Only run lint checks on non-deleted areas
        if is_deleted:
            issues = []
        else:
            issues = lint_area_dict(area)
        
        area_type = area.get('tags', {}).get('type', 'unknown')
        
        # Derive country for non-country areas
        country_id = None
        country_name = None
        if area_type != 'country':
            geo_json = area.get('tags', {}).get('geo_json')
            country_id, country_name = self.derive_country_for_area(geo_json)
        
        area_result = {
            'area_id': str(area.get('id', area_id)),
            'area_name': area.get('tags', {}).get('name', 'Unknown'),
            'area_type': area_type,
            'is_deleted': is_deleted,
            'country_id': country_id,
            'country_name': country_name,
            'tags': area.get('tags', {}),  # Store full tags for search
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
