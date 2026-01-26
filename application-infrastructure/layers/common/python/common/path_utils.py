"""Path utility functions for origin path pattern handling."""

from typing import Optional, Tuple, List


def calculate_path_depth(path: str) -> int:
    """
    Calculate the depth of a path by counting segments.
    
    Args:
        path: Path string (e.g., '/{stageId}/public' or '/prod/public')
    
    Returns:
        Number of path segments (e.g., 2 for '/{stageId}/public')
    
    Examples:
        >>> calculate_path_depth('/')
        0
        >>> calculate_path_depth('/public')
        1
        >>> calculate_path_depth('/{stageId}/public')
        2
        >>> calculate_path_depth('/prod/public/')
        2
    """
    # Remove leading/trailing slashes and split
    segments = [s for s in path.strip('/').split('/') if s]
    return len(segments)


def matches_pattern(event_path: str, pattern: str, stage_ids: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Check if an event path matches the origin path pattern.
    
    Args:
        event_path: S3 object key from event
        pattern: Origin path pattern (may contain {stageId})
        stage_ids: List of valid stage identifiers
    
    Returns:
        Tuple of (matches: bool, resolved_stage: str or None)
    
    Examples:
        >>> matches_pattern('/prod/public/file.html', '/{stageId}/public', ['prod', 'dev'])
        (True, 'prod')
        >>> matches_pattern('/public/file.html', '/public', ['prod'])
        (True, None)
        >>> matches_pattern('/dev/public/file.html', '/{stageId}/public', ['prod'])
        (False, None)
    """
    # If pattern has {stageId}, try to match with each stage identifier
    if '{stageId}' in pattern:
        for stage_id in stage_ids:
            resolved_pattern = pattern.replace('{stageId}', stage_id)
            if event_path.startswith(resolved_pattern + '/'):
                return True, stage_id
        return False, None
    else:
        # Pattern has no placeholder, direct match
        if event_path.startswith(pattern + '/'):
            return True, None
        return False, None


def derive_pattern_from_path(
    event_path: str,
    public_segment: str,
    prod_stages: List[str],
    non_prod_stages: List[str]
) -> str:
    """
    Derive origin path pattern from an event path containing public segment.
    
    Args:
        event_path: S3 object key
        public_segment: Public directory name (e.g., 'public')
        prod_stages: Production stage identifiers
        non_prod_stages: Non-production stage identifiers
    
    Returns:
        Derived pattern (e.g., '/{stageId}/public' or '/public')
    
    Examples:
        >>> derive_pattern_from_path('/prod/public/file.html', 'public', ['prod'], ['dev'])
        '/{stageId}/public'
        >>> derive_pattern_from_path('/public/file.html', 'public', ['prod'], ['dev'])
        '/public'
        >>> derive_pattern_from_path('/assets/file.html', 'public', ['prod'], ['dev'])
        ''
    """
    segments = event_path.strip('/').split('/')
    
    # Find public segment index
    try:
        public_index = segments.index(public_segment)
    except ValueError:
        return ''
    
    # Extract path up to and including public
    path_segments = segments[:public_index + 1]
    
    # Replace stage identifiers with {stageId}
    normalized_segments = []
    for segment in path_segments:
        if segment in prod_stages or segment in non_prod_stages:
            normalized_segments.append('{stageId}')
        else:
            normalized_segments.append(segment)
    
    return '/' + '/'.join(normalized_segments)


def extract_stage_from_path(event_path: str, pattern: str) -> str:
    """
    Extract stage identifier from event path using pattern.
    
    Args:
        event_path: S3 object key
        pattern: Origin path pattern with {stageId} placeholder
    
    Returns:
        Stage identifier or empty string if not found
    
    Examples:
        >>> extract_stage_from_path('/prod/public/file.html', '/{stageId}/public')
        'prod'
        >>> extract_stage_from_path('/public/file.html', '/public')
        ''
        >>> extract_stage_from_path('/prod/assets/file.html', '/{stageId}/public')
        ''
    """
    if '{stageId}' not in pattern:
        return ''
    
    # Split pattern and path into segments
    pattern_segments = pattern.strip('/').split('/')
    path_segments = event_path.strip('/').split('/')
    
    # Find {stageId} position in pattern
    try:
        stage_index = pattern_segments.index('{stageId}')
        if stage_index < len(path_segments):
            return path_segments[stage_index]
    except (ValueError, IndexError):
        pass
    
    return ''
