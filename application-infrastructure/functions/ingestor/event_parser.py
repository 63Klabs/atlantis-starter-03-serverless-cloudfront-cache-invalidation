"""S3 event parsing module for extracting event metadata."""

from typing import Dict, Optional
from datetime import datetime

from common.logger import setup_logger


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
    logger.info(
        "Extracting event metadata DEBUG",
        extra={'extra_fields': {
            'recordType': type(record).__name__,
            'recordKeys': list(record.keys()) if isinstance(record, dict) else 'not_dict',
            'hasS3Key': 's3' in record if isinstance(record, dict) else False,
            'hasEventTime': 'eventTime' in record if isinstance(record, dict) else False,
            'hasEventName': 'eventName' in record if isinstance(record, dict) else False
        }}
    )
    
    try:
        # DEBUG: Log S3 section analysis
        s3_section = record.get('s3', {})
        logger.info(
            "S3 section analysis DEBUG",
            extra={'extra_fields': {
                's3Section': s3_section,
                's3Keys': list(s3_section.keys()) if isinstance(s3_section, dict) else 'not_dict',
                'hasBucket': 'bucket' in s3_section if isinstance(s3_section, dict) else False,
                'hasObject': 'object' in s3_section if isinstance(s3_section, dict) else False
            }}
        )
        
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        event_time = record['eventTime']
        event_type = record['eventName']
        
        # DEBUG: Log extracted values
        logger.info(
            "Raw extraction results DEBUG",
            extra={'extra_fields': {
                'bucketName': bucket_name,
                'objectKey': object_key,
                'eventTime': event_time,
                'eventType': event_type,
                'bucketNameType': type(bucket_name).__name__,
                'objectKeyType': type(object_key).__name__,
                'eventTimeType': type(event_time).__name__,
                'eventTypeType': type(event_type).__name__
            }}
        )
        
        # Validate that all fields are non-empty strings
        if not all([bucket_name, object_key, event_time, event_type]):
            logger.error(
                "Validation failed - empty fields DEBUG",
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
        logger.info(
            "Event metadata extraction successful DEBUG",
            extra={'extra_fields': {
                'extractedMetadata': result
            }}
        )
        
        return result
        
    except KeyError as e:
        logger.error(
            "KeyError during extraction DEBUG",
            extra={'extra_fields': {
                'missingKey': str(e),
                'recordStructure': record
            }}
        )
        raise S3EventParseError(f"Missing required field in S3 event: {e}")
    except TypeError as e:
        logger.error(
            "TypeError during extraction DEBUG",
            extra={'extra_fields': {
                'typeError': str(e),
                'recordType': type(record).__name__
            }}
        )
        raise S3EventParseError(f"Invalid S3 event structure: {e}")


def extract_stage_id(object_key: str) -> Optional[str]:
    """Extract StageId from the first path segment of an object key.
    
    The StageId is expected to be the first non-empty segment after the leading slash.
    For example, from "/prod/public/images/logo.png", extracts "prod".
    
    Args:
        object_key: S3 object key path
        
    Returns:
        StageId string, or None if the path has no segments
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 2: StageId extraction from object key**
    """
    logger = setup_logger(__name__)
    
    # DEBUG: Log StageId extraction
    logger.info(
        "Extracting StageId DEBUG",
        extra={'extra_fields': {
            'objectKey': object_key,
            'objectKeyType': type(object_key).__name__,
            'objectKeyLength': len(object_key) if object_key else 0
        }}
    )
    
    if not object_key:
        logger.info("StageId extraction: empty object key DEBUG")
        return None
    
    # Remove leading slash and split by '/'
    path_segments = object_key.lstrip('/').split('/')
    
    # DEBUG: Log path analysis
    logger.info(
        "Path segments analysis DEBUG",
        extra={'extra_fields': {
            'originalKey': object_key,
            'afterLstrip': object_key.lstrip('/'),
            'pathSegments': path_segments,
            'segmentCount': len(path_segments)
        }}
    )
    
    # Filter out empty segments and return the first one
    non_empty_segments = [seg for seg in path_segments if seg]
    
    # DEBUG: Log filtering results
    logger.info(
        "Segment filtering results DEBUG",
        extra={'extra_fields': {
            'nonEmptySegments': non_empty_segments,
            'nonEmptyCount': len(non_empty_segments),
            'firstSegment': non_empty_segments[0] if non_empty_segments else None
        }}
    )
    
    if not non_empty_segments:
        logger.info("StageId extraction: no non-empty segments DEBUG")
        return None
    
    result = non_empty_segments[0]
    logger.info(
        "StageId extraction result DEBUG",
        extra={'extra_fields': {
            'extractedStageId': result
        }}
    )
    
    return result


def extract_origin_path(object_key: str) -> Optional[str]:
    """Extract origin path from object key.
    
    The origin path is structured as /<StageId>/public.
    For example, from "/prod/public/images/logo.png", extracts "/prod/public".
    
    Args:
        object_key: S3 object key path
        
    Returns:
        Origin path string (/<StageId>/public), or None if pattern doesn't match
    """
    if not object_key:
        return None
    
    # Split the path
    parts = object_key.lstrip('/').split('/')
    
    # We need at least 2 segments: stageId and 'public'
    if len(parts) < 2:
        return None
    
    stage_id = parts[0]
    
    # Check if second segment is 'public'
    if parts[1] != 'public':
        return None
    
    return f"/{stage_id}/public"