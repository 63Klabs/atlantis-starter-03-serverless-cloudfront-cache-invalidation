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
import logging

# Lambda layer import handling
def setup_imports():
    """Setup imports from Lambda layer with fallbacks."""
    # Add common layer paths to Python path
    layer_paths = ['/opt/python', '/opt/python/lib/python3.14/site-packages']
    for path in layer_paths:
        if path not in sys.path and os.path.exists(path):
            sys.path.insert(0, path)
    
    # Try to import from common layer
    try:
        from common.logger import setup_logger
        return setup_logger
    except ImportError as e:
        print(f"Failed to import from common layer: {e}")
        print(f"Python path: {sys.path}")
        print(f"Available paths: {[p for p in sys.path if os.path.exists(p)]}")
        
        # Fallback logger setup
        def setup_logger(name):
            logger = logging.getLogger(name)
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            return logger
        return setup_logger

# Initialize logger setup function
setup_logger = setup_imports()
from .event_parser import (
    extract_event_metadata,
    extract_stage_id,
    extract_origin_path,
    S3EventParseError
)
from .event_filter import should_process_event
from .queue_client import send_event_to_queue, SQSClientError
from .window_tracker import check_active_window, create_window
from .scheduler_client import create_one_time_schedule

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
        # DEBUG: Log raw record before parsing
        logger.info(
            "Step 1: Parsing S3 event metadata DEBUG",
            extra={'extra_fields': {
                'rawRecord': record,
                'recordKeys': list(record.keys()) if isinstance(record, dict) else 'not_dict'
            }}
        )
        
        metadata = extract_event_metadata(record)
        
        # DEBUG: Log extracted metadata
        logger.info(
            "Step 1: Metadata extraction result DEBUG",
            extra={'extra_fields': {
                'extractedMetadata': metadata,
                'metadataKeys': list(metadata.keys()) if isinstance(metadata, dict) else 'not_dict'
            }}
        )
        
        bucket_name = metadata['bucketName']
        object_key = metadata['objectKey']
        event_time = metadata['eventTime']
        event_type = metadata['eventType']
        
        # Step 2: Extract StageId and origin path
        # DEBUG: Log extraction process
        logger.info(
            "Step 2: Extracting StageId and origin path DEBUG",
            extra={'extra_fields': {
                'objectKey': object_key,
                'objectKeyLength': len(object_key),
                'objectKeyParts': object_key.split('/') if '/' in object_key else [object_key]
            }}
        )
        
        stage_id = extract_stage_id(object_key)
        origin_path = extract_origin_path(object_key)
        
        # DEBUG: Log extraction results
        logger.info(
            "Step 2: Extraction results DEBUG",
            extra={'extra_fields': {
                'extractedStageId': stage_id,
                'extractedOriginPath': origin_path,
                'stageIdType': type(stage_id).__name__,
                'originPathType': type(origin_path).__name__
            }}
        )
        
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
        # DEBUG: Log filtering process
        logger.info(
            "Step 4: Event filtering DEBUG",
            extra={'extra_fields': {
                'filterInputStageId': stage_id,
                'filterInputObjectKey': object_key,
                'aboutToCallShouldProcessEvent': True
            }}
        )
        
        should_process, filter_reason = should_process_event(stage_id, object_key)
        
        # DEBUG: Log filtering results
        logger.info(
            "Step 4: Filtering results DEBUG",
            extra={'extra_fields': {
                'shouldProcess': should_process,
                'filterReason': filter_reason,
                'filterReasonType': type(filter_reason).__name__
            }}
        )
        
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
            # DEBUG: Log SQS send attempt
            logger.info(
                "Step 5: Sending event to SQS DEBUG",
                extra={'extra_fields': {
                    'sqsQueueUrl': queue_url,
                    'sqsMessageData': {
                        'bucketName': bucket_name,
                        'objectKey': object_key,
                        'originPath': origin_path,
                        'stageId': stage_id,
                        'eventTime': event_time,
                        'eventType': event_type
                    }
                }}
            )
            
            message_id = send_event_to_queue(
                queue_url=queue_url,
                bucket_name=bucket_name,
                object_key=object_key,
                origin_path=origin_path,
                stage_id=stage_id,
                event_time=event_time,
                event_type=event_type
            )
            
            # DEBUG: Log SQS response
            logger.info(
                "Step 5: SQS send result DEBUG",
                extra={'extra_fields': {
                    'sqsMessageId': message_id,
                    'sqsMessageIdType': type(message_id).__name__,
                    'sqsSendSuccessful': True
                }}
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
            # DEBUG: Log window check attempt
            logger.info(
                "Step 6: Checking for active aggregation window DEBUG",
                extra={'extra_fields': {
                    'aboutToCallCheckActiveWindow': True
                }}
            )
            
            active_window = check_active_window()
            
            # DEBUG: Log window check result
            logger.info(
                "Step 6: Active window check result DEBUG",
                extra={'extra_fields': {
                    'activeWindow': active_window,
                    'activeWindowType': type(active_window).__name__,
                    'activeWindowExists': bool(active_window),
                    'activeWindowKeys': list(active_window.keys()) if isinstance(active_window, dict) else 'not_dict'
                }}
            )
            
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
                logger.info(
                    "Step 6: No active window found, creating new schedule DEBUG",
                    extra={'extra_fields': {
                        'aboutToCallCreateOneTimeSchedule': True
                    }}
                )
                
                schedule_arn = create_one_time_schedule()
                
                # DEBUG: Log schedule creation result
                logger.info(
                    "Step 6: Schedule creation result DEBUG",
                    extra={'extra_fields': {
                        'scheduleArn': schedule_arn,
                        'scheduleArnType': type(schedule_arn).__name__,
                        'scheduleCreated': bool(schedule_arn)
                    }}
                )
                
                if schedule_arn:
                    # DEBUG: Log window creation attempt
                    logger.info(
                        "Step 6: Creating window tracking record DEBUG",
                        extra={'extra_fields': {
                            'scheduleArnForWindow': schedule_arn,
                            'aboutToCallCreateWindow': True
                        }}
                    )
                    
                    # Create window tracking record
                    window_created = create_window(schedule_arn)
                    
                    # DEBUG: Log window creation result
                    logger.info(
                        "Step 6: Window creation result DEBUG",
                        extra={'extra_fields': {
                            'windowCreated': window_created,
                            'windowCreatedType': type(window_created).__name__,
                            'scheduleArn': schedule_arn
                        }}
                    )
                    
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
                    logger.warning(
                        "Failed to create schedule, but event was queued successfully DEBUG",
                        extra={'extra_fields': {
                            'scheduleCreationFailed': True,
                            'scheduleArnResult': schedule_arn
                        }}
                    )
                    
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
    # DEBUG: Log the complete incoming event
    logger.info(
        "Ingestor Lambda invoked - FULL EVENT DEBUG",
        extra={'extra_fields': {
            'requestId': context.aws_request_id if context else 'unknown',
            'recordCount': len(event.get('Records', [])),
            'fullEvent': event,
            'contextInfo': {
                'functionName': context.function_name if context else 'unknown',
                'functionVersion': context.function_version if context else 'unknown',
                'memoryLimitInMB': context.memory_limit_in_mb if context else 'unknown',
                'remainingTimeInMillis': context.get_remaining_time_in_millis() if context else 'unknown'
            }
        }}
    )
    
    try:
        # Get queue URL from environment
        queue_url = get_queue_url()
        
        # DEBUG: Log environment variables and configuration
        logger.info(
            "Environment configuration DEBUG",
            extra={'extra_fields': {
                'queueUrl': queue_url,
                'allEnvVars': dict(os.environ),
                'pythonPath': sys.path[:3]  # First 3 entries to avoid too much noise
            }}
        )
        
        # Process each S3 event record
        records = event.get('Records', [])
        
        # DEBUG: Log detailed record information
        logger.info(
            "Records analysis DEBUG",
            extra={'extra_fields': {
                'recordCount': len(records),
                'recordTypes': [record.get('eventSource', 'unknown') for record in records],
                'recordEventNames': [record.get('eventName', 'unknown') for record in records]
            }}
        )
        
        if not records:
            logger.warning("No records found in event - DEBUG: This means no S3 events to process")
            return {
                'statusCode': 200,
                'body': 'No records to process'
            }
        
        results = []
        for i, record in enumerate(records):
            # DEBUG: Log each record before processing
            logger.info(
                f"Processing record {i+1}/{len(records)} DEBUG",
                extra={'extra_fields': {
                    'recordIndex': i,
                    'fullRecord': record,
                    'recordEventSource': record.get('eventSource'),
                    'recordEventName': record.get('eventName'),
                    'recordEventTime': record.get('eventTime'),
                    's3Info': record.get('s3', {})
                }}
            )
            
            result = process_s3_record(record, queue_url)
            
            # DEBUG: Log processing result
            logger.info(
                f"Record {i+1} processing result DEBUG",
                extra={'extra_fields': {
                    'recordIndex': i,
                    'processingResult': result
                }}
            )
            
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