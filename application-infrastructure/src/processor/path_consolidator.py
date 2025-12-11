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
import sys
from typing import List, Set, Dict
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.constants import (
    DIRECTORY_CONSOLIDATION_THRESHOLD,
    SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
    MAX_PATHS_PER_INVALIDATION,
    INDEX_FILE_PATTERNS
)
from common.logger import setup_logger

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


def consolidate_index_and_default_files(paths: Set[str]) -> Set[str]:
    """Consolidate index.* and default.* files to their parent directories.
    
    Rule: Any path ending with index.* or default.* is replaced with
    the parent directory followed by /*
    
    Args:
        paths: Set of file paths
        
    Returns:
        Set of paths with index/default files consolidated
    """
    consolidated = set()
    
    for path in paths:
        if is_index_or_default_file(path):
            parent = get_parent_directory(path)
            if parent == '/':
                consolidated.add('/*')
            else:
                consolidated.add(f"{parent}/*")
        else:
            consolidated.add(path)
    
    return consolidated


def consolidate_by_directory_threshold(paths: Set[str]) -> Set[str]:
    """Consolidate paths when more than 3 files share the same directory.
    
    Rule: When more than DIRECTORY_CONSOLIDATION_THRESHOLD (3) paths share
    the same parent directory, replace them with <parent>/*
    
    Args:
        paths: Set of file paths
        
    Returns:
        Set of paths with directory-level consolidation applied
    """
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
        if len(files) > DIRECTORY_CONSOLIDATION_THRESHOLD:
            # Consolidate to directory wildcard
            if parent == '/':
                consolidated.add('/*')
            else:
                consolidated.add(f"{parent}/*")
        else:
            # Keep individual files
            consolidated.update(files)
    
    # Add back existing wildcards
    consolidated.update(directory_wildcards)
    
    return consolidated


def consolidate_sibling_directories(paths: Set[str]) -> Set[str]:
    """Consolidate sibling directories when more than 10 would be invalidated.
    
    Rule: When more than SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD (10)
    sibling directories would be invalidated, consolidate to their parent.
    
    This function should be called iteratively until no more consolidation
    is possible.
    
    Args:
        paths: Set of paths (may include wildcards)
        
    Returns:
        Set of paths with sibling directory consolidation applied
    """
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
            # Consolidate to parent wildcard
            if parent == '/':
                consolidated.add('/*')
            else:
                consolidated.add(f"{parent}/*")
        else:
            # Keep individual sibling wildcards
            consolidated.update(siblings)
    
    # Add back non-wildcard paths
    consolidated.update(non_wildcards)
    
    return consolidated


def consolidate_paths_recursive(paths: Set[str]) -> Set[str]:
    """Recursively apply consolidation rules until no more consolidation is possible.
    
    This function applies directory threshold consolidation and sibling directory
    consolidation in a loop until the path set stabilizes.
    
    Args:
        paths: Set of paths to consolidate
        
    Returns:
        Fully consolidated set of paths
    """
    previous_size = len(paths)
    
    while True:
        # Apply directory threshold consolidation
        paths = consolidate_by_directory_threshold(paths)
        
        # Apply sibling directory consolidation
        paths = consolidate_sibling_directories(paths)
        
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


def consolidate_paths(paths: List[str]) -> List[List[str]]:
    """Consolidate invalidation paths using threshold-based algorithm.
    
    This is the main entry point for path consolidation. It applies all
    consolidation rules in sequence:
    
    1. Filter and clean input paths
    2. Consolidate index.* and default.* files to parent directories
    3. Consolidate directories with more than 3 files
    4. Consolidate sibling directories (more than 10)
    5. Recursively consolidate up to root if needed
    6. Split into multiple requests if exceeding 1000 paths
    
    Args:
        paths: List of object paths to invalidate (e.g., ['/prod/public/file.js'])
        
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
    
    logger.info(
        f"Starting path consolidation with {len(paths)} paths",
        extra={'extra_fields': {
            'original_path_count': len(paths)
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
    
    # Step 1: Consolidate index and default files
    path_set = consolidate_index_and_default_files(path_set)
    logger.debug(
        f"After index/default consolidation: {len(path_set)} paths",
        extra={'extra_fields': {
            'path_count': len(path_set)
        }}
    )
    
    # Step 2: Recursively apply directory and sibling consolidation
    path_set = consolidate_paths_recursive(path_set)
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
