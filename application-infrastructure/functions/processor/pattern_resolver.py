"""Pattern resolution for bucket-specific origin path patterns."""

import boto3
from botocore.exceptions import ClientError
from typing import Optional

# Import from Lambda layer
from common.logger import setup_logger  # pyright: ignore[reportMissingImports]
from common.constants import (  # pyright: ignore[reportMissingImports]
    ORIGIN_PATH_PATTERN,
    PUBLIC_PATH_SEGMENT,
    PRODUCTION_STAGE_IDENTIFIERS,
    NON_PRODUCTION_STAGE_IDENTIFIERS
)
from common.path_utils import matches_pattern, derive_pattern_from_path  # pyright: ignore[reportMissingImports]

logger = setup_logger(__name__)


def resolve_bucket_pattern(bucket_name: str, sample_event_path: str) -> str:
    """
    Determine the origin path pattern for a bucket.
    
    Priority:
    1. Bucket tag (invalidator:OriginPathPattern)
    2. Pattern match with ORIGIN_PATH_PATTERN
    3. Derive from public segment placement
    
    Args:
        bucket_name: S3 bucket name
        sample_event_path: Sample S3 object key from an event
        
    Returns:
        Resolved bucket pattern string
        
    Examples:
        >>> resolve_bucket_pattern('my-bucket', '/prod/public/file.html')
        '/{stageId}/public'  # If tag not present and matches ORIGIN_PATH_PATTERN
        
        >>> resolve_bucket_pattern('my-bucket', '/public/file.html')
        '/public'  # If tag not present and derived from public segment
    """
    # Check bucket tag
    s3_client = boto3.client('s3')
    try:
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        for tag in response.get('TagSet', []):
            if tag['Key'] == 'invalidator:OriginPathPattern':
                tag_value = tag['Value']
                logger.info(
                    f"Using bucket tag pattern for {bucket_name}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'pattern': tag_value,
                        'pattern_source': 'bucket_tag'
                    }}
                )
                return tag_value
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchTagSet':
            logger.warning(
                f"Error retrieving bucket tags for {bucket_name}: {str(e)}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'error': str(e),
                    'error_code': e.response['Error']['Code']
                }}
            )
    
    # Try pattern match with ORIGIN_PATH_PATTERN
    all_stages = PRODUCTION_STAGE_IDENTIFIERS + NON_PRODUCTION_STAGE_IDENTIFIERS
    matches, _ = matches_pattern(sample_event_path, ORIGIN_PATH_PATTERN, all_stages)
    if matches:
        logger.info(
            f"Using ORIGIN_PATH_PATTERN for {bucket_name}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'pattern': ORIGIN_PATH_PATTERN,
                'pattern_source': 'environment_variable'
            }}
        )
        return ORIGIN_PATH_PATTERN
    
    # Derive from public segment
    derived = derive_pattern_from_path(
        sample_event_path,
        PUBLIC_PATH_SEGMENT,
        PRODUCTION_STAGE_IDENTIFIERS,
        NON_PRODUCTION_STAGE_IDENTIFIERS
    )
    
    if derived:
        logger.info(
            f"Derived pattern from public segment for {bucket_name}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'pattern': derived,
                'pattern_source': 'derived_from_public_segment',
                'sample_path': sample_event_path
            }}
        )
        return derived
    
    # Fallback to ORIGIN_PATH_PATTERN
    logger.warning(
        f"Could not derive pattern for {bucket_name}, using ORIGIN_PATH_PATTERN as fallback",
        extra={'extra_fields': {
            'bucket_name': bucket_name,
            'pattern': ORIGIN_PATH_PATTERN,
            'pattern_source': 'fallback',
            'sample_path': sample_event_path
        }}
    )
    return ORIGIN_PATH_PATTERN



def filter_events_by_pattern(events: list, bucket_pattern: str) -> list:
    """
    Filter events that match the bucket's origin path pattern.
    
    Returns only events that:
    1. Match the bucket pattern
    2. Are production stages (if pattern has {stageId})
    
    Args:
        events: List of SQS messages with parsed_body containing objectKey
        bucket_pattern: Resolved origin path pattern for the bucket
        
    Returns:
        Filtered list of events
        
    Examples:
        >>> events = [
        ...     {'parsed_body': {'objectKey': '/prod/public/file.html'}},
        ...     {'parsed_body': {'objectKey': '/dev/public/file.html'}},
        ... ]
        >>> filter_events_by_pattern(events, '/{stageId}/public')
        [{'parsed_body': {'objectKey': '/prod/public/file.html'}}]  # dev filtered out
    """
    from common.path_utils import extract_stage_from_path  # pyright: ignore[reportMissingImports]
    
    filtered = []
    all_stages = PRODUCTION_STAGE_IDENTIFIERS + NON_PRODUCTION_STAGE_IDENTIFIERS
    
    for event in events:
        parsed_body = event.get('parsed_body', {})
        event_path = parsed_body.get('objectKey', '')
        
        if not event_path:
            logger.warning(
                "Event missing objectKey, skipping",
                extra={'extra_fields': {
                    'event': event,
                    'filter_reason': 'missing_object_key'
                }}
            )
            continue
        
        # Check pattern match
        matches, stage = matches_pattern(event_path, bucket_pattern, all_stages)
        if not matches:
            logger.debug(
                f"Event path does not match bucket pattern, filtering out",
                extra={'extra_fields': {
                    'event_path': event_path,
                    'bucket_pattern': bucket_pattern,
                    'filter_reason': 'pattern_mismatch'
                }}
            )
            continue
        
        # Stage filtering
        if '{stageId}' in bucket_pattern:
            if stage and stage in PRODUCTION_STAGE_IDENTIFIERS:
                filtered.append(event)
                logger.debug(
                    f"Event passed stage filtering (production stage)",
                    extra={'extra_fields': {
                        'event_path': event_path,
                        'stage': stage,
                        'filter_result': 'passed'
                    }}
                )
            else:
                logger.debug(
                    f"Event filtered out (non-production stage)",
                    extra={'extra_fields': {
                        'event_path': event_path,
                        'stage': stage,
                        'filter_reason': 'non_production_stage'
                    }}
                )
        else:
            # No stage placeholder, treat as production
            filtered.append(event)
            logger.debug(
                f"Event passed filtering (no stage placeholder)",
                extra={'extra_fields': {
                    'event_path': event_path,
                    'filter_result': 'passed'
                }}
            )
    
    logger.info(
        f"Event filtering complete: {len(events)} -> {len(filtered)} events",
        extra={'extra_fields': {
            'original_count': len(events),
            'filtered_count': len(filtered),
            'bucket_pattern': bucket_pattern
        }}
    )
    
    return filtered
