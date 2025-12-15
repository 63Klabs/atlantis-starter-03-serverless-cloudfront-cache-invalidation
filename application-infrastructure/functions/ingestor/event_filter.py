"""S3 event filtering module for validating events based on StageId and path patterns."""

from typing import Tuple
import os

from common.constants import PRODUCTION_STAGE_PREFIXES, PUBLIC_PATH_SEGMENT  # pyright: ignore[reportMissingImports]
from common.logger import setup_logger # pyright: ignore[reportMissingImports]


def is_production_stage(stage_id: str) -> bool:
    """Check if a StageId represents a production environment.
    
    Production environments are identified by StageIds starting with 'p', 's', or 'b'
    (case-insensitive).
    
    Args:
        stage_id: The StageId to validate
        
    Returns:
        True if the StageId starts with a production prefix, False otherwise
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 4: Production StageId filter acceptance**
    **Feature: multi-bucket-cloudfront-invalidation, Property 5: Non-production StageId filter rejection**
    """
    if not stage_id:
        return False
    
    # Check if the first character (case-insensitive) matches any production prefix
    first_char = stage_id[0].lower()
    return first_char in PRODUCTION_STAGE_PREFIXES


def matches_public_path_pattern(object_key: str) -> bool:
    """Check if an object key matches the public path pattern.
    
    The pattern is: /<StageId>/public/*
    This means the path must have at least 3 segments, with 'public' as the second segment.
    
    Args:
        object_key: S3 object key path
        
    Returns:
        True if the path matches the pattern, False otherwise
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 6: Public path pattern acceptance**
    **Feature: multi-bucket-cloudfront-invalidation, Property 7: Non-public path pattern rejection**
    """
    if not object_key:
        return False
    
    # Split the path and remove empty segments
    parts = object_key.lstrip('/').split('/')
    non_empty_parts = [p for p in parts if p]
    
    # Must have at least 3 parts: stageId, 'public', and at least one file/folder
    if len(non_empty_parts) < 3:
        return False
    
    # Second segment (index 1) must be 'public'
    return non_empty_parts[1] == PUBLIC_PATH_SEGMENT


def should_process_event(stage_id: str, object_key: str) -> Tuple[bool, str]:
    """Determine if an S3 event should be processed based on filtering rules.
    
    An event should be processed if:
    1. The StageId represents a production environment (p*, s*, b*)
    2. The object key matches the public path pattern (/<StageId>/public/*)
    
    Args:
        stage_id: The extracted StageId
        object_key: The S3 object key
        
    Returns:
        Tuple of (should_process: bool, reason: str)
        - should_process: True if event passes all filters
        - reason: Explanation of the decision (for logging)
    """
    logger = setup_logger(__name__)
    
    # DEBUG: Log filtering inputs
    logger.info(
        "Event filtering analysis DEBUG",
        extra={'extra_fields': {
            'inputStageId': stage_id,
            'inputObjectKey': object_key,
            'stageIdType': type(stage_id).__name__,
            'objectKeyType': type(object_key).__name__,
            'productionPrefixes': PRODUCTION_STAGE_PREFIXES,
            'publicPathSegment': PUBLIC_PATH_SEGMENT
        }}
    )
    
    # Check production stage filter
    is_prod = is_production_stage(stage_id)
    logger.info(
        "Production stage check DEBUG",
        extra={'extra_fields': {
            'stageId': stage_id,
            'isProductionStage': is_prod,
            'firstChar': stage_id[0].lower() if stage_id else None,
            'matchesProductionPrefix': stage_id[0].lower() in PRODUCTION_STAGE_PREFIXES if stage_id else False
        }}
    )
    
    if not is_prod:
        reason = f"StageId '{stage_id}' is not a production environment (must start with p, s, or b)"
        logger.info(
            "Event filtered: non-production stage DEBUG",
            extra={'extra_fields': {
                'filterReason': reason,
                'stageId': stage_id
            }}
        )
        return False, reason
    
    # Check public path pattern
    matches_public = matches_public_path_pattern(object_key)
    logger.info(
        "Public path pattern check DEBUG",
        extra={'extra_fields': {
            'objectKey': object_key,
            'matchesPublicPattern': matches_public,
            'pathParts': object_key.lstrip('/').split('/') if object_key else [],
            'hasPublicSegment': 'public' in object_key.split('/') if object_key else False
        }}
    )
    
    if not matches_public:
        reason = f"Object key '{object_key}' does not match public path pattern (/<StageId>/public/*)"
        logger.info(
            "Event filtered: non-public path DEBUG",
            extra={'extra_fields': {
                'filterReason': reason,
                'objectKey': object_key
            }}
        )
        return False, reason
    
    reason = "Event passes all filters"
    logger.info(
        "Event accepted: passes all filters DEBUG",
        extra={'extra_fields': {
            'stageId': stage_id,
            'objectKey': object_key,
            'filterResult': reason
        }}
    )
    
    return True, reason