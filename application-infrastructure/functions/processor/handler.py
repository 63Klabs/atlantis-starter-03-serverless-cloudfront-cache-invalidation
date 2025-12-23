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
from typing import Dict, Any, List, Tuple

# Import from Lambda layer
from common.logger import setup_logger # pyright: ignore[reportMissingImports]
from common.window_tracker import close_window # pyright: ignore[reportMissingImports]
from common.constants import DIRECTORY_CONSOLIDATION_THRESHOLD, CONSOLIDATION_STOP_LEVEL, SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD # pyright: ignore[reportMissingImports]

# Import function-specific modules (compatible with both Lambda and test environments)
try:
    # Lambda environment - files are at root level
    from queue_client import receive_messages_batch, delete_messages_batch
    from tag_validator import validate_bucket_tags, get_bucket_tags, validate_distribution_tags, get_bucket_consolidation_config
    from distribution_finder import find_matching_distributions
    from path_consolidator import consolidate_paths
    from invalidation_client import create_invalidation
except ImportError:
    # Development/test environment - use relative imports
    from .queue_client import receive_messages_batch, delete_messages_batch
    from .tag_validator import validate_bucket_tags, get_bucket_tags, validate_distribution_tags, get_bucket_consolidation_config
    from .distribution_finder import find_matching_distributions
    from .path_consolidator import consolidate_paths
    from .invalidation_client import create_invalidation

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
    # DEBUG: Log grouping function entry
    logger.info(
        "Starting message grouping DEBUG",
        extra={'extra_fields': {
            'totalMessages': len(messages),
            'messageTypes': [type(msg).__name__ for msg in messages[:5]],  # First 5 types
            'messageKeys': [list(msg.keys()) if isinstance(msg, dict) else 'not_dict' for msg in messages[:3]]  # First 3 key sets
        }}
    )
    
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    skipped_messages = []
    
    for i, message in enumerate(messages):
        # DEBUG: Log each message processing
        logger.info(
            f"Processing message {i+1}/{len(messages)} for grouping DEBUG",
            extra={'extra_fields': {
                'messageIndex': i,
                'messageId': message.get('MessageId', 'no_id'),
                'messageKeys': list(message.keys()) if isinstance(message, dict) else 'not_dict',
                'hasParsedBody': 'parsed_body' in message if isinstance(message, dict) else False
            }}
        )
        
        # Extract parsed body
        parsed_body = message.get('parsed_body', {})
        
        # DEBUG: Log parsed body analysis
        logger.info(
            f"Message {i+1} parsed body analysis DEBUG",
            extra={'extra_fields': {
                'messageIndex': i,
                'parsedBody': parsed_body,
                'parsedBodyType': type(parsed_body).__name__,
                'parsedBodyKeys': list(parsed_body.keys()) if isinstance(parsed_body, dict) else 'not_dict'
            }}
        )
        
        # Get grouping keys
        bucket_name = parsed_body.get('bucketName')
        origin_path = parsed_body.get('originPath')
        
        # DEBUG: Log grouping key extraction
        logger.info(
            f"Message {i+1} grouping keys DEBUG",
            extra={'extra_fields': {
                'messageIndex': i,
                'bucketName': bucket_name,
                'originPath': origin_path,
                'bucketNameType': type(bucket_name).__name__,
                'originPathType': type(origin_path).__name__,
                'hasBucket': bool(bucket_name),
                'hasOrigin': bool(origin_path)
            }}
        )
        
        # Skip messages with missing required fields
        if not bucket_name or not origin_path:
            skip_info = {
                'message_id': message.get('MessageId'),
                'has_bucket': bool(bucket_name),
                'has_origin': bool(origin_path),
                'bucket_value': bucket_name,
                'origin_value': origin_path
            }
            skipped_messages.append(skip_info)
            
            logger.warning(
                f"Skipping message {i+1} with missing bucketName or originPath DEBUG",
                extra={'extra_fields': skip_info}
            )
            continue
        
        # Create group key
        group_key = (bucket_name, origin_path)
        
        # DEBUG: Log group assignment
        logger.info(
            f"Message {i+1} group assignment DEBUG",
            extra={'extra_fields': {
                'messageIndex': i,
                'groupKey': group_key,
                'groupExists': group_key in grouped,
                'currentGroupSize': len(grouped.get(group_key, []))
            }}
        )
        
        # Add message to group
        if group_key not in grouped:
            grouped[group_key] = []
        
        grouped[group_key].append(message)
    
    # DEBUG: Log final grouping results
    logger.info(
        f"Message grouping complete DEBUG",
        extra={'extra_fields': {
            'total_messages': len(messages),
            'messages_grouped': len(messages) - len(skipped_messages),
            'messages_skipped': len(skipped_messages),
            'skipped_details': skipped_messages,
            'group_count': len(grouped),
            'groups_detailed': [
                {
                    'bucket': bucket,
                    'origin': origin,
                    'message_count': len(msgs),
                    'message_ids': [msg.get('MessageId', 'no_id') for msg in msgs]
                }
                for (bucket, origin), msgs in grouped.items()
            ]
        }}
    )
    
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
    # DEBUG: Log the complete incoming event and context
    logger.info(
        "Processor Lambda invoked - FULL EVENT DEBUG",
        extra={'extra_fields': {
            'requestId': context.aws_request_id if context else 'unknown',
            'fullEvent': event,
            'eventKeys': list(event.keys()) if isinstance(event, dict) else 'not_dict',
            'contextInfo': {
                'functionName': context.function_name if context else 'unknown',
                'functionVersion': context.function_version if context else 'unknown',
                'memoryLimitInMB': context.memory_limit_in_mb if context else 'unknown',
                'remainingTimeInMillis': context.get_remaining_time_in_millis() if context else 'unknown'
            },
            'environmentVars': dict(os.environ)
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
        
        # DEBUG: Log configuration
        logger.info(
            "Processor configuration DEBUG",
            extra={'extra_fields': {
                'queueUrl': queue_url,
                'hasQueueUrl': bool(queue_url),
                'allEnvVars': dict(os.environ)
            }}
        )
        
        if not queue_url:
            raise ValueError("QUEUE_URL environment variable not set")
        
        # Step 1: Receive messages from SQS in batches
        all_messages = []
        batch_count = 0
        
        # DEBUG: Log batch retrieval start
        logger.info(
            "Step 1: Starting SQS batch message retrieval DEBUG",
            extra={'extra_fields': {
                'queueUrl': queue_url,
                'startingBatchRetrieval': True
            }}
        )
        
        # Continue receiving until queue is empty
        while True:
            batch_count += 1
            
            # DEBUG: Log each batch attempt
            logger.info(
                f"Step 1: Batch {batch_count} retrieval attempt DEBUG",
                extra={'extra_fields': {
                    'batchNumber': batch_count,
                    'currentMessageCount': len(all_messages),
                    'aboutToCallReceiveMessagesBatch': True
                }}
            )
            
            messages = receive_messages_batch(queue_url)
            
            # DEBUG: Log batch result
            logger.info(
                f"Step 1: Batch {batch_count} result DEBUG",
                extra={'extra_fields': {
                    'batchNumber': batch_count,
                    'messagesReceived': len(messages) if messages else 0,
                    'messagesType': type(messages).__name__,
                    'messageIds': [msg.get('MessageId', 'no_id') for msg in messages] if messages else [],
                    'totalMessagesNow': len(all_messages) + (len(messages) if messages else 0)
                }}
            )
            
            if not messages:
                # Queue is empty
                logger.info(
                    f"Step 1: Queue empty after {batch_count} batches DEBUG",
                    extra={'extra_fields': {
                        'totalBatches': batch_count,
                        'finalMessageCount': len(all_messages),
                        'queueEmpty': True
                    }}
                )
                break
            
            all_messages.extend(messages)
            
            # Safety limit to prevent infinite loops
            if len(all_messages) >= 1000:
                logger.warning(
                    "Reached message limit, stopping batch retrieval DEBUG",
                    extra={'extra_fields': {
                        'message_count': len(all_messages),
                        'batchCount': batch_count,
                        'hitSafetyLimit': True
                    }}
                )
                break
        
        summary['total_messages'] = len(all_messages)
        
        # DEBUG: Log message retrieval summary
        logger.info(
            "Step 1: Message retrieval complete DEBUG",
            extra={'extra_fields': {
                'totalMessages': len(all_messages),
                'totalBatches': batch_count,
                'messageDetails': [
                    {
                        'messageId': msg.get('MessageId', 'no_id'),
                        'receiptHandle': msg.get('ReceiptHandle', 'no_handle')[:50] + '...' if msg.get('ReceiptHandle') else 'no_handle',
                        'body': msg.get('Body', 'no_body')[:200] + '...' if msg.get('Body') else 'no_body',
                        'parsedBody': msg.get('parsed_body', 'no_parsed_body')
                    }
                    for msg in all_messages[:5]  # First 5 messages for debugging
                ]
            }}
        )
        
        if not all_messages:
            logger.info(
                "No messages to process - closing window DEBUG",
                extra={'extra_fields': {
                    'noMessagesToProcess': True,
                    'aboutToCloseWindow': True
                }}
            )
            
            # Close aggregation window even if no messages
            try:
                close_window()
                logger.info("Window closed successfully with no messages DEBUG")
            except Exception as e:
                logger.error(
                    f"Failed to close aggregation window: {str(e)} DEBUG",
                    extra={'extra_fields': {
                        'error': str(e),
                        'windowCloseFailed': True
                    }}
                )
            
            return {
                'statusCode': 200,
                'body': 'No messages to process'
            }
        
        logger.info(
            f"Retrieved {len(all_messages)} messages from queue - proceeding to grouping DEBUG",
            extra={'extra_fields': {
                'message_count': len(all_messages),
                'proceedingToGrouping': True
            }}
        )
        
        # Step 2: Group messages by bucket and origin path
        # DEBUG: Log grouping start
        logger.info(
            "Step 2: Starting message grouping DEBUG",
            extra={'extra_fields': {
                'totalMessagesToGroup': len(all_messages),
                'aboutToCallGroupMessages': True
            }}
        )
        
        grouped_messages = group_messages_by_bucket_and_origin(all_messages)
        summary['groups_processed'] = len(grouped_messages)
        
        # DEBUG: Log grouping results
        logger.info(
            "Step 2: Message grouping complete DEBUG",
            extra={'extra_fields': {
                'totalGroups': len(grouped_messages),
                'groupDetails': [
                    {
                        'bucketName': bucket,
                        'originPath': origin,
                        'messageCount': len(msgs),
                        'messageIds': [msg.get('MessageId', 'no_id') for msg in msgs[:3]]  # First 3 IDs
                    }
                    for (bucket, origin), msgs in grouped_messages.items()
                ]
            }}
        )
        
        # Track messages to delete (successfully processed)
        messages_to_delete = []
        
        # Step 3-8: Process each group
        group_index = 0
        for (bucket_name, origin_path), messages in grouped_messages.items():
            group_index += 1
            
            # DEBUG: Log group processing start
            logger.info(
                f"Step 3-8: Processing group {group_index}/{len(grouped_messages)} DEBUG",
                extra={'extra_fields': {
                    'groupIndex': group_index,
                    'totalGroups': len(grouped_messages),
                    'bucket_name': bucket_name,
                    'origin_path': origin_path,
                    'message_count': len(messages),
                    'messageIds': [msg.get('MessageId', 'no_id') for msg in messages],
                    'firstMessageBody': messages[0].get('parsed_body', {}) if messages else {}
                }}
            )
            
            # Step 3: Validate bucket tags
            # DEBUG: Log bucket validation start
            logger.info(
                f"Step 3: Validating bucket tags for {bucket_name} DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'aboutToCallValidateBucketTags': True
                }}
            )
            
            bucket_validation_result = validate_bucket_tags(bucket_name)
            
            # DEBUG: Log bucket validation result
            logger.info(
                f"Step 3: Bucket validation result DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'validationResult': bucket_validation_result,
                    'validationPassed': bool(bucket_validation_result)
                }}
            )
            
            if not bucket_validation_result:
                logger.warning(
                    f"Bucket {bucket_name} failed tag validation, skipping DEBUG",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path,
                        'bucketValidationFailed': True,
                        'messagesBeingDeleted': len(messages)
                    }}
                )
                summary['buckets_rejected'] += 1
                # Still delete messages for rejected buckets (they were processed, just rejected)
                messages_to_delete.extend(messages)
                continue
            
            summary['buckets_validated'] += 1
            
            # DEBUG: Log bucket validation success
            logger.info(
                f"Step 3: Bucket {bucket_name} validation passed DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'bucketValidationPassed': True
                }}
            )
            
            # Get bucket's Application tag for distribution validation
            # DEBUG: Log bucket tags retrieval
            logger.info(
                f"Step 3: Getting bucket tags for {bucket_name} DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'aboutToCallGetBucketTags': True
                }}
            )
            
            bucket_tags = get_bucket_tags(bucket_name)
            
            # DEBUG: Log bucket tags result
            logger.info(
                f"Step 3: Bucket tags retrieval result DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'bucketTags': bucket_tags,
                    'bucketTagsType': type(bucket_tags).__name__,
                    'bucketTagsKeys': list(bucket_tags.keys()) if isinstance(bucket_tags, dict) else 'not_dict',
                    'hasApplicationTag': 'atlantis:Application' in bucket_tags if isinstance(bucket_tags, dict) else False
                }}
            )
            
            if not bucket_tags:
                logger.error(
                    f"Failed to retrieve bucket tags for {bucket_name}, skipping DEBUG",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path,
                        'bucketTagsRetrievalFailed': True
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            bucket_app_tag = bucket_tags.get('atlantis:Application', '')
            
            # DEBUG: Log application tag extraction
            logger.info(
                f"Step 3: Application tag extraction DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'bucketAppTag': bucket_app_tag,
                    'hasAppTag': bool(bucket_app_tag)
                }}
            )
            
            if not bucket_app_tag:
                logger.warning(
                    f"Bucket {bucket_name} missing atlantis:Application tag, skipping DEBUG",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path,
                        'missingApplicationTag': True,
                        'availableTags': list(bucket_tags.keys())
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Extract stageId from first message (all messages in group have same stageId)
            # DEBUG: Log stageId extraction
            first_message = messages[0] if messages else {}
            parsed_body = first_message.get('parsed_body', {})
            stage_id = parsed_body.get('stageId', '')
            
            logger.info(
                f"Step 3: StageId extraction DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'firstMessage': first_message,
                    'parsedBody': parsed_body,
                    'extractedStageId': stage_id,
                    'hasStageId': bool(stage_id)
                }}
            )
            
            if not stage_id:
                logger.error(
                    f"Missing stageId in messages for bucket {bucket_name}, skipping DEBUG",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path,
                        'missingStageId': True,
                        'firstMessageParsedBody': parsed_body
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Step 4: Find matching CloudFront distributions
            # DEBUG: Log distribution search
            logger.info(
                f"Step 4: Finding CloudFront distributions DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'originPath': origin_path,
                    'aboutToCallFindMatchingDistributions': True
                }}
            )
            
            distribution_ids = find_matching_distributions(bucket_name, origin_path)
            
            # DEBUG: Log distribution search results
            logger.info(
                f"Step 4: Distribution search results DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'originPath': origin_path,
                    'distributionIds': distribution_ids,
                    'distributionCount': len(distribution_ids) if distribution_ids else 0,
                    'distributionsFound': bool(distribution_ids)
                }}
            )
            
            if not distribution_ids:
                logger.info(
                    f"No distributions found for bucket {bucket_name} with origin {origin_path} DEBUG",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'origin_path': origin_path,
                        'noDistributionsFound': True,
                        'messagesBeingDeleted': len(messages)
                    }}
                )
                # Delete messages even if no distributions found
                messages_to_delete.extend(messages)
                continue
            
            summary['distributions_found'] += len(distribution_ids)
            
            # DEBUG: Log distributions found
            logger.info(
                f"Step 4: Found {len(distribution_ids)} distributions DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'originPath': origin_path,
                    'distributionIds': distribution_ids,
                    'distributionCount': len(distribution_ids)
                }}
            )
            
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
            
            # Step 6: Get bucket-specific consolidation configuration
            # DEBUG: Log configuration resolution start
            logger.info(
                f"Step 6: Resolving consolidation configuration for bucket {bucket_name} DEBUG",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'aboutToCallGetBucketConsolidationConfig': True
                }}
            )
            
            try:
                bucket_config = get_bucket_consolidation_config(bucket_name)
                
                # DEBUG: Log configuration resolution result
                logger.info(
                    f"Step 6: Consolidation configuration resolved DEBUG",
                    extra={'extra_fields': {
                        'bucketName': bucket_name,
                        'bucketConfig': bucket_config,
                        'configResolutionSuccessful': True
                    }}
                )
                
                # Log effective configuration being used for this bucket
                logger.info(
                    f"Using consolidation configuration for bucket {bucket_name}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'directory_threshold': bucket_config['directory_threshold'],
                        'stop_level': bucket_config['stop_level'],
                        'directory_threshold_source': bucket_config['directory_threshold_source'],
                        'stop_level_source': bucket_config['stop_level_source'],
                        'operation': 'consolidation_config_applied'
                    }}
                )
                
            except Exception as e:
                # Error handling: fall back to default configuration gracefully
                logger.error(
                    f"Failed to resolve consolidation configuration for bucket {bucket_name}, using defaults: {str(e)}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'error': str(e),
                        'fallback_directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
                        'fallback_stop_level': CONSOLIDATION_STOP_LEVEL,
                        'fallback_reason': 'config_resolution_error'
                    }}
                )
                
                # Use default configuration
                bucket_config = {
                    'directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
                    'stop_level': CONSOLIDATION_STOP_LEVEL,
                    'sibling_directory_threshold': SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
                    'directory_threshold_source': 'default_fallback',
                    'stop_level_source': 'default_fallback',
                    'sibling_directory_threshold_source': 'default_fallback'
                }
            
            # Step 7: Extract and consolidate paths
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
                        
                        # DEBUG: Log path construction
                        logger.debug(
                            f"Constructed invalidation path DEBUG",
                            extra={'extra_fields': {
                                'bucket_name': bucket_name,
                                'object_key': object_key,
                                'origin_path': origin_path,
                                'relative_path': relative_path,
                                'object_key_starts_with_origin': object_key.startswith(origin_path),
                                'relative_path_starts_with_slash': relative_path.startswith('/')
                            }}
                        )
                        
                        object_paths.append(relative_path)
                    else:
                        # Fallback: use full object key with leading slash
                        fallback_path = object_key if object_key.startswith('/') else '/' + object_key
                        
                        # DEBUG: Log fallback path construction
                        logger.debug(
                            f"Using fallback path construction DEBUG",
                            extra={'extra_fields': {
                                'bucket_name': bucket_name,
                                'object_key': object_key,
                                'origin_path': origin_path,
                                'fallback_path': fallback_path,
                                'object_key_starts_with_origin': object_key.startswith(origin_path)
                            }}
                        )
                        
                        object_paths.append(fallback_path)
            
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
            
            # DEBUG: Log paths before consolidation
            logger.info(
                f"Paths before consolidation DEBUG",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'origin_path': origin_path,
                    'path_count': len(object_paths),
                    'paths': object_paths[:20] if len(object_paths) > 20 else object_paths  # Log first 20 paths
                }}
            )
            
            # Consolidate paths with bucket-specific configuration
            consolidated_path_chunks = consolidate_paths(
                object_paths,
                directory_threshold=bucket_config['directory_threshold'],
                stop_level=bucket_config['stop_level'],
                sibling_threshold=bucket_config['sibling_directory_threshold']
            )
            
            # DEBUG: Log paths after consolidation
            logger.info(
                f"Paths after consolidation DEBUG",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'origin_path': origin_path,
                    'chunk_count': len(consolidated_path_chunks),
                    'consolidated_chunks': [chunk[:10] for chunk in consolidated_path_chunks]  # Log first 10 paths per chunk
                }}
            )
            
            # Step 8: Submit invalidations for each valid distribution
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
        
        # Step 9: Delete processed messages from SQS
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
        
        # Step 10: Close aggregation window
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