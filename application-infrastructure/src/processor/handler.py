"""Processor Lambda handler for batch processing of S3 events.

This handler orchestrates the processing of queued S3 events:
1. Batch read messages from SQS
2. Group messages by bucketName and originPath
3. Validate bucket tags
4. Resolve CloudFront distributions
5. Validate distribution tags
6. Consolidate paths
7. Submit invalidations
8. Delete processed messages from SQS
9. Close aggregation window
"""

import os
import sys
from typing import Dict, Any, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.logger import setup_logger
from processor.queue_client import receive_messages_batch

logger = setup_logger(__name__)


def group_messages_by_bucket_and_origin(messages: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """Group SQS messages by bucketName and originPath.
    
    Groups events to enable batch processing of invalidations for the same
    bucket and origin combination. This allows efficient path consolidation
    and reduces the number of CloudFront API calls.
    
    Args:
        messages: List of SQS messages with parsed_body containing:
            - bucketName: S3 bucket name
            - objectKey: Full S3 object key
            - originPath: Origin path (/<StageId>/public)
            - stageId: Stage identifier
            - eventTime: ISO 8601 timestamp
            - eventType: S3 event type
            
    Returns:
        Dictionary where:
            - Keys are tuples of (bucketName, originPath)
            - Values are lists of messages belonging to that group
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 12: Event grouping by bucket and origin**
    """
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    
    for message in messages:
        # Extract parsed body
        parsed_body = message.get('parsed_body', {})
        
        # Get grouping keys
        bucket_name = parsed_body.get('bucketName')
        origin_path = parsed_body.get('originPath')
        
        # Skip messages with missing required fields
        if not bucket_name or not origin_path:
            logger.warning(
                "Skipping message with missing bucketName or originPath",
                extra={'extra_fields': {
                    'message_id': message.get('MessageId'),
                    'has_bucket': bool(bucket_name),
                    'has_origin': bool(origin_path)
                }}
            )
            continue
        
        # Create group key
        group_key = (bucket_name, origin_path)
        
        # Add message to group
        if group_key not in grouped:
            grouped[group_key] = []
        
        grouped[group_key].append(message)
    
    logger.info(
        f"Grouped {len(messages)} messages into {len(grouped)} bucket/origin combinations",
        extra={'extra_fields': {
            'total_messages': len(messages),
            'group_count': len(grouped),
            'groups': [
                {
                    'bucket': bucket,
                    'origin': origin,
                    'message_count': len(msgs)
                }
                for (bucket, origin), msgs in grouped.items()
            ]
        }}
    )
    
    return grouped


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for processing queued S3 events.
    
    Invoked by EventBridge Scheduler after the aggregation window.
    Processes all queued events, validates permissions, consolidates paths,
    and submits CloudFront invalidations.
    
    Args:
        event: EventBridge Scheduler event (empty for one-time schedules)
        context: Lambda context object
        
    Returns:
        Dictionary containing:
            - statusCode: HTTP status code (200 for success, 500 for failure)
            - body: Summary of processing results
    """
    logger.info(
        "Processor Lambda invoked",
        extra={'extra_fields': {
            'requestId': context.request_id if context else 'unknown'
        }}
    )
    
    try:
        # Get queue URL from environment
        queue_url = os.environ.get('QUEUE_URL')
        if not queue_url:
            raise ValueError("QUEUE_URL environment variable not set")
        
        # Step 1: Receive messages from SQS in batches
        all_messages = []
        
        # Continue receiving until queue is empty
        while True:
            messages = receive_messages_batch(queue_url)
            
            if not messages:
                # Queue is empty
                break
            
            all_messages.extend(messages)
            
            # Safety limit to prevent infinite loops
            if len(all_messages) >= 1000:
                logger.warning(
                    "Reached message limit, stopping batch retrieval",
                    extra={'extra_fields': {
                        'message_count': len(all_messages)
                    }}
                )
                break
        
        if not all_messages:
            logger.info("No messages to process")
            return {
                'statusCode': 200,
                'body': 'No messages to process'
            }
        
        logger.info(
            f"Retrieved {len(all_messages)} messages from queue",
            extra={'extra_fields': {
                'message_count': len(all_messages)
            }}
        )
        
        # Step 2: Group messages by bucket and origin path
        grouped_messages = group_messages_by_bucket_and_origin(all_messages)
        
        # TODO: Implement remaining processing steps:
        # - Validate bucket tags
        # - Find CloudFront distributions
        # - Validate distribution tags
        # - Consolidate paths
        # - Submit invalidations
        # - Delete processed messages
        # - Close aggregation window
        
        logger.info(
            "Processor Lambda completed",
            extra={'extra_fields': {
                'total_messages': len(all_messages),
                'groups_processed': len(grouped_messages)
            }}
        )
        
        return {
            'statusCode': 200,
            'body': f'Processed {len(all_messages)} messages in {len(grouped_messages)} groups'
        }
        
    except ValueError as e:
        logger.error(
            f"Configuration error: {str(e)}",
            extra={'extra_fields': {
                'error': str(e)
            }}
        )
        return {
            'statusCode': 500,
            'body': f'Configuration error: {str(e)}'
        }
    
    except Exception as e:
        logger.error(
            f"Unexpected error in handler: {str(e)}",
            extra={'extra_fields': {
                'error': str(e)
            }}
        )
        return {
            'statusCode': 500,
            'body': f'Internal error: {str(e)}'
        }
