"""CloudFront invalidation path validation utilities."""

import re
import sys
import os
from typing import List, Tuple

# Import from Lambda layer
from common.logger import setup_logger

logger = setup_logger(__name__)


def validate_cloudfront_path(path: str) -> Tuple[bool, str]:
    """
    Validate a CloudFront invalidation path according to AWS requirements.
    
    CloudFront path requirements:
    1. Must start with /
    2. Can contain: a-z, A-Z, 0-9, -, _, ., /, *, ?
    3. Cannot contain: spaces, special characters like @, #, etc.
    4. Cannot be empty
    5. Cannot have double slashes
    6. Maximum length is around 8000 characters
    
    Args:
        path: The path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(path, str):
        return False, f"Path must be a string, got {type(path)}"
    
    if not path:
        return False, "Path is empty"
    
    if not path.startswith('/'):
        return False, "Path must start with /"
    
    # Check for double slashes
    if '//' in path:
        return False, "Path contains double slashes"
    
    # Check for invalid characters
    # CloudFront allows: alphanumeric, hyphens, underscores, dots, slashes, asterisks
    # Note: Removed question marks as they can cause issues in some cases
    valid_pattern = re.compile(r'^[a-zA-Z0-9\-_./\*]+$')
    if not valid_pattern.match(path):
        return False, f"Path contains invalid characters"
    
    # Check length (CloudFront has limits)
    if len(path) > 8000:
        return False, f"Path too long: {len(path)} characters"
    
    return True, "Valid"


def sanitize_path(path: str) -> str:
    """
    Sanitize a path to make it CloudFront-compatible.
    
    Args:
        path: The path to sanitize
        
    Returns:
        Sanitized path that should be valid for CloudFront
    """
    if not path:
        return "/"
    
    # Ensure it's a string
    path = str(path)
    
    # Ensure it starts with /
    if not path.startswith('/'):
        path = '/' + path
    
    # Remove double slashes
    while '//' in path:
        path = path.replace('//', '/')
    
    # Remove invalid characters (keep only allowed ones)
    # Allow: alphanumeric, hyphens, underscores, dots, slashes, asterisks
    sanitized = re.sub(r'[^a-zA-Z0-9\-_./\*]', '', path)
    
    # Ensure it still starts with / after sanitization
    if not sanitized.startswith('/'):
        sanitized = '/' + sanitized
    
    # Truncate if too long
    if len(sanitized) > 8000:
        sanitized = sanitized[:8000]
        # Ensure we don't cut in the middle of a path segment
        if not sanitized.endswith('/') and not sanitized.endswith('*'):
            last_slash = sanitized.rfind('/')
            if last_slash > 0:
                sanitized = sanitized[:last_slash + 1] + '*'
    
    return sanitized


def validate_and_sanitize_paths(paths: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate and sanitize a list of paths for CloudFront invalidation.
    
    Args:
        paths: List of paths to validate and sanitize
        
    Returns:
        Tuple of (valid_paths, error_messages)
    """
    valid_paths = []
    error_messages = []
    
    for i, path in enumerate(paths):
        # First try to sanitize the path
        try:
            sanitized_path = sanitize_path(path)
            
            # Then validate the sanitized path
            is_valid, error_msg = validate_cloudfront_path(sanitized_path)
            
            if is_valid:
                valid_paths.append(sanitized_path)
            else:
                error_msg = f"Path {i}: '{path}' -> '{sanitized_path}': {error_msg}"
                error_messages.append(error_msg)
                logger.warning(
                    f"Invalid path after sanitization: {error_msg}",
                    extra={'extra_fields': {
                        'original_path': path,
                        'sanitized_path': sanitized_path,
                        'validation_error': error_msg
                    }}
                )
        except Exception as e:
            error_msg = f"Path {i}: '{path}': Exception during sanitization: {str(e)}"
            error_messages.append(error_msg)
            logger.error(
                f"Exception during path sanitization: {error_msg}",
                extra={'extra_fields': {
                    'original_path': path,
                    'exception': str(e)
                }}
            )
    
    # Remove duplicates while preserving order
    seen = set()
    unique_valid_paths = []
    for path in valid_paths:
        if path not in seen:
            seen.add(path)
            unique_valid_paths.append(path)
    
    if len(unique_valid_paths) != len(valid_paths):
        logger.info(
            f"Removed {len(valid_paths) - len(unique_valid_paths)} duplicate paths",
            extra={'extra_fields': {
                'original_count': len(valid_paths),
                'unique_count': len(unique_valid_paths)
            }}
        )
    
    return unique_valid_paths, error_messages