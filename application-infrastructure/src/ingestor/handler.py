"""Ingestor Lambda handler for S3 event processing.

This handler orchestrates the ingestion of S3 events:
1. Parse S3 event to extract metadata
2. Filter events based on StageId and path patterns
3. Send valid events to SQS queue
4. Check and create aggregation window using DynamoDB and EventBridge Scheduler
5. Log all operations in JSON format
6. Return success/failure response to S3
"""

import os
import sys
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.logger import setup_logger
from ingestor.event_parser import (
    extract_event_metadata,
    extract_stage_id,
    extract_origin_path,
    S3EventParseError
)
from ingestor.event_filter import should_process_event
from ingestor.queue_client import send_event_to_queue, SQSClientError
from ingestor.window_tracker import check_active_window, create_window
from ingestor.scheduler_client import create_one_time_schedule

logger = setup_logger(__name__)


def get_queue_url() -> str:
    """Get SQS queue URL from environment variables.
    
    Returns:
        SQS queue URL
        
    Raises:
        ValueError: If QUEUE_URL environment variable is not set
    """
    queue_url = os.environ.get('QUEUE_URL')
    if not queue_url:
        raise ValueError("QUEUE_URL environment variable not set")
    return queue_url


def process_s3_record(record: Dict[str, Any], queue_url: str) -> Dict[str, Any]:
    """Process a single S3 event record.
    
    Args:
        record: S3 event record from the Records array
        queue_url: SQS queue URL
        
    Returns:
        Dictionary containing processing result with keys:
            - success: bool indicating if processing succeeded
            - message: str describing the result
            - metadata: dict with event metadata (if successful)
    """
    try:
        # Step 1: Parse S3 event to extract metadata
        metadata = extract_event_metadata(record)
        bucket_name = metadata['bucketName']
        object_key = metadata['objectKey']
        event_time = metadata['eventTime']
        event_type = metadata['eventType']
        
        # Step 2: Extract StageId and origin path
        stage_id = extract_stage_id(object_key)
        origin_path = extract_origin_path(object_key)
        
        if not stage_id:
            logger.info(
                "Skipping event: unable to extract StageId from object key",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'objectKey': object_key,
                    'eventType': event_type
                }}
            )
            return {
                'success': True,
                'message': 'Event skipped: no StageId found',
                'metadata': metadata
            }
        
        if not origin_path:
            logger.info(
                "Skipping event: unable to extract origin path from object key",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'objectKey': object_key,
                    'stageId': stage_id,
                    'eventType': event_type
                }}
            )
            return {
                'success': True,
                'message': 'Event skipped: no origin path found',
                'metadata': metadata
            }
        
        # Step 3: Log event details (Property 3: Event logging contains required fields)
        logger.info(
            "Processing S3 event",
            extra={'extra_fields': {
                'bucketName': bucket_name,
                'originPath': origin_path,
                'stageId': stage_id,
                'objectKey': object_key,
                'eventType': event_type,
                'eventTime': event_time
            }}
        )
        
        # Step 4: Filter event based on StageId and path pattern
        should_process, filter_reason = should_process_event(stage_id, object_key)
        
        if not should_process:
            logger.info(
                f"Event filtered out: {filter_reason}",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'objectKey': object_key,
                    'stageId': stage_id,
                    'originPath': origin_path,
                    'filterReason': filter_reason
                }}
            )
            return {
                'success': True,
                'message': f'Event filtered: {filter_reason}',
                'metadata': metadata
            }
        
        # Step 5: Send valid event to SQS queue
        try:
            message_id = send_event_to_queue(
                queue_url=queue_url,
                bucket_name=bucket_name,
                object_key=object_key,
                origin_path=origin_path,
                stage_id=stage_id,
                event_time=event_time,
                event_type=event_type
            )
            
            logger.info(
                "Successfully queued event for processing",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'objectKey': object_key,
                    'stageId': stage_id,
                    'originPath': origin_path,
                    'messageId': message_id
                }}
            )
            
        except SQSClientError as e:
            logger.error(
                f"Failed to send event to SQS: {str(e)}",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'objectKey': object_key,
                    'stageId': stage_id,
                    'originPath': origin_path,
                    'error': str(e)
                }}
            )
            raise
        
        # Step 6: Check and create aggregation window
        try:
            active_window = check_active_window()
            
            if active_window:
                logger.info(
                    "Active aggregation window exists, skipping schedule creation",
                    extra={'extra_fields': {
                        'windowId': active_window.get('windowId'),
                        'scheduleArn': active_window.get('scheduleArn'),
                        'windowStartTime': active_window.get('windowStartTime'),
                        'windowEndTime': active_window.get('windowEndTime')
                    }}
                )
            else:
                # No active window, create a new schedule
                logger.info("No active window found, creating new schedule")
                
                schedule_arn = create_one_time_schedule()
                
                if schedule_arn:
                    # Create window tracking record
                    window_created = create_window(schedule_arn)
                    
                    if window_created:
                        logger.info(
                            "Successfully created aggregation window and schedule",
                            extra={'extra_fields': {
                                'scheduleArn': schedule_arn
                            }}
                        )
                    else:
                        logger.info(
                            "Window creation skipped (race condition - another invocation created it)",
                            extra={'extra_fields': {
                                'scheduleArn': schedule_arn
                            }}
                        )
                else:
                    logger.warning("Failed to create schedule, but event was queued successfully")
                    
        except Exception as e:
            # Log error but don't fail the entire operation
            # The event is already queued, so it will be processed
            logger.error(
                f"Error managing aggregation window: {str(e)}",
                extra={'extra_fields': {
                    'error': str(e),
                    'bucketName': bucket_name,
                    'objectKey': object_key
                }}
            )
            # Continue - window management is best-effort
        
        return {
            'success': True,
            'message': 'Event processed successfully',
            'metadata': {
                'bucketName': bucket_name,
                'objectKey': object_key,
                'stageId': stage_id,
                'originPath': origin_path,
                'eventType': event_type
            }
        }
        
    except S3EventParseError as e:
        logger.error(
            f"Failed to parse S3 event: {str(e)}",
            extra={'extra_fields': {
                'error': str(e),
                'record': record
            }}
        )
        return {
            'success': False,
            'message': f'Parse error: {str(e)}'
        }
    
    except Exception as e:
        logger.error(
            f"Unexpected error processing S3 event: {str(e)}",
            extra={'extra_fields': {
                'error': str(e),
                'record': record
            }}
        )
        return {
            'success': False,
            'message': f'Processing error: {str(e)}'
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for S3 event ingestion.
    
    Processes S3 object-change events, filters them, queues valid events,
    and manages aggregation window scheduling.
    
    Args:
        event: S3 Event Notification containing Records array
        context: Lambda context object
        
    Returns:
        Dictionary containing:
            - statusCode: HTTP status code (200 for success, 500 for failure)
            - body: Summary of processing results
    """
    logger.info(
        "Ingestor Lambda invoked",
        extra={'extra_fields': {
            'requestId': context.aws_request_id if context else 'unknown',
            'recordCount': len(event.get('Records', []))
        }}
    )
    
    try:
        # Get queue URL from environment
        queue_url = get_queue_url()
        
        # Process each S3 event record
        records = event.get('Records', [])
        
        if not records:
            logger.warning("No records found in event")
            return {
                'statusCode': 200,
                'body': 'No records to process'
            }
        
        results = []
        for record in records:
            result = process_s3_record(record, queue_url)
            results.append(result)
        
        # Summarize results
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        logger.info(
            "Ingestor Lambda completed",
            extra={'extra_fields': {
                'totalRecords': len(results),
                'successful': successful,
                'failed': failed
            }}
        )
        
        # Return success if at least one record was processed successfully
        if successful > 0:
            return {
                'statusCode': 200,
                'body': f'Processed {successful} of {len(results)} records successfully'
            }
        else:
            return {
                'statusCode': 500,
                'body': f'Failed to process all {len(results)} records'
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
