"""S3 event parsing module for extracting event metadata."""

from typing import Dict, Optional
from datetime import datetime


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
    try:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        event_time = record['eventTime']
        event_type = record['eventName']
        
        # Validate that all fields are non-empty strings
        if not all([bucket_name, object_key, event_time, event_type]):
            raise S3EventParseError("One or more required fields are empty")
        
        return {
            'bucketName': bucket_name,
            'objectKey': object_key,
            'eventTime': event_time,
            'eventType': event_type
        }
    except KeyError as e:
        raise S3EventParseError(f"Missing required field in S3 event: {e}")
    except TypeError as e:
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
    if not object_key:
        return None
    
    # Remove leading slash and split by '/'
    path_segments = object_key.lstrip('/').split('/')
    
    # Filter out empty segments and return the first one
    non_empty_segments = [seg for seg in path_segments if seg]
    
    if not non_empty_segments:
        return None
    
    return non_empty_segments[0]


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
