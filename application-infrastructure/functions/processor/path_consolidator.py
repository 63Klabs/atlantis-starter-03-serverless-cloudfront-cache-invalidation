"""Path consolidation algorithm for CloudFront invalidations.

This module implements a threshold-based consolidation algorithm that reduces
the number of invalidation paths by replacing multiple individual paths with
directory-level wildcards. The algorithm follows these rules:

1. Index/Default Files: Paths ending with index.* or default.* are automatically
   consolidated to their parent directory (e.g., /dir/index.html -> /dir/*)

2. Directory Threshold: When more than 3 files in the same directory are
   invalidated, consolidate to the directory level (e.g., /dir/a, /dir/b,
   /dir/c, /dir/d -> /dir/*)

3. Sibling Directory Consolidation: When more than 10 sibling directories
   would be invalidated, consolidate to their parent directory

4. Root Consolidation: Consolidation can recurse up to the root (/*) as a
   terminal case

5. Request Splitting: If consolidated paths exceed 1000 items, split into
   multiple lists for separate invalidation requests
"""

import os
from typing import List, Set, Dict
from collections import defaultdict

# Import from Lambda layer
from common.constants import ( # pyright: ignore[reportMissingImports]
    DIRECTORY_CONSOLIDATION_THRESHOLD,
    SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
    MAX_PATHS_PER_INVALIDATION,
    INDEX_FILE_PATTERNS
)
from common.logger import setup_logger # pyright: ignore[reportMissingImports]

logger = setup_logger(__name__)


def is_index_or_default_file(path: str) -> bool:
    """Check if a path represents an index or default file.
    
    Args:
        path: File path to check
        
    Returns:
        True if the path ends with index.* or default.*, False otherwise
    """
    if not path:
        return False
    
    # Get the filename from the path
    filename = path.rstrip('/').split('/')[-1]
    
    # Check if filename starts with any index/default pattern
    return any(filename.startswith(pattern) for pattern in INDEX_FILE_PATTERNS)


def get_parent_directory(path: str) -> str:
    """Get the parent directory of a path.
    
    Args:
        path: File or directory path
        
    Returns:
        Parent directory path, or '/' if at root
    """
    if not path or path == '/':
        return '/'
    
    # Clean up the path first - remove double slashes and trailing slashes
    # Replace multiple slashes with single slash
    while '//' in path:
        path = path.replace('//', '/')
    
    # Remove trailing slash (but keep root slash)
    if len(path) > 1:
        path = path.rstrip('/')
    
    # Split and get parent
    parts = path.split('/')
    if len(parts) <= 2:  # ['', 'something'] or less
        return '/'
    
    # Return parent directory (ensure no trailing slash except for root)
    parent = '/'.join(parts[:-1])
    return parent if parent != '' else '/'


def consolidate_index_and_default_files(paths: Set[str], stop_level: int = None, root_path: str = '/') -> Set[str]:
    """Consolidate index.* and default.* files to their parent directories.
    
    Rule: Any path ending with index.* or default.* is replaced with
    the parent directory followed by /* unless stop level prevents it
    
    Args:
        paths: Set of file paths
        stop_level: Consolidation stop level (default: no limit)
        root_path: Root directory to measure depth from
        
    Returns:
        Set of paths with index/default files consolidated (respecting stop level)
    """
    if stop_level is None:
        from common.constants import CONSOLIDATION_STOP_LEVEL # pyright: ignore[reportMissingImports]
        stop_level = CONSOLIDATION_STOP_LEVEL
    
    consolidated = set()
    
    for path in paths:
        if is_index_or_default_file(path):
            parent = get_parent_directory(path)
            
            # Check if consolidation to parent is allowed by stop level
            parent_depth = calculate_path_depth(parent, root_path)
            
            if is_consolidation_allowed_at_depth(parent_depth, stop_level):
                if parent == '/':
                    consolidated.add('/*')
                else:
                    consolidated.add(f"{parent}/*")
            else:
                # Stop level prevents consolidation, keep original path
                consolidated.add(path)
                logger.debug(
                    f"Stop level {stop_level} prevents index/default consolidation at depth {parent_depth}: {path}",
                    extra={'extra_fields': {
                        'stop_level': stop_level,
                        'blocked_depth': parent_depth,
                        'original_path': path,
                        'would_consolidate_to': f"{parent}/*" if parent != '/' else '/*'
                    }}
                )
        else:
            consolidated.add(path)
    
    return consolidated


def consolidate_by_directory_threshold(paths: Set[str], directory_threshold: int = None, stop_level: int = None, root_path: str = '/') -> Set[str]:
    """Consolidate paths when more than threshold files share the same directory.
    
    Rule: When more than directory_threshold paths share the same parent directory,
    replace them with <parent>/* unless stop level prevents it
    
    Args:
        paths: Set of file paths
        directory_threshold: Threshold for directory consolidation (default: use global constant)
        stop_level: Consolidation stop level (default: use global constant)
        root_path: Root directory to measure depth from
        
    Returns:
        Set of paths with directory-level consolidation applied
    """
    if directory_threshold is None:
        directory_threshold = DIRECTORY_CONSOLIDATION_THRESHOLD
    if stop_level is None:
        from common.constants import CONSOLIDATION_STOP_LEVEL # pyright: ignore[reportMissingImports]
        stop_level = CONSOLIDATION_STOP_LEVEL
    
    # Group paths by parent directory
    directory_groups: Dict[str, List[str]] = defaultdict(list)
    directory_wildcards = set()
    
    for path in paths:
        # Skip paths that are already wildcards
        if path.endswith('/*'):
            directory_wildcards.add(path)
            continue
        
        parent = get_parent_directory(path)
        directory_groups[parent].append(path)
    
    # Consolidate directories with more than threshold files
    consolidated = set()
    
    for parent, files in directory_groups.items():
        if len(files) > directory_threshold:
            # Check if consolidation is allowed by stop level
            parent_depth = calculate_path_depth(parent, root_path)
            
            if is_consolidation_allowed_at_depth(parent_depth, stop_level):
                # Consolidate to directory wildcard
                if parent == '/':
                    consolidated.add('/*')
                else:
                    consolidated.add(f"{parent}/*")
                
                logger.debug(
                    f"Directory threshold consolidation: {len(files)} files in {parent} -> {parent}/*",
                    extra={'extra_fields': {
                        'directory_threshold': directory_threshold,
                        'file_count': len(files),
                        'parent_directory': parent,
                        'consolidated_to': f"{parent}/*" if parent != '/' else '/*'
                    }}
                )
            else:
                # Stop level prevents consolidation, keep individual files
                consolidated.update(files)
                logger.debug(
                    f"Stop level {stop_level} prevents directory consolidation at depth {parent_depth}: {parent}",
                    extra={'extra_fields': {
                        'stop_level': stop_level,
                        'blocked_depth': parent_depth,
                        'parent_directory': parent,
                        'file_count': len(files)
                    }}
                )
        else:
            # Keep individual files (below threshold)
            consolidated.update(files)
    
    # Add back existing wildcards
    consolidated.update(directory_wildcards)
    
    return consolidated


def consolidate_sibling_directories(paths: Set[str], stop_level: int = None, root_path: str = '/') -> Set[str]:
    """Consolidate sibling directories when more than 10 would be invalidated.
    
    Rule: When more than SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD (10)
    sibling directories would be invalidated, consolidate to their parent
    unless stop level prevents it.
    
    This function should be called iteratively until no more consolidation
    is possible.
    
    Args:
        paths: Set of paths (may include wildcards)
        stop_level: Consolidation stop level (default: use global constant)
        root_path: Root directory to measure depth from
        
    Returns:
        Set of paths with sibling directory consolidation applied
    """
    if stop_level is None:
        from common.constants import CONSOLIDATION_STOP_LEVEL # pyright: ignore[reportMissingImports]
        stop_level = CONSOLIDATION_STOP_LEVEL
    
    # Extract directory wildcards (paths ending with /*)
    wildcards = {p for p in paths if p.endswith('/*')}
    non_wildcards = paths - wildcards
    
    # Group wildcards by their parent directory
    parent_groups: Dict[str, List[str]] = defaultdict(list)
    
    for wildcard in wildcards:
        # Remove the /* suffix to get the directory
        directory = wildcard[:-2] if wildcard != '/*' else '/'
        parent = get_parent_directory(directory)
        parent_groups[parent].append(wildcard)
    
    # Consolidate parents with more than threshold siblings
    consolidated = set()
    
    for parent, siblings in parent_groups.items():
        if len(siblings) > SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD:
            # Check if consolidation is allowed by stop level
            parent_depth = calculate_path_depth(parent, root_path)
            
            if is_consolidation_allowed_at_depth(parent_depth, stop_level):
                # Consolidate to parent wildcard
                if parent == '/':
                    consolidated.add('/*')
                else:
                    consolidated.add(f"{parent}/*")
                
                logger.debug(
                    f"Sibling directory consolidation: {len(siblings)} siblings in {parent} -> {parent}/*",
                    extra={'extra_fields': {
                        'sibling_count': len(siblings),
                        'parent_directory': parent,
                        'consolidated_to': f"{parent}/*" if parent != '/' else '/*'
                    }}
                )
            else:
                # Stop level prevents consolidation, keep individual siblings
                consolidated.update(siblings)
                logger.debug(
                    f"Stop level {stop_level} prevents sibling consolidation at depth {parent_depth}: {parent}",
                    extra={'extra_fields': {
                        'stop_level': stop_level,
                        'blocked_depth': parent_depth,
                        'parent_directory': parent,
                        'sibling_count': len(siblings)
                    }}
                )
        else:
            # Keep individual sibling wildcards (below threshold)
            consolidated.update(siblings)
    
    # Add back non-wildcard paths
    consolidated.update(non_wildcards)
    
    return consolidated


def remove_redundant_subdirectories(paths: Set[str]) -> Set[str]:
    """Remove redundant subdirectory paths when parent directories have wildcards.
    
    Rule: When a higher-level directory is marked with a wildcard, remove all
    subdirectory paths that are already covered by the parent wildcard.
    
    For example:
    - Input: {'/stage/public/asdf/qwerty/*', '/stage/public/asdf/qwerty/e/*'}
    - Output: {'/stage/public/asdf/qwerty/*'}
    
    Args:
        paths: Set of paths (may include wildcards)
        
    Returns:
        Set of paths with redundant subdirectories removed
    """
    # Separate wildcard paths from non-wildcard paths
    wildcards = {p for p in paths if p.endswith('/*')}
    non_wildcards = paths - wildcards
    
    # For each wildcard, find any other wildcards that are subdirectories
    redundant_wildcards = set()
    
    for wildcard in wildcards:
        # Get the directory path (remove the /*)
        wildcard_dir = wildcard[:-2] if wildcard != '/*' else '/'
        
        # Check all other wildcards to see if they are subdirectories
        for other_wildcard in wildcards:
            if other_wildcard == wildcard:
                continue
                
            # Get the other directory path
            other_dir = other_wildcard[:-2] if other_wildcard != '/*' else '/'
            
            # Check if other_dir is a subdirectory of wildcard_dir
            if is_subdirectory(other_dir, wildcard_dir):
                redundant_wildcards.add(other_wildcard)
    
    # Remove redundant wildcards
    final_wildcards = wildcards - redundant_wildcards
    
    # Also check non-wildcard paths against wildcards
    redundant_non_wildcards = set()
    
    for non_wildcard in non_wildcards:
        for wildcard in final_wildcards:
            wildcard_dir = wildcard[:-2] if wildcard != '/*' else '/'
            
            # Check if the non-wildcard path is covered by this wildcard
            if is_path_covered_by_wildcard(non_wildcard, wildcard_dir):
                redundant_non_wildcards.add(non_wildcard)
                break
    
    # Remove redundant non-wildcards
    final_non_wildcards = non_wildcards - redundant_non_wildcards
    
    return final_wildcards | final_non_wildcards


def is_subdirectory(potential_subdir: str, parent_dir: str) -> bool:
    """Check if potential_subdir is a subdirectory of parent_dir.
    
    Args:
        potential_subdir: Path that might be a subdirectory
        parent_dir: Parent directory path
        
    Returns:
        True if potential_subdir is a subdirectory of parent_dir
    """
    if parent_dir == '/':
        # Everything is a subdirectory of root
        return potential_subdir != '/'
    
    # Normalize paths - ensure no trailing slashes except for root
    parent_normalized = parent_dir.rstrip('/')
    subdir_normalized = potential_subdir.rstrip('/')
    
    # Check if subdir starts with parent + '/'
    return (subdir_normalized.startswith(parent_normalized + '/') and 
            subdir_normalized != parent_normalized)


def is_path_covered_by_wildcard(path: str, wildcard_dir: str) -> bool:
    """Check if a path is covered by a wildcard directory.
    
    Args:
        path: File or directory path to check
        wildcard_dir: Directory that has a wildcard (without the /*)
        
    Returns:
        True if the path is covered by the wildcard directory
    """
    if wildcard_dir == '/':
        # Root wildcard covers everything
        return True
    
    # Normalize paths
    wildcard_normalized = wildcard_dir.rstrip('/')
    path_normalized = path.rstrip('/')
    
    # Path is covered if it starts with wildcard_dir + '/'
    return (path_normalized.startswith(wildcard_normalized + '/') or 
            path_normalized == wildcard_normalized)


def consolidate_paths_recursive(paths: Set[str], directory_threshold: int = None, stop_level: int = None, root_path: str = '/') -> Set[str]:
    """Recursively apply consolidation rules until no more consolidation is possible.
    
    This function applies directory threshold consolidation, sibling directory
    consolidation, and redundant subdirectory removal in a loop until the path 
    set stabilizes, respecting the stop level constraints.
    
    Args:
        paths: Set of paths to consolidate
        directory_threshold: Threshold for directory consolidation
        stop_level: Consolidation stop level
        root_path: Root directory to measure depth from
        
    Returns:
        Fully consolidated set of paths
    """
    previous_size = len(paths)
    
    while True:
        # Apply directory threshold consolidation
        paths = consolidate_by_directory_threshold(paths, directory_threshold, stop_level, root_path)
        
        # Apply sibling directory consolidation
        paths = consolidate_sibling_directories(paths, stop_level, root_path)
        
        # Remove redundant subdirectories
        paths = remove_redundant_subdirectories(paths)
        
        # Check if we've reached a stable state
        current_size = len(paths)
        if current_size >= previous_size:
            # No more consolidation possible
            break
        
        previous_size = current_size
    
    return paths


def split_paths_for_invalidation(paths: List[str]) -> List[List[str]]:
    """Split paths into chunks for CloudFront invalidation requests.
    
    CloudFront has a limit of 1000 paths per invalidation request.
    This function splits the path list into multiple lists if needed.
    
    Args:
        paths: List of consolidated paths
        
    Returns:
        List of path lists, each containing at most MAX_PATHS_PER_INVALIDATION items
    """
    if len(paths) <= MAX_PATHS_PER_INVALIDATION:
        return [paths]
    
    # Split into chunks
    chunks = []
    for i in range(0, len(paths), MAX_PATHS_PER_INVALIDATION):
        chunk = paths[i:i + MAX_PATHS_PER_INVALIDATION]
        chunks.append(chunk)
    
    return chunks


def calculate_path_depth(path: str, root_path: str = '/') -> int:
    """Calculate the depth of a path relative to the root directory.
    
    Args:
        path: The path to calculate depth for
        root_path: The root directory to measure from (default: '/')
        
    Returns:
        The depth of the path relative to the root directory
        
    Example:
        calculate_path_depth('/prod/public/dir/file.html', '/prod/public') -> 1
        calculate_path_depth('/prod/public/dir/subdir/file.html', '/prod/public') -> 2
    """
    if not path or not root_path:
        return 0
    
    # Normalize paths - remove trailing slashes except for root
    path_normalized = path.rstrip('/') if path != '/' else '/'
    root_normalized = root_path.rstrip('/') if root_path != '/' else '/'
    
    # If path is the same as root, depth is 0
    if path_normalized == root_normalized:
        return 0
    
    # If path doesn't start with root, it's not under the root
    if root_normalized == '/':
        # Special case for root - everything is under root
        if not path_normalized.startswith('/'):
            return 0
        # Count segments after root
        segments = [s for s in path_normalized.split('/') if s]
        return len(segments)
    else:
        # Check if path is under the root
        if not path_normalized.startswith(root_normalized + '/'):
            return 0
        # Get the relative part and count segments
        relative_part = path_normalized[len(root_normalized):].lstrip('/')
        if not relative_part:
            return 0
        segments = [s for s in relative_part.split('/') if s]
        return len(segments)


def is_consolidation_allowed_at_depth(depth: int, stop_level: int) -> bool:
    """Check if consolidation is allowed at the given depth.
    
    Args:
        depth: The depth from root directory (of the consolidation target)
        stop_level: The consolidation stop level
        
    Returns:
        True if consolidation is allowed, False otherwise
        
    Example:
        is_consolidation_allowed_at_depth(1, 2) -> False (depth 1 < stop level 2, so blocked)
        is_consolidation_allowed_at_depth(2, 2) -> True  (depth 2 >= stop level 2, so allowed)
        
    Note: Stop level 1 means allow all consolidation (backward compatibility)
          Stop level N prevents consolidation at depths 0 through N-1
    """
    if stop_level <= 1:
        # Stop level 1 or less means allow all consolidation (backward compatibility)
        return True
    return depth >= stop_level


def apply_stop_level_constraints(paths: Set[str], stop_level: int, root_path: str = '/') -> Set[str]:
    """Apply consolidation stop level constraints to path set.
    
    This function prevents consolidation from occurring at or above the stop level depth.
    It works by identifying paths that would violate the stop level and ensuring they
    remain unconsolidated.
    
    Args:
        paths: Set of paths to apply constraints to
        stop_level: The consolidation stop level
        root_path: The root directory to measure depth from
        
    Returns:
        Set of paths with stop level constraints applied
    """
    if stop_level <= 0:
        # Stop level 0 means consolidate everything to root
        return {'/*'}
    
    # Separate wildcards from regular paths
    wildcards = {p for p in paths if p.endswith('/*')}
    regular_paths = paths - wildcards
    
    # Check each wildcard to see if it violates stop level
    allowed_wildcards = set()
    blocked_wildcards = set()
    
    for wildcard in wildcards:
        # Get the directory path (remove the /*)
        if wildcard == '/*':
            dir_path = '/'
        else:
            dir_path = wildcard[:-2]
        
        # Calculate depth of the directory
        depth = calculate_path_depth(dir_path, root_path)
        
        if is_consolidation_allowed_at_depth(depth, stop_level):
            allowed_wildcards.add(wildcard)
        else:
            blocked_wildcards.add(wildcard)
            logger.debug(
                f"Stop level {stop_level} prevents consolidation at depth {depth}: {wildcard}",
                extra={'extra_fields': {
                    'stop_level': stop_level,
                    'blocked_depth': depth,
                    'blocked_wildcard': wildcard
                }}
            )
    
    # For blocked wildcards, we need to expand them back to individual paths
    # This is a simplified approach - in practice, the consolidation algorithm
    # should not create these wildcards in the first place
    result = allowed_wildcards | regular_paths
    
    # Add blocked wildcards back as-is for now
    # The actual prevention happens in the consolidation functions
    result.update(blocked_wildcards)
    
    return result


def consolidate_paths(paths: List[str], directory_threshold: int = None, stop_level: int = None) -> List[List[str]]:
    """Consolidate invalidation paths using threshold-based algorithm.
    
    This is the main entry point for path consolidation. It applies all
    consolidation rules in sequence:
    
    1. Filter and clean input paths
    2. Consolidate index.* and default.* files to parent directories
    3. Consolidate directories with more than threshold files
    4. Consolidate sibling directories (more than 10)
    5. Recursively consolidate up to root if needed (respecting stop level)
    6. Split into multiple requests if exceeding 1000 paths
    
    Args:
        paths: List of object paths to invalidate (e.g., ['/prod/public/file.js'])
        directory_threshold: Override for DIRECTORY_CONSOLIDATION_THRESHOLD (default: use global constant)
        stop_level: Consolidation stop level - depth from root where consolidation stops (default: use global constant)
        
    Returns:
        List of path lists, where each inner list contains at most 1000
        consolidated paths ready for CloudFront invalidation
        
    Example:
        Input: ['/prod/public/index.html', '/prod/public/about.html',
                '/prod/public/contact.html', '/prod/public/services.html']
        Output: [['/prod/public/*']]
    """
    if not paths:
        return [[]]
    
    # Use provided parameters or fall back to global constants
    if directory_threshold is None:
        directory_threshold = DIRECTORY_CONSOLIDATION_THRESHOLD
    if stop_level is None:
        from common.constants import CONSOLIDATION_STOP_LEVEL # pyright: ignore[reportMissingImports]
        stop_level = CONSOLIDATION_STOP_LEVEL
    
    logger.info(
        f"Starting path consolidation with {len(paths)} paths",
        extra={'extra_fields': {
            'original_path_count': len(paths),
            'directory_threshold': directory_threshold,
            'stop_level': stop_level
        }}
    )
    
    # Step 0: Clean and filter input paths
    cleaned_paths = []
    for path in paths:
        if not path or not isinstance(path, str):
            logger.warning(
                f"Skipping invalid path during consolidation: {repr(path)}",
                extra={'extra_fields': {'invalid_path': repr(path)}}
            )
            continue
        
        # Clean up double slashes and ensure proper format
        cleaned_path = path
        while '//' in cleaned_path:
            cleaned_path = cleaned_path.replace('//', '/')
        
        # Ensure path starts with /
        if not cleaned_path.startswith('/'):
            cleaned_path = '/' + cleaned_path
        
        cleaned_paths.append(cleaned_path)
    
    if not cleaned_paths:
        logger.warning("No valid paths remaining after cleaning")
        return [[]]
    
    logger.debug(
        f"After path cleaning: {len(cleaned_paths)} valid paths",
        extra={'extra_fields': {
            'original_count': len(paths),
            'cleaned_count': len(cleaned_paths)
        }}
    )
    
    # Convert to set for efficient operations
    path_set = set(cleaned_paths)
    
    # Determine root path for depth calculations (assume first path gives us the root structure)
    root_path = '/'
    if cleaned_paths:
        # Try to find a common root path pattern like /stage/public
        first_path = cleaned_paths[0]
        parts = first_path.split('/')
        if len(parts) >= 3 and parts[2] == 'public':
            # Pattern like /stage/public/... - use /stage/public as root
            root_path = f"/{parts[1]}/public"
        else:
            # For simple paths like /dir/file.html, use root /
            # But adjust stop level logic to be more permissive
            root_path = '/'
    
    # Handle special case: stop level 0 means consolidate everything to root
    if stop_level == 0:
        logger.info(
            f"Stop level 0: consolidating all paths to root wildcard",
            extra={'extra_fields': {
                'stop_level': stop_level,
                'original_count': len(cleaned_paths)
            }}
        )
        return [['/*']]
    
    # Step 1: Consolidate index and default files
    path_set = consolidate_index_and_default_files(path_set, stop_level, root_path)
    logger.debug(
        f"After index/default consolidation: {len(path_set)} paths",
        extra={'extra_fields': {
            'path_count': len(path_set)
        }}
    )
    
    # Step 2: Recursively apply directory and sibling consolidation
    path_set = consolidate_paths_recursive(path_set, directory_threshold, stop_level, root_path)
    logger.debug(
        f"After recursive consolidation: {len(path_set)} paths",
        extra={'extra_fields': {
            'path_count': len(path_set)
        }}
    )
    
    # Convert back to sorted list for consistent output
    consolidated_list = sorted(list(path_set))
    
    logger.info(
        f"Path consolidation complete: {len(paths)} -> {len(consolidated_list)} paths",
        extra={'extra_fields': {
            'original_count': len(paths),
            'consolidated_count': len(consolidated_list),
            'reduction_percent': round((1 - len(consolidated_list) / len(paths)) * 100, 2) if paths else 0
        }}
    )
    
    # Step 3: Split into chunks if needed
    chunks = split_paths_for_invalidation(consolidated_list)
    
    if len(chunks) > 1:
        logger.info(
            f"Split paths into {len(chunks)} invalidation requests",
            extra={'extra_fields': {
                'chunk_count': len(chunks),
                'paths_per_chunk': [len(chunk) for chunk in chunks]
            }}
        )
    
    return chunks