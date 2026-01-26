"""S3 event filtering module for validating events based on StageId and path patterns."""

from typing import Tuple

from common.constants import (  # pyright: ignore[reportMissingImports]
    ORIGIN_PATH_PATTERN,
    PUBLIC_PATH_SEGMENT,
    PRODUCTION_STAGE_IDENTIFIERS,
    NON_PRODUCTION_STAGE_IDENTIFIERS
)
from common.path_utils import matches_pattern  # pyright: ignore[reportMissingImports]
from common.logger import setup_logger  # pyright: ignore[reportMissingImports]

logger = setup_logger(__name__)


def should_process_event(event_path: str) -> Tuple[bool, str]:
    """Determine if an S3 event should be queued for processing.
    
    Logic:
    1. Try exact pattern match with production stages
    2. Fall back to public segment detection
    3. Filter non-production stages
    
    Args:
        event_path: S3 object key from event
        
    Returns:
        Tuple of (should_process: bool, reason: str)
        - should_process: True if event passes all filters
        - reason: Explanation of the decision (for logging)
        
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
    """
    # Try exact pattern match
    all_stages = PRODUCTION_STAGE_IDENTIFIERS + NON_PRODUCTION_STAGE_IDENTIFIERS
    matches, stage = matches_pattern(event_path, ORIGIN_PATH_PATTERN, all_stages)
    
    if matches:
        # If pattern has {stageId}, only allow production stages
        if '{stageId}' in ORIGIN_PATH_PATTERN:
            if stage in PRODUCTION_STAGE_IDENTIFIERS:
                reason = f"Event matches pattern '{ORIGIN_PATH_PATTERN}' with production stage '{stage}'"
                logger.debug(
                    "Event accepted: pattern match with production stage",
                    extra={'extra_fields': {
                        'eventPath': event_path,
                        'pattern': ORIGIN_PATH_PATTERN,
                        'stage': stage,
                        'reason': reason
                    }}
                )
                return True, reason
            else:
                reason = f"Event matches pattern but stage '{stage}' is non-production"
                logger.debug(
                    "Event filtered: non-production stage",
                    extra={'extra_fields': {
                        'eventPath': event_path,
                        'pattern': ORIGIN_PATH_PATTERN,
                        'stage': stage,
                        'reason': reason
                    }}
                )
                return False, reason
        else:
            # No stage placeholder, treat as production
            reason = f"Event matches pattern '{ORIGIN_PATH_PATTERN}' (no stage filtering)"
            logger.debug(
                "Event accepted: pattern match without stage placeholder",
                extra={'extra_fields': {
                    'eventPath': event_path,
                    'pattern': ORIGIN_PATH_PATTERN,
                    'reason': reason
                }}
            )
            return True, reason
    
    # Fallback: Check for public segment
    if PUBLIC_PATH_SEGMENT in event_path:
        segments = event_path.strip('/').split('/')
        try:
            public_index = segments.index(PUBLIC_PATH_SEGMENT)
            # Check if any non-prod stage appears before public
            for i in range(public_index):
                if segments[i] in NON_PRODUCTION_STAGE_IDENTIFIERS:
                    reason = f"Event contains non-production stage '{segments[i]}' before public segment"
                    logger.debug(
                        "Event filtered: non-production stage before public segment",
                        extra={'extra_fields': {
                            'eventPath': event_path,
                            'nonProdStage': segments[i],
                            'reason': reason
                        }}
                    )
                    return False, reason
            
            reason = f"Event contains public segment and no non-production stages"
            logger.debug(
                "Event accepted: public segment fallback",
                extra={'extra_fields': {
                    'eventPath': event_path,
                    'reason': reason
                }}
            )
            return True, reason
        except ValueError:
            pass
    
    # No match
    reason = f"Event does not match pattern '{ORIGIN_PATH_PATTERN}' and does not contain public segment"
    logger.debug(
        "Event filtered: no pattern match or public segment",
        extra={'extra_fields': {
            'eventPath': event_path,
            'pattern': ORIGIN_PATH_PATTERN,
            'reason': reason
        }}
    )
    return False, reason