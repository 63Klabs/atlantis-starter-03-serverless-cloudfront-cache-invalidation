"""DynamoDB window tracking for aggregation window management."""

import os
import time
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError

from common.logger import setup_logger
from common.retry import retry_with_backoff
from common.constants import (
    MAX_RETRY_ATTEMPTS_DYNAMODB,
    WINDOW_ID_FIXED_VALUE,
    WINDOW_STATUS_ACTIVE,
    WINDOW_STATUS_CLOSED,
    WINDOW_TTL_BUFFER_SECONDS,
    AGGREGATION_WINDOW_SECONDS
)

logger = setup_logger(__name__)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')


def get_tracking_table():
    """Get DynamoDB table for window tracking.
    
    Returns:
        DynamoDB Table resource
    """
    table_name = os.environ.get('TRACKING_TABLE')
    if not table_name:
        raise ValueError("TRACKING_TABLE environment variable not set")
    return dynamodb.Table(table_name)


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_DYNAMODB,
    exceptions=(ClientError,)
)
def check_active_window() -> Optional[Dict[str, Any]]:
    """Check if an active aggregation window exists.
    
    Queries DynamoDB for a window with status='active' and windowId='current'.
    
    Returns:
        Dictionary containing window data if active window exists, None otherwise.
        Window data includes: windowId, scheduleArn, windowStartTime, windowEndTime, status
        
    Raises:
        ClientError: If DynamoDB operation fails after retries
    """
    table = get_tracking_table()
    
    try:
        response = table.get_item(
            Key={'windowId': WINDOW_ID_FIXED_VALUE}
        )
        
        item = response.get('Item')
        
        if item and item.get('status') == WINDOW_STATUS_ACTIVE:
            logger.info(
                "Active aggregation window found",
                extra={'extra_fields': {
                    'windowId': item.get('windowId'),
                    'scheduleArn': item.get('scheduleArn'),
                    'windowStartTime': item.get('windowStartTime'),
                    'windowEndTime': item.get('windowEndTime')
                }}
            )
            return item
        
        logger.info("No active aggregation window found")
        return None
        
    except ClientError as e:
        logger.error(
            "Failed to check active window",
            extra={'extra_fields': {
                'error': str(e),
                'error_code': e.response.get('Error', {}).get('Code')
            }}
        )
        raise


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_DYNAMODB,
    exceptions=(ClientError,)
)
def create_window(schedule_arn: str) -> bool:
    """Create a new aggregation window with conditional write to prevent duplicates.
    
    Uses a conditional expression to ensure the window is only created if:
    - The windowId doesn't exist, OR
    - The existing window status is 'closed'
    
    Args:
        schedule_arn: ARN of the EventBridge schedule created for this window
        
    Returns:
        True if window was created successfully, False if condition failed (active window exists)
        
    Raises:
        ClientError: If DynamoDB operation fails after retries (except ConditionalCheckFailedException)
    """
    table = get_tracking_table()
    
    current_time = int(time.time())
    window_end_time = current_time + AGGREGATION_WINDOW_SECONDS
    ttl_time = window_end_time + WINDOW_TTL_BUFFER_SECONDS
    
    item = {
        'windowId': WINDOW_ID_FIXED_VALUE,
        'scheduleArn': schedule_arn,
        'windowStartTime': current_time,
        'windowEndTime': window_end_time,
        'status': WINDOW_STATUS_ACTIVE,
        'ttl': ttl_time
    }
    
    try:
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(windowId) OR #status = :closed',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':closed': WINDOW_STATUS_CLOSED
            }
        )
        
        logger.info(
            "Created new aggregation window",
            extra={'extra_fields': {
                'windowId': WINDOW_ID_FIXED_VALUE,
                'scheduleArn': schedule_arn,
                'windowStartTime': current_time,
                'windowEndTime': window_end_time,
                'ttl': ttl_time
            }}
        )
        return True
        
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            logger.info(
                "Active window already exists, skipping window creation",
                extra={'extra_fields': {
                    'windowId': WINDOW_ID_FIXED_VALUE
                }}
            )
            return False
        
        logger.error(
            "Failed to create window",
            extra={'extra_fields': {
                'error': str(e),
                'error_code': e.response.get('Error', {}).get('Code'),
                'scheduleArn': schedule_arn
            }}
        )
        raise


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_DYNAMODB,
    exceptions=(ClientError,)
)
def close_window() -> bool:
    """Close the current aggregation window by updating status to 'closed'.
    
    Updates the window status from 'active' to 'closed' to indicate processing is complete.
    
    Returns:
        True if window was closed successfully, False if window doesn't exist
        
    Raises:
        ClientError: If DynamoDB operation fails after retries
    """
    table = get_tracking_table()
    
    try:
        response = table.update_item(
            Key={'windowId': WINDOW_ID_FIXED_VALUE},
            UpdateExpression='SET #status = :closed',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':closed': WINDOW_STATUS_CLOSED
            },
            ConditionExpression='attribute_exists(windowId)',
            ReturnValues='ALL_NEW'
        )
        
        logger.info(
            "Closed aggregation window",
            extra={'extra_fields': {
                'windowId': WINDOW_ID_FIXED_VALUE,
                'updatedAttributes': response.get('Attributes')
            }}
        )
        return True
        
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            logger.warning(
                "Window does not exist, cannot close",
                extra={'extra_fields': {
                    'windowId': WINDOW_ID_FIXED_VALUE
                }}
            )
            return False
        
        logger.error(
            "Failed to close window",
            extra={'extra_fields': {
                'error': str(e),
                'error_code': e.response.get('Error', {}).get('Code')
            }}
        )
        raise
