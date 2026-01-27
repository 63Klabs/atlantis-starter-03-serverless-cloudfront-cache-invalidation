"""S3 event parsing module for extracting event metadata."""

from typing import Dict, Optional
from datetime import datetime
import os

from common.logger import setup_logger # pyright: ignore[reportMissingImports]


class S3EventParseError(Exception):
    """Exception raised when S3 event parsing fails."""
    pass


def extract_event_metadata(record: Dict) -> Dict[str, str]:
    """Extract metadata from an S3 event record.
    
    Extracts bucketName, objectKey, eventTime, and eventType from an S3 event notification.
    
    Args:
        record: S3 event record from the Records array
        
    Returns:
        Dictionary containing:
            - bucketName: Name of the S3 bucket
            - objectKey: Full S3 object key
            - eventTime: ISO 8601 timestamp of the event
            - eventType: S3 event type (e.g., ObjectCreated:Put)
            
    Raises:
        S3EventParseError: If required fields are missing or malformed
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 1: S3 event field extraction completeness**
    """
    logger = setup_logger(__name__)
    
    # DEBUG: Log extraction attempt
    # logger.info(
    #     "Extracting event metadata DEBUG",
    #     extra={'extra_fields': {
    #         'recordType': type(record).__name__,
    #         'recordKeys': list(record.keys()) if isinstance(record, dict) else 'not_dict',
    #         'hasS3Key': 's3' in record if isinstance(record, dict) else False,
    #         'hasEventTime': 'eventTime' in record if isinstance(record, dict) else False,
    #         'hasEventName': 'eventName' in record if isinstance(record, dict) else False
    #     }}
    # )
    
    try:
        # DEBUG: Log S3 section analysis
        s3_section = record.get('s3', {})
        # logger.info(
        #     "S3 section analysis DEBUG",
        #     extra={'extra_fields': {
        #         's3Section': s3_section,
        #         's3Keys': list(s3_section.keys()) if isinstance(s3_section, dict) else 'not_dict',
        #         'hasBucket': 'bucket' in s3_section if isinstance(s3_section, dict) else False,
        #         'hasObject': 'object' in s3_section if isinstance(s3_section, dict) else False
        #     }}
        # )
        
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        event_time = record['eventTime']
        event_type = record['eventName']
        
        # DEBUG: Log extracted values
        # logger.info(
        #     "Raw extraction results DEBUG",
        #     extra={'extra_fields': {
        #         'bucketName': bucket_name,
        #         'objectKey': object_key,
        #         'eventTime': event_time,
        #         'eventType': event_type,
        #         'bucketNameType': type(bucket_name).__name__,
        #         'objectKeyType': type(object_key).__name__,
        #         'eventTimeType': type(event_time).__name__,
        #         'eventTypeType': type(event_type).__name__
        #     }}
        # )
        
        # Validate that all fields are non-empty strings
        if not all([bucket_name, object_key, event_time, event_type]):
            logger.error(
                "Validation failed - empty fields",
                extra={'extra_fields': {
                    'bucketNameEmpty': not bucket_name,
                    'objectKeyEmpty': not object_key,
                    'eventTimeEmpty': not event_time,
                    'eventTypeEmpty': not event_type
                }}
            )
            raise S3EventParseError("One or more required fields are empty")
        
        result = {
            'bucketName': bucket_name,
            'objectKey': object_key,
            'eventTime': event_time,
            'eventType': event_type
        }
        
        # DEBUG: Log final result
        # logger.info(
        #     "Event metadata extraction successful DEBUG",
        #     extra={'extra_fields': {
        #         'extractedMetadata': result
        #     }}
        # )
        
        return result
        
    except KeyError as e:
        logger.error(
            "KeyError during extraction",
            extra={'extra_fields': {
                'missingKey': str(e),
                'recordStructure': record
            }}
        )
        raise S3EventParseError(f"Missing required field in S3 event: {e}")
    except TypeError as e:
        logger.error(
            "TypeError during extraction",
            extra={'extra_fields': {
                'typeError': str(e),
                'recordType': type(record).__name__
            }}
        )
        raise S3EventParseError(f"Invalid S3 event structure: {e}")


def extract_stage_id(object_key: str) -> Optional[str]:
    """Extract StageId from object key using the configured pattern.
    
    Uses ORIGIN_PATH_PATTERN to determine where the stage ID is located.
    For root pattern (/), returns "prod" as default (no stage filtering).
    For patterns without {stageId}, returns "prod" as default.
    For patterns with {stageId}, extracts the stage from the matching position.
    
    Args:
        object_key: S3 object key path (e.g., "/prod/public/images/logo.png")
        
    Returns:
        StageId string, or None if unable to extract
        
    Examples:
        >>> # With ORIGIN_PATH_PATTERN = "/{stageId}/public"
        >>> extract_stage_id("/prod/public/images/logo.png")
        'prod'
        
        >>> # With ORIGIN_PATH_PATTERN = "/"
        >>> extract_stage_id("/any/path/file.html")
        'prod'
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 2: StageId extraction from object key**
    """
    from common.constants import (  # pyright: ignore[reportMissingImports]
        ORIGIN_PATH_PATTERN,
        PRODUCTION_STAGE_IDENTIFIERS,
        NON_PRODUCTION_STAGE_IDENTIFIERS
    )
    from common.path_utils import extract_stage_from_path  # pyright: ignore[reportMissingImports]
    
    logger = setup_logger(__name__)
    
    # DEBUG: Log StageId extraction
    # logger.info(
    #     "Extracting StageId DEBUG",
    #     extra={'extra_fields': {
    #         'objectKey': object_key,
    #         'objectKeyType': type(object_key).__name__,
    #         'objectKeyLength': len(object_key) if object_key else 0
    #     }}
    # )
    
    if not object_key:
        logger.info("StageId extraction: empty object key")
        return None
    
    # Special case: root pattern or pattern without {stageId}
    if ORIGIN_PATH_PATTERN == '/' or '{stageId}' not in ORIGIN_PATH_PATTERN:
        # No stage filtering, treat as production
        return 'prod'
    
    # Extract stage using the pattern
    stage = extract_stage_from_path(object_key, ORIGIN_PATH_PATTERN)
    
    if stage:
        return stage
    
    # Fallback: try to extract from first segment (backward compatibility)
    path_segments = object_key.lstrip('/').split('/')
    non_empty_segments = [seg for seg in path_segments if seg]
    
    if not non_empty_segments:
        return None
    
    first_segment = non_empty_segments[0]
    
    # Check if first segment is a known stage identifier
    all_stages = PRODUCTION_STAGE_IDENTIFIERS + NON_PRODUCTION_STAGE_IDENTIFIERS
    if first_segment in all_stages:
        return first_segment
    
    # If not a known stage, treat as production (no stage filtering)
    return 'prod'


def extract_origin_path(object_key: str) -> Optional[str]:
    """Extract origin path from object key using the configured pattern.
    
    Uses ORIGIN_PATH_PATTERN to determine the origin path structure.
    For root pattern (/), returns "/" for all paths.
    For pattern-based paths, extracts the matching origin path.
    
    Args:
        object_key: S3 object key path
        
    Returns:
        Origin path string, or None if pattern doesn't match
        
    Examples:
        >>> # With ORIGIN_PATH_PATTERN = "/{stageId}/public"
        >>> extract_origin_path("/prod/public/images/logo.png")
        '/prod/public'
        
        >>> # With ORIGIN_PATH_PATTERN = "/"
        >>> extract_origin_path("/any/path/file.html")
        '/'
    """
    from common.constants import (  # pyright: ignore[reportMissingImports]
        ORIGIN_PATH_PATTERN,
        PUBLIC_PATH_SEGMENT,
        PRODUCTION_STAGE_IDENTIFIERS,
        NON_PRODUCTION_STAGE_IDENTIFIERS
    )
    from common.path_utils import matches_pattern, derive_pattern_from_path  # pyright: ignore[reportMissingImports]
    
    if not object_key:
        return None
    
    # Special case: root pattern matches everything
    if ORIGIN_PATH_PATTERN == '/':
        return '/'
    
    # Try to match against the configured pattern
    all_stages = PRODUCTION_STAGE_IDENTIFIERS + NON_PRODUCTION_STAGE_IDENTIFIERS
    matches, stage = matches_pattern(object_key, ORIGIN_PATH_PATTERN, all_stages)
    
    if matches:
        # Extract the origin path by replacing {stageId} with actual stage
        if '{stageId}' in ORIGIN_PATH_PATTERN and stage:
            return ORIGIN_PATH_PATTERN.replace('{stageId}', stage)
        else:
            return ORIGIN_PATH_PATTERN
    
    # Fallback: Try to derive pattern from public segment
    if PUBLIC_PATH_SEGMENT in object_key:
        derived_pattern = derive_pattern_from_path(
            object_key,
            PUBLIC_PATH_SEGMENT,
            PRODUCTION_STAGE_IDENTIFIERS,
            NON_PRODUCTION_STAGE_IDENTIFIERS
        )
        
        if derived_pattern:
            # Extract the actual origin path from the object key
            segments = object_key.strip('/').split('/')
            try:
                public_index = segments.index(PUBLIC_PATH_SEGMENT)
                origin_segments = segments[:public_index + 1]
                return '/' + '/'.join(origin_segments)
            except ValueError:
                pass
    
    return None