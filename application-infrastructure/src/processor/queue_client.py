"""SQS queue client for receiving and deleting messages in the Processor Lambda."""

import json
import os
import sys
from typing import List, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.constants import (
    MAX_RETRY_ATTEMPTS_SQS,
    SQS_MAX_BATCH_SIZE,
    SQS_LONG_POLL_WAIT_TIME_SECONDS
)
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


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_SQS,
    exceptions=(ClientError,)
)
def receive_messages_batch(queue_url: str, max_messages: int = SQS_MAX_BATCH_SIZE) -> List[Dict]:
    """Receive messages from the SQS queue in batches with long polling.
    
    Retrieves messages from the Event Queue for batch processing.
    Uses long polling to reduce empty responses and API costs.
    Handles empty queue gracefully by returning an empty list.
    
    Args:
        queue_url: SQS queue URL
        max_messages: Maximum number of messages to retrieve (1-10)
        
    Returns:
        List of message dictionaries, each containing:
            - MessageId: SQS message ID
            - ReceiptHandle: Handle for deleting the message
            - Body: JSON string containing the event data
            - parsed_body: Parsed JSON body as dictionary
        Returns empty list if queue is empty.
        
    Raises:
        SQSClientError: If message retrieval fails after all retries
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    """
    try:
        sqs_client = get_sqs_client()
        
        # Ensure max_messages is within valid range
        max_messages = max(1, min(max_messages, 10))
        
        logger.info(
            "Receiving messages from SQS queue",
            extra={'extra_fields': {
                'queue_url': queue_url,
                'max_messages': max_messages,
                'wait_time_seconds': SQS_LONG_POLL_WAIT_TIME_SECONDS
            }}
        )
        
        # Receive messages with long polling
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=SQS_LONG_POLL_WAIT_TIME_SECONDS,
            AttributeNames=['All']
        )
        
        # Handle empty queue gracefully
        messages = response.get('Messages', [])
        
        if not messages:
            logger.info(
                "No messages available in queue",
                extra={'extra_fields': {'queue_url': queue_url}}
            )
            return []
        
        # Parse message bodies
        parsed_messages = []
        for message in messages:
            try:
                parsed_body = json.loads(message['Body'])
                message['parsed_body'] = parsed_body
                parsed_messages.append(message)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse message body as JSON: {str(e)}",
                    extra={'extra_fields': {
                        'message_id': message.get('MessageId'),
                        'error': str(e)
                    }}
                )
                # Skip malformed messages
                continue
        
        logger.info(
            f"Successfully received {len(parsed_messages)} messages from SQS",
            extra={'extra_fields': {
                'message_count': len(parsed_messages),
                'queue_url': queue_url
            }}
        )
        
        return parsed_messages
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"SQS receive_message failed: {error_code} - {error_message}",
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
            f"Unexpected error receiving messages from SQS: {str(e)}",
            extra={'extra_fields': {
                'error': str(e),
                'queue_url': queue_url
            }}
        )
        raise SQSClientError(f"Failed to receive messages from SQS: {str(e)}") from e


def delete_message(queue_url: str, receipt_handle: str) -> None:
    """Delete a single message from the SQS queue.
    
    Removes a successfully processed message from the queue.
    
    Args:
        queue_url: SQS queue URL
        receipt_handle: Receipt handle from the received message
        
    Raises:
        SQSClientError: If message deletion fails
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    """
    try:
        sqs_client = get_sqs_client()
        
        logger.debug(
            "Deleting message from SQS queue",
            extra={'extra_fields': {
                'queue_url': queue_url,
                'receipt_handle': receipt_handle[:50] + '...'  # Truncate for logging
            }}
        )
        
        sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        
        logger.debug(
            "Successfully deleted message from SQS",
            extra={'extra_fields': {'queue_url': queue_url}}
        )
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"SQS delete_message failed: {error_code} - {error_message}",
            extra={'extra_fields': {
                'error_code': error_code,
                'error_message': error_message,
                'queue_url': queue_url
            }}
        )
        
        raise SQSClientError(
            f"Failed to delete message from SQS: {error_code} - {error_message}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting message from SQS: {str(e)}",
            extra={'extra_fields': {
                'error': str(e),
                'queue_url': queue_url
            }}
        )
        raise SQSClientError(f"Failed to delete message from SQS: {str(e)}") from e


def delete_messages_batch(queue_url: str, receipt_handles: List[str]) -> Dict[str, List[str]]:
    """Delete multiple messages from the SQS queue in a single batch operation.
    
    Efficiently removes multiple successfully processed messages.
    Handles partial failures by returning both successful and failed deletions.
    
    Args:
        queue_url: SQS queue URL
        receipt_handles: List of receipt handles from received messages
        
    Returns:
        Dictionary with keys:
            - 'successful': List of successfully deleted receipt handles
            - 'failed': List of failed receipt handles
        
    Raises:
        SQSClientError: If batch deletion request fails entirely
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    """
    if not receipt_handles:
        logger.debug("No messages to delete")
        return {'successful': [], 'failed': []}
    
    try:
        sqs_client = get_sqs_client()
        
        # SQS batch delete supports up to 10 messages at a time
        batch_size = 10
        all_successful = []
        all_failed = []
        
        for i in range(0, len(receipt_handles), batch_size):
            batch = receipt_handles[i:i + batch_size]
            
            # Format entries for batch delete
            entries = [
                {
                    'Id': str(idx),
                    'ReceiptHandle': handle
                }
                for idx, handle in enumerate(batch)
            ]
            
            logger.info(
                f"Deleting batch of {len(entries)} messages from SQS",
                extra={'extra_fields': {
                    'queue_url': queue_url,
                    'batch_size': len(entries)
                }}
            )
            
            response = sqs_client.delete_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            
            # Track successful deletions
            successful = response.get('Successful', [])
            for success in successful:
                idx = int(success['Id'])
                all_successful.append(batch[idx])
            
            # Track failed deletions
            failed = response.get('Failed', [])
            for failure in failed:
                idx = int(failure['Id'])
                all_failed.append(batch[idx])
                
                logger.error(
                    f"Failed to delete message: {failure.get('Code')} - {failure.get('Message')}",
                    extra={'extra_fields': {
                        'error_code': failure.get('Code'),
                        'error_message': failure.get('Message'),
                        'sender_fault': failure.get('SenderFault', False)
                    }}
                )
        
        logger.info(
            f"Batch delete completed: {len(all_successful)} successful, {len(all_failed)} failed",
            extra={'extra_fields': {
                'successful_count': len(all_successful),
                'failed_count': len(all_failed),
                'queue_url': queue_url
            }}
        )
        
        return {
            'successful': all_successful,
            'failed': all_failed
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"SQS delete_message_batch failed: {error_code} - {error_message}",
            extra={'extra_fields': {
                'error_code': error_code,
                'error_message': error_message,
                'queue_url': queue_url,
                'message_count': len(receipt_handles)
            }}
        )
        
        raise SQSClientError(
            f"Failed to delete message batch from SQS: {error_code} - {error_message}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting message batch from SQS: {str(e)}",
            extra={'extra_fields': {
                'error': str(e),
                'queue_url': queue_url,
                'message_count': len(receipt_handles)
            }}
        )
        raise SQSClientError(f"Failed to delete message batch from SQS: {str(e)}") from e
