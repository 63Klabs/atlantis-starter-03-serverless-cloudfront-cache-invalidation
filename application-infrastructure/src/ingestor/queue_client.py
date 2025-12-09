"""SQS queue client for sending S3 event messages."""

import json
import os
import sys
from typing import Dict

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.constants import MAX_RETRY_ATTEMPTS_SQS
from common.retry import retry_with_backoff
from common.logger import setup_logger

logger = setup_logger(__name__)


class SQSClientError(Exception):
    """Exception raised when SQS operations fail."""
    pass


def get_sqs_client():
    """Get or create SQS client instance.
    
    Returns:
        boto3 SQS client
    """
    return boto3.client('sqs')


def format_sqs_message(bucket_name: str, object_key: str, origin_path: str, 
                       stage_id: str, event_time: str, event_type: str) -> Dict[str, str]:
    """Format an SQS message with S3 event metadata.
    
    Creates a message containing all required fields for downstream processing.
    
    Args:
        bucket_name: S3 bucket name
        object_key: Full S3 object key
        origin_path: Extracted origin path (/<StageId>/public)
        stage_id: Extracted StageId
        event_time: ISO 8601 timestamp of the event
        event_type: S3 event type (e.g., ObjectCreated:Put)
        
    Returns:
        Dictionary containing all message fields
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 8: SQS message format completeness**
    """
    return {
        'bucketName': bucket_name,
        'objectKey': object_key,
        'originPath': origin_path,
        'stageId': stage_id,
        'eventTime': event_time,
        'eventType': event_type
    }


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_SQS,
    exceptions=(ClientError,)
)
def send_message(queue_url: str, message_body: Dict[str, str]) -> str:
    """Send a message to the SQS queue with retry logic.
    
    Sends an S3 event message to the Event Queue for batch processing.
    Retries automatically on transient failures with exponential backoff.
    
    Args:
        queue_url: SQS queue URL
        message_body: Message dictionary to send
        
    Returns:
        Message ID from SQS
        
    Raises:
        SQSClientError: If message send fails after all retries
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 8: SQS message format completeness**
    """
    try:
        sqs_client = get_sqs_client()
        
        # Convert message body to JSON string
        message_json = json.dumps(message_body)
        
        logger.info(
            "Sending message to SQS queue",
            extra={'extra_fields': {
                'queue_url': queue_url,
                'bucket_name': message_body.get('bucketName'),
                'stage_id': message_body.get('stageId'),
                'origin_path': message_body.get('originPath')
            }}
        )
        
        # Send message to SQS
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_json
        )
        
        message_id = response['MessageId']
        
        logger.info(
            "Successfully sent message to SQS",
            extra={'extra_fields': {
                'message_id': message_id,
                'queue_url': queue_url
            }}
        )
        
        return message_id
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"SQS send_message failed: {error_code} - {error_message}",
            extra={'extra_fields': {
                'error_code': error_code,
                'error_message': error_message,
                'queue_url': queue_url
            }}
        )
        
        # Re-raise to trigger retry
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error sending message to SQS: {str(e)}",
            extra={'extra_fields': {
                'error': str(e),
                'queue_url': queue_url
            }}
        )
        raise SQSClientError(f"Failed to send message to SQS: {str(e)}") from e


def send_event_to_queue(queue_url: str, bucket_name: str, object_key: str, 
                        origin_path: str, stage_id: str, event_time: str,
                        event_type: str) -> str:
    """Send an S3 event to the SQS queue.
    
    High-level function that formats and sends an S3 event message.
    
    Args:
        queue_url: SQS queue URL
        bucket_name: S3 bucket name
        object_key: Full S3 object key
        origin_path: Extracted origin path (/<StageId>/public)
        stage_id: Extracted StageId
        event_time: ISO 8601 timestamp of the event
        event_type: S3 event type
        
    Returns:
        Message ID from SQS
        
    Raises:
        SQSClientError: If message send fails after all retries
    """
    # Format the message
    message_body = format_sqs_message(
        bucket_name=bucket_name,
        object_key=object_key,
        origin_path=origin_path,
        stage_id=stage_id,
        event_time=event_time,
        event_type=event_type
    )
    
    # Send to queue
    return send_message(queue_url, message_body)
