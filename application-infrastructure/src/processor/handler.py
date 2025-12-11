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
from processor.queue_client import receive_messages_batch, delete_messages_batch
from processor.tag_validator import validate_bucket_tags, get_bucket_tags, validate_distribution_tags
from processor.distribution_finder import find_matching_distributions
from processor.path_consolidator import consolidate_paths
from processor.invalidation_client import create_invalidation
from ingestor.window_tracker import close_window

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
            'requestId': context.aws_request_id if context else 'unknown'
        }}
    )
    
    # Initialize counters for summary
    summary = {
        'total_messages': 0,
        'groups_processed': 0,
        'buckets_validated': 0,
        'buckets_rejected': 0,
        'distributions_found': 0,
        'distributions_validated': 0,
        'distributions_rejected': 0,
        'invalidations_submitted': 0,
        'invalidations_failed': 0,
        'messages_deleted': 0,
        'messages_failed_delete': 0
    }
    
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
        
        summary['total_messages'] = len(all_messages)
        
        if not all_messages:
            logger.info("No messages to process")
            
            # Close aggregation window even if no messages
            try:
                close_window()
            except Exception as e:
                logger.error(
                    f"Failed to close aggregation window: {str(e)}",
                    extra={'extra_fields': {'error': str(e)}}
                )
            
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
        summary['groups_processed'] = len(grouped_messages)
        
        # Track messages to delete (successfully processed)
        messages_to_delete = []
        
        # Step 3-7: Process each group
        for (bucket_name, origin_path), messages in grouped_messages.items():
            logger.info(
                f"Processing group: bucket={bucket_name}, origin={origin_path}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'origin_path': origin_path,
                    'message_count': len(messages)
                }}
            )
            
            # Step 3: Validate bucket tags
            if not validate_bucket_tags(bucket_name):
                logger.warning(
                    f"Bucket {bucket_name} failed tag validation, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                summary['buckets_rejected'] += 1
                # Still delete messages for rejected buckets (they were processed, just rejected)
                messages_to_delete.extend(messages)
                continue
            
            summary['buckets_validated'] += 1
            
            # Get bucket's Application tag for distribution validation
            bucket_tags = get_bucket_tags(bucket_name)
            if not bucket_tags:
                logger.error(
                    f"Failed to retrieve bucket tags for {bucket_name}, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            bucket_app_tag = bucket_tags.get('atlantis:Application', '')
            if not bucket_app_tag:
                logger.warning(
                    f"Bucket {bucket_name} missing atlantis:Application tag, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Extract stageId from first message (all messages in group have same stageId)
            stage_id = messages[0].get('parsed_body', {}).get('stageId', '')
            if not stage_id:
                logger.error(
                    f"Missing stageId in messages for bucket {bucket_name}, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Step 4: Find matching CloudFront distributions
            distribution_ids = find_matching_distributions(bucket_name, origin_path)
            
            if not distribution_ids:
                logger.info(
                    f"No distributions found for bucket {bucket_name} with origin {origin_path}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                # Delete messages even if no distributions found
                messages_to_delete.extend(messages)
                continue
            
            summary['distributions_found'] += len(distribution_ids)
            
            # Step 5: Validate distribution tags and filter
            valid_distributions = []
            for dist_id in distribution_ids:
                if validate_distribution_tags(dist_id, bucket_app_tag, stage_id):
                    valid_distributions.append(dist_id)
                    summary['distributions_validated'] += 1
                else:
                    logger.warning(
                        f"Distribution {dist_id} failed tag validation",
                        extra={'extra_fields': {
                            'distribution_id': dist_id,
                            'bucket_name': bucket_name,
                            'origin_path': origin_path
                        }}
                    )
                    summary['distributions_rejected'] += 1
            
            if not valid_distributions:
                logger.info(
                    f"No valid distributions for bucket {bucket_name} after tag validation",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                # Delete messages even if no valid distributions
                messages_to_delete.extend(messages)
                continue
            
            # Step 6: Extract and consolidate paths
            object_paths = []
            for message in messages:
                parsed_body = message.get('parsed_body', {})
                object_key = parsed_body.get('objectKey', '')
                if object_key:
                    # Remove the origin path prefix to get the relative path for invalidation
                    # CloudFront invalidation paths should be relative to the origin
                    if object_key.startswith(origin_path):
                        relative_path = object_key[len(origin_path):]
                        # Ensure path starts with /
                        if not relative_path.startswith('/'):
                            relative_path = '/' + relative_path
                        object_paths.append(relative_path)
                    else:
                        # Fallback: use full object key
                        object_paths.append(object_key)
            
            if not object_paths:
                logger.warning(
                    f"No valid paths extracted from messages for bucket {bucket_name}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Consolidate paths
            consolidated_path_chunks = consolidate_paths(object_paths)
            
            # Step 7: Submit invalidations for each valid distribution
            for dist_id in valid_distributions:
                for chunk_idx, path_chunk in enumerate(consolidated_path_chunks):
                    try:
                        result = create_invalidation(dist_id, path_chunk)
                        if result:
                            summary['invalidations_submitted'] += 1
                            logger.info(
                                f"Successfully submitted invalidation for distribution {dist_id}",
                                extra={'extra_fields': {
                                    'distribution_id': dist_id,
                                    'invalidation_id': result.get('Id'),
                                    'path_count': len(path_chunk),
                                    'chunk_index': chunk_idx,
                                    'total_chunks': len(consolidated_path_chunks)
                                }}
                            )
                        else:
                            summary['invalidations_failed'] += 1
                            logger.error(
                                f"Failed to submit invalidation for distribution {dist_id}",
                                extra={'extra_fields': {
                                    'distribution_id': dist_id,
                                    'path_count': len(path_chunk),
                                    'chunk_index': chunk_idx
                                }}
                            )
                    except Exception as e:
                        summary['invalidations_failed'] += 1
                        logger.error(
                            f"Exception submitting invalidation for distribution {dist_id}: {str(e)}",
                            extra={'extra_fields': {
                                'distribution_id': dist_id,
                                'error': str(e),
                                'path_count': len(path_chunk),
                                'chunk_index': chunk_idx
                            }}
                        )
            
            # Mark messages for deletion (processed successfully)
            messages_to_delete.extend(messages)
        
        # Step 8: Delete processed messages from SQS
        if messages_to_delete:
            receipt_handles = [msg.get('ReceiptHandle') for msg in messages_to_delete if msg.get('ReceiptHandle')]
            
            if receipt_handles:
                logger.info(
                    f"Deleting {len(receipt_handles)} processed messages from queue",
                    extra={'extra_fields': {
                        'message_count': len(receipt_handles)
                    }}
                )
                
                try:
                    delete_result = delete_messages_batch(queue_url, receipt_handles)
                    summary['messages_deleted'] = len(delete_result.get('successful', []))
                    summary['messages_failed_delete'] = len(delete_result.get('failed', []))
                    
                    if delete_result.get('failed'):
                        logger.warning(
                            f"Failed to delete {len(delete_result['failed'])} messages",
                            extra={'extra_fields': {
                                'failed_count': len(delete_result['failed'])
                            }}
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to delete messages from queue: {str(e)}",
                        extra={'extra_fields': {
                            'error': str(e),
                            'message_count': len(receipt_handles)
                        }}
                    )
        
        # Step 9: Close aggregation window
        try:
            close_window()
            logger.info("Successfully closed aggregation window")
        except Exception as e:
            logger.error(
                f"Failed to close aggregation window: {str(e)}",
                extra={'extra_fields': {
                    'error': str(e)
                }}
            )
            # Don't fail the entire handler if window closure fails
        
        # Log final summary
        logger.info(
            "Processor Lambda completed successfully",
            extra={'extra_fields': summary}
        )
        
        return {
            'statusCode': 200,
            'body': f"Processed {summary['total_messages']} messages, "
                   f"submitted {summary['invalidations_submitted']} invalidations, "
                   f"deleted {summary['messages_deleted']} messages"
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
                'error': str(e),
                'summary': summary
            }}
        )
        return {
            'statusCode': 500,
            'body': f'Internal error: {str(e)}'
        }
