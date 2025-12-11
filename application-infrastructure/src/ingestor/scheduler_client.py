"""EventBridge Scheduler client for creating one-time schedules."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from common.logger import setup_logger
from common.retry import retry_with_backoff
from common.constants import (
    MAX_RETRY_ATTEMPTS_SCHEDULER,
    AGGREGATION_WINDOW_SECONDS
)

logger = setup_logger(__name__)

# Initialize EventBridge Scheduler client
scheduler = boto3.client('scheduler')


def get_processor_function_arn() -> str:
    """Get the Processor Lambda function ARN from environment variables.
    
    Returns:
        Processor Lambda ARN
        
    Raises:
        ValueError: If PROCESSOR_FUNCTION_ARN environment variable is not set
    """
    function_arn = os.environ.get('PROCESSOR_FUNCTION_ARN')
    if not function_arn:
        raise ValueError("PROCESSOR_FUNCTION_ARN environment variable not set")
    return function_arn


def get_scheduler_role_arn() -> str:
    """Get the EventBridge Scheduler execution role ARN from environment variables.
    
    Returns:
        Scheduler execution role ARN
        
    Raises:
        ValueError: If SCHEDULER_ROLE_ARN environment variable is not set
    """
    role_arn = os.environ.get('SCHEDULER_ROLE_ARN')
    if not role_arn:
        raise ValueError("SCHEDULER_ROLE_ARN environment variable not set")
    return role_arn


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_SCHEDULER,
    exceptions=(ClientError,)
)
def create_one_time_schedule() -> Optional[str]:
    """Create a one-time EventBridge schedule to invoke Processor Lambda.
    
    Calculates target time as current time + AGGREGATION_WINDOW_SECONDS (5 minutes).
    Creates a schedule with at() expression for exact one-time execution.
    The schedule will automatically delete after execution.
    
    Returns:
        Schedule ARN if created successfully, None if creation failed
        
    Raises:
        ClientError: If EventBridge Scheduler operation fails after retries
        ValueError: If required environment variables are not set
    """
    try:
        # Calculate target time (current time + aggregation window)
        current_time = datetime.now(timezone.utc)
        target_time = current_time + timedelta(seconds=AGGREGATION_WINDOW_SECONDS)
        
        # Format as ISO 8601 for at() expression: YYYY-MM-DDTHH:MM:SS
        schedule_expression = f"at({target_time.strftime('%Y-%m-%dT%H:%M:%S')})"
        
        # Generate unique schedule name
        schedule_name = f"invalidation-processor-{uuid.uuid4()}"
        
        # Get required ARNs
        processor_arn = get_processor_function_arn()
        scheduler_role_arn = get_scheduler_role_arn()
        
        # DEBUG: Log schedule creation request
        schedule_request = {
            'Name': schedule_name,
            'ScheduleExpression': schedule_expression,
            'ScheduleExpressionTimezone': 'UTC',
            'Target': {
                'Arn': processor_arn,
                'RoleArn': scheduler_role_arn,
                'RetryPolicy': {
                    'MaximumRetryAttempts': 0  # Lambda handles retries internally
                }
            },
            'FlexibleTimeWindow': {
                'Mode': 'OFF'  # Exact time execution
            },
            'State': 'ENABLED',
            'ActionAfterCompletion': 'DELETE'  # Auto-delete after execution
        }
        
        logger.info(
            "Creating EventBridge schedule DEBUG",
            extra={'extra_fields': {
                'scheduleRequest': schedule_request,
                'currentTime': current_time.isoformat(),
                'targetTime': target_time.isoformat(),
                'aggregationWindowSeconds': AGGREGATION_WINDOW_SECONDS
            }}
        )
        
        # Create the one-time schedule
        response = scheduler.create_schedule(**schedule_request)
        
        # DEBUG: Log full AWS response
        logger.info(
            "EventBridge schedule creation response DEBUG",
            extra={'extra_fields': {
                'fullResponse': response,
                'responseKeys': list(response.keys()) if isinstance(response, dict) else 'not_dict',
                'responseMetadata': response.get('ResponseMetadata', {})
            }}
        )
        
        schedule_arn = response.get('ScheduleArn')
        
        logger.info(
            "Created one-time EventBridge schedule",
            extra={'extra_fields': {
                'scheduleName': schedule_name,
                'scheduleArn': schedule_arn,
                'scheduleExpression': schedule_expression,
                'targetTime': target_time.isoformat(),
                'processorArn': processor_arn,
                'aggregationWindowSeconds': AGGREGATION_WINDOW_SECONDS
            }}
        )
        
        return schedule_arn
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_message = e.response.get('Error', {}).get('Message')
        
        logger.error(
            "Failed to create EventBridge schedule",
            extra={'extra_fields': {
                'error': str(e),
                'error_code': error_code,
                'error_message': error_message,
                'processorArn': os.environ.get('PROCESSOR_FUNCTION_ARN'),
                'aggregationWindowSeconds': AGGREGATION_WINDOW_SECONDS
            }}
        )
        raise
    
    except ValueError as e:
        logger.error(
            "Configuration error creating schedule",
            extra={'extra_fields': {
                'error': str(e)
            }}
        )
        raise

