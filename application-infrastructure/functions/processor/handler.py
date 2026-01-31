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
from common.path_utils import extract_stage_from_path # pyright: ignore[reportMissingImports]

# Import function-specific modules (compatible with both Lambda and test environments)
try:
    # Lambda environment - files are at root level
    from queue_client import receive_messages_batch, delete_messages_batch
    from tag_validator import validate_bucket_tags, get_bucket_tags, validate_distribution_tags, get_bucket_consolidation_config, validate_bucket_tags_from_dict, get_bucket_consolidation_config_from_dict
    from distribution_finder import find_matching_distributions
    from path_consolidator import consolidate_paths
    from invalidation_client import create_invalidation
    from pattern_resolver import resolve_bucket_pattern, filter_events_by_pattern
except ImportError:
    # Development/test environment - use relative imports
    from .queue_client import receive_messages_batch, delete_messages_batch
    from .tag_validator import validate_bucket_tags, get_bucket_tags, validate_distribution_tags, get_bucket_consolidation_config, validate_bucket_tags_from_dict, get_bucket_consolidation_config_from_dict
    from .distribution_finder import find_matching_distributions
    from .path_consolidator import consolidate_paths
    from .invalidation_client import create_invalidation
    from .pattern_resolver import resolve_bucket_pattern, filter_events_by_pattern

logger = setup_logger(__name__)


def group_messages_by_bucket(messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group SQS messages by bucketName only.
    
    Groups events by bucket to enable batch processing. Stage and origin path
    will be determined later from bucket tags after reading the bucket's
    OriginPathPattern tag.
    
    Args:
        messages: List of SQS messages with parsed_body containing:
            - bucketName: S3 bucket name
            - objectKey: Full S3 object key
            - eventTime: ISO 8601 timestamp
            - eventType: S3 event type
            
    Returns:
        Dictionary where:
            - Keys are bucket names (strings)
            - Values are lists of messages belonging to that bucket
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 12: Event grouping by bucket**
    """
    logger.info(
        "Starting message grouping by bucket",
        extra={'extra_fields': {
            'totalMessages': len(messages)
        }}
    )
    
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    skipped_messages = []
    
    for i, message in enumerate(messages):
        # Extract parsed body
        parsed_body = message.get('parsed_body', {})
        
        # Get bucket name
        bucket_name = parsed_body.get('bucketName')
        
        # Skip messages with missing bucket name
        if not bucket_name:
            skip_info = {
                'message_id': message.get('MessageId'),
                'reason': 'missing_bucket_name'
            }
            skipped_messages.append(skip_info)
            
            logger.warning(
                f"Skipping message {i+1} with missing bucketName",
                extra={'extra_fields': skip_info}
            )
            continue
        
        # Add message to bucket group
        if bucket_name not in grouped:
            grouped[bucket_name] = []
        
        grouped[bucket_name].append(message)
    
    logger.info(
        f"Grouped {len(messages)} messages into {len(grouped)} bucket(s)",
        extra={'extra_fields': {
            'total_messages': len(messages),
            'messages_skipped': len(skipped_messages),
            'bucket_count': len(grouped),
            'buckets': [
                {
                    'bucket': bucket,
                    'message_count': len(msgs)
                }
                for bucket, msgs in grouped.items()
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
        "Processor Lambda invoked - FULL EVENT",
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
            "Processor configuration",
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
            "Step 1: Starting SQS batch message retrieval",
            extra={'extra_fields': {
                'queueUrl': queue_url,
                'startingBatchRetrieval': True
            }}
        )
        
        # Continue receiving until queue is empty
        while True:
            batch_count += 1
            
            # DEBUG: Log each batch attempt
            # logger.info(
            #     f"Step 1: Batch {batch_count} retrieval attempt DEBUG",
            #     extra={'extra_fields': {
            #         'batchNumber': batch_count,
            #         'currentMessageCount': len(all_messages),
            #         'aboutToCallReceiveMessagesBatch': True
            #     }}
            # )
            
            messages = receive_messages_batch(queue_url)
            
            # DEBUG: Log batch result
            logger.info(
                f"Step 1: Batch {batch_count} result",
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
                    f"Step 1: Queue empty after {batch_count} batches",
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
                    "Reached message limit, stopping batch retrieval",
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
            "Step 1: Message retrieval complete",
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
                "No messages to process - closing window",
                extra={'extra_fields': {
                    'noMessagesToProcess': True,
                    'aboutToCloseWindow': True
                }}
            )
            
            # Close aggregation window even if no messages
            try:
                close_window()
                logger.info("Window closed successfully with no messages")
            except Exception as e:
                logger.error(
                    f"Failed to close aggregation window: {str(e)}",
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
            f"Retrieved {len(all_messages)} messages from queue - proceeding to grouping",
            extra={'extra_fields': {
                'message_count': len(all_messages),
                'proceedingToGrouping': True
            }}
        )
        
        # Step 2: Group messages by bucket
        logger.info(
            "Step 2: Starting message grouping by bucket",
            extra={'extra_fields': {
                'totalMessagesToGroup': len(all_messages),
                'aboutToCallGroupMessages': True
            }}
        )
        
        grouped_messages = group_messages_by_bucket(all_messages)
        summary['groups_processed'] = len(grouped_messages)
        
        logger.info(
            "Step 2: Message grouping complete",
            extra={'extra_fields': {
                'totalBuckets': len(grouped_messages),
                'bucketDetails': [
                    {
                        'bucketName': bucket,
                        'messageCount': len(msgs),
                        'messageIds': [msg.get('MessageId', 'no_id') for msg in msgs[:3]]  # First 3 IDs
                    }
                    for bucket, msgs in grouped_messages.items()
                ]
            }}
        )
        
        # Track messages to delete (successfully processed)
        messages_to_delete = []
        
        # Step 3-8: Process each bucket group
        bucket_index = 0
        for bucket_name, messages in grouped_messages.items():
            bucket_index += 1
            
            logger.info(
                f"Step 3-8: Processing bucket {bucket_index}/{len(grouped_messages)}",
                extra={'extra_fields': {
                    'bucketIndex': bucket_index,
                    'totalBuckets': len(grouped_messages),
                    'bucket_name': bucket_name,
                    'message_count': len(messages),
                    'messageIds': [msg.get('MessageId', 'no_id') for msg in messages]
                }}
            )
            
            # Step 3: Fetch bucket tags once (single API call per bucket)
            logger.info(
                f"Step 3: Fetching bucket tags for {bucket_name}",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'aboutToCallGetBucketTags': True
                }}
            )
            
            bucket_tags = get_bucket_tags(bucket_name)
            
            # Early exit if tag fetch fails
            if bucket_tags is None:
                logger.error(
                    f"Failed to retrieve bucket tags for {bucket_name}, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'bucketTagsRetrievalFailed': True,
                        'messagesBeingDeleted': len(messages)
                    }}
                )
                summary['buckets_rejected'] += 1
                messages_to_delete.extend(messages)
                continue
            
            logger.info(
                f"Successfully fetched {len(bucket_tags)} tags for bucket {bucket_name}",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'tagCount': len(bucket_tags),
                    'tagKeys': list(bucket_tags.keys())
                }}
            )
            
            # Step 3.1: Validate bucket tags from fetched dictionary
            logger.info(
                f"Step 3.1: Validating bucket tags for {bucket_name}",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'aboutToCallValidateBucketTagsFromDict': True
                }}
            )
            
            bucket_validation_result = validate_bucket_tags_from_dict(bucket_tags)
            
            logger.info(
                f"Step 3.1: Bucket validation result",
                extra={'extra_fields': {
                    'bucketName': bucket_name,
                    'validationResult': bucket_validation_result,
                    'validationPassed': bool(bucket_validation_result)
                }}
            )
            
            if not bucket_validation_result:
                logger.warning(
                    f"Bucket {bucket_name} failed tag validation, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'bucketValidationFailed': True,
                        'messagesBeingDeleted': len(messages)
                    }}
                )
                summary['buckets_rejected'] += 1
                # Still delete messages for rejected buckets (they were processed, just rejected)
                messages_to_delete.extend(messages)
                continue
            
            summary['buckets_validated'] += 1
            
            # Extract application tag from fetched tags
            bucket_app_tag = bucket_tags.get('atlantis:Application', '')
            
            if not bucket_app_tag:
                logger.warning(
                    f"Bucket {bucket_name} missing atlantis:Application tag, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'missingApplicationTag': True,
                        'availableTags': list(bucket_tags.keys())
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Step 3.5: Resolve bucket pattern
            # Get sample event path from first message
            first_message = messages[0] if messages else {}
            first_parsed_body = first_message.get('parsed_body', {})
            sample_event_path = first_parsed_body.get('objectKey', '')
            
            if not sample_event_path:
                logger.error(
                    f"Missing objectKey in first message for bucket {bucket_name}, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'missingObjectKey': True
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            # Resolve the bucket's origin path pattern
            bucket_pattern = resolve_bucket_pattern(bucket_name, sample_event_path)
            
            logger.info(
                f"Resolved bucket pattern for {bucket_name}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'bucket_pattern': bucket_pattern,
                    'sample_path': sample_event_path
                }}
            )
            
            # Step 3.6: Filter events by bucket pattern
            filtered_messages = filter_events_by_pattern(messages, bucket_pattern)
            
            if not filtered_messages:
                logger.info(
                    f"No events match bucket pattern for {bucket_name}, skipping",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'bucket_pattern': bucket_pattern,
                        'original_count': len(messages),
                        'filtered_count': 0
                    }}
                )
                messages_to_delete.extend(messages)
                continue
            
            logger.info(
                f"Filtered events by pattern: {len(messages)} -> {len(filtered_messages)}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'bucket_pattern': bucket_pattern,
                    'original_count': len(messages),
                    'filtered_count': len(filtered_messages)
                }}
            )
            
            # Step 3.7: Group filtered messages by stage
            # Now that we have the bucket pattern, we can extract stage from each message
            # and group them by stage for separate processing
            messages_by_stage: Dict[str, List[Dict[str, Any]]] = {}
            
            for message in filtered_messages:
                parsed_body = message.get('parsed_body', {})
                object_key = parsed_body.get('objectKey', '')
                
                # Extract stage from object key using the bucket pattern
                stage_id = extract_stage_from_path(object_key, bucket_pattern)
                
                # Group by stage
                if stage_id not in messages_by_stage:
                    messages_by_stage[stage_id] = []
                messages_by_stage[stage_id].append(message)
            
            logger.info(
                f"Grouped bucket {bucket_name} messages into {len(messages_by_stage)} stage(s)",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'bucket_pattern': bucket_pattern,
                    'stage_count': len(messages_by_stage),
                    'stages': [
                        {
                            'stage_id': stage,
                            'message_count': len(stage_msgs)
                        }
                        for stage, stage_msgs in messages_by_stage.items()
                    ]
                }}
            )
            
            # Step 4-8: Process each stage within this bucket
            for stage_id, stage_messages in messages_by_stage.items():
                logger.info(
                    f"Processing stage '{stage_id}' for bucket {bucket_name}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'stage_id': stage_id,
                        'message_count': len(stage_messages),
                        'bucket_pattern': bucket_pattern
                    }}
                )
                
                # Step 3.8: Resolve origin path for distribution lookup
                # IMPORTANT: The origin path for distribution lookup should match what's configured
                # in CloudFront. If the bucket pattern contains {stageId}, we need to substitute it
                # with the actual stage to match the CloudFront distribution's origin path.
                # For example: bucket_pattern="/{stageId}/public" + stage_id="prod" -> "/prod/public"
                
                # Resolve the origin path by substituting {stageId} in the bucket pattern
                if '{stageId}' in bucket_pattern:
                    if not stage_id:
                        logger.warning(
                            f"Pattern contains {{stageId}} but no stage found for bucket {bucket_name}, skipping stage group",
                            extra={'extra_fields': {
                                'bucket_name': bucket_name,
                                'bucket_pattern': bucket_pattern,
                                'operation': 'origin_path_resolution',
                                'skip_reason': 'missing_stage_id'
                            }}
                        )
                        # Still mark these messages for deletion
                        messages_to_delete.extend(stage_messages)
                        continue
                    resolved_origin_path = bucket_pattern.replace('{stageId}', stage_id)
                else:
                    # No stage placeholder, use the bucket pattern as-is
                    resolved_origin_path = bucket_pattern
                
                # Convert root path to empty string for CloudFront
                if resolved_origin_path == '/':
                    resolved_origin_path = ''
                
                logger.info(
                    f"Resolved origin path for distribution lookup",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'bucket_pattern': bucket_pattern,
                        'stage_id': stage_id,
                        'resolved_origin_path': resolved_origin_path,
                        'operation': 'origin_path_resolution'
                    }}
                )
                
                # Step 4: Find matching CloudFront distributions
                logger.info(
                    f"Step 4: Finding CloudFront distributions",
                    extra={'extra_fields': {
                        'bucketName': bucket_name,
                        'stageId': stage_id,
                        'resolvedOriginPath': resolved_origin_path,
                        'aboutToCallFindMatchingDistributions': True
                    }}
                )
                
                distribution_ids = find_matching_distributions(bucket_name, resolved_origin_path)
                
                logger.info(
                    f"Step 4: Distribution search results",
                    extra={'extra_fields': {
                        'bucketName': bucket_name,
                        'stageId': stage_id,
                        'resolvedOriginPath': resolved_origin_path,
                        'distributionIds': distribution_ids,
                        'distributionCount': len(distribution_ids) if distribution_ids else 0,
                        'distributionsFound': bool(distribution_ids)
                    }}
                )
                
                if not distribution_ids:
                    logger.info(
                        f"No distributions found for bucket {bucket_name} with stage {stage_id}",
                        extra={'extra_fields': {
                            'bucket_name': bucket_name,
                            'stage_id': stage_id,
                            'resolved_origin_path': resolved_origin_path,
                            'noDistributionsFound': True,
                            'messagesBeingDeleted': len(stage_messages)
                        }}
                    )
                    # Delete messages even if no distributions found
                    messages_to_delete.extend(stage_messages)
                    continue
                
                summary['distributions_found'] += len(distribution_ids)
                
                # Step 5: Validate distribution tags and filter
                valid_distributions = []
                
                logger.info(
                    f"Step 5: Starting distribution tag validation",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'bucket_app_tag': bucket_app_tag,
                        'stage_id': stage_id,
                        'distribution_count': len(distribution_ids),
                        'distribution_ids': distribution_ids,
                        'expected_app_deployment_id': f"{bucket_app_tag}-{stage_id}"
                    }}
                )
                
                for dist_id in distribution_ids:
                    is_valid = validate_distribution_tags(dist_id, bucket_app_tag, stage_id)
                    
                    logger.info(
                        f"Distribution {dist_id} validation result: {is_valid}",
                        extra={'extra_fields': {
                            'distribution_id': dist_id,
                            'bucket_name': bucket_name,
                            'bucket_app_tag': bucket_app_tag,
                            'stage_id': stage_id,
                            'expected_app_deployment_id': f"{bucket_app_tag}-{stage_id}",
                            'validation_passed': is_valid
                        }}
                    )
                    
                    if is_valid:
                        valid_distributions.append(dist_id)
                        summary['distributions_validated'] += 1
                    else:
                        logger.warning(
                            f"Distribution {dist_id} failed tag validation",
                            extra={'extra_fields': {
                                'distribution_id': dist_id,
                                'bucket_name': bucket_name,
                                'stage_id': stage_id,
                                'bucket_app_tag': bucket_app_tag,
                                'expected_app_deployment_id': f"{bucket_app_tag}-{stage_id}"
                            }}
                        )
                        summary['distributions_rejected'] += 1
                
                if not valid_distributions:
                    logger.info(
                        f"No valid distributions for bucket {bucket_name}, stage {stage_id} after tag validation",
                        extra={'extra_fields': {
                            'bucket_name': bucket_name,
                            'stage_id': stage_id
                        }}
                    )
                    # Delete messages even if no valid distributions
                    messages_to_delete.extend(stage_messages)
                    continue
                
                # Step 6: Get bucket-specific consolidation configuration from fetched tags
                logger.info(
                    f"Step 6: Resolving consolidation configuration for bucket {bucket_name}",
                    extra={'extra_fields': {
                        'bucketName': bucket_name,
                        'aboutToCallGetBucketConsolidationConfigFromDict': True
                    }}
                )
                
                try:
                    bucket_config = get_bucket_consolidation_config_from_dict(bucket_tags, bucket_name)
                    
                    logger.info(
                        f"Using consolidation configuration for bucket {bucket_name}",
                        extra={'extra_fields': {
                            'bucket_name': bucket_name,
                            'directory_threshold': bucket_config['directory_threshold'],
                            'stop_level': bucket_config['stop_level'],
                            'sibling_directory_threshold': bucket_config['sibling_directory_threshold'],
                            'directory_threshold_source': bucket_config['directory_threshold_source'],
                            'stop_level_source': bucket_config['stop_level_source'],
                            'sibling_directory_threshold_source': bucket_config['sibling_directory_threshold_source'],
                            'operation': 'consolidation_config_applied'
                        }}
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to resolve consolidation configuration for bucket {bucket_name}, using defaults: {str(e)}",
                        extra={'extra_fields': {
                            'bucket_name': bucket_name,
                            'error': str(e),
                            'fallback_directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
                            'fallback_stop_level': CONSOLIDATION_STOP_LEVEL,
                            'fallback_sibling_directory_threshold': SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
                            'fallback_reason': 'config_resolution_error'
                        }}
                    )
                    
                    bucket_config = {
                        'directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
                        'stop_level': CONSOLIDATION_STOP_LEVEL,
                        'sibling_directory_threshold': SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
                        'directory_threshold_source': 'default_fallback',
                        'stop_level_source': 'default_fallback',
                        'sibling_directory_threshold_source': 'default_fallback'
                    }
                
                # Step 7: Extract and consolidate paths for this stage
                object_paths = []
                for message in stage_messages:
                    parsed_body = message.get('parsed_body', {})
                    object_key = parsed_body.get('objectKey', '')
                    if object_key:
                        # Remove the resolved origin path prefix to get the relative path for invalidation
                        # CloudFront invalidation paths should be relative to the origin
                        if resolved_origin_path and object_key.startswith(resolved_origin_path):
                            relative_path = object_key[len(resolved_origin_path):]
                            # Ensure path starts with /
                            if not relative_path.startswith('/'):
                                relative_path = '/' + relative_path
                            object_paths.append(relative_path)
                        else:
                            # Fallback: use full object key with leading slash
                            fallback_path = object_key if object_key.startswith('/') else '/' + object_key
                            object_paths.append(fallback_path)
                
                if not object_paths:
                    logger.warning(
                        f"No valid paths extracted from messages for bucket {bucket_name}, stage {stage_id}",
                        extra={'extra_fields': {
                            'bucket_name': bucket_name,
                            'stage_id': stage_id
                        }}
                    )
                    messages_to_delete.extend(stage_messages)
                    continue
                
                logger.info(
                    f"Paths before consolidation",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'stage_id': stage_id,
                        'path_count': len(object_paths),
                        'paths': object_paths[:20] if len(object_paths) > 20 else object_paths
                    }}
                )
                
                # Consolidate paths with bucket-specific configuration
                # Note: We don't pass bucket_pattern here because we've already grouped by stage
                # and extracted relative paths. Passing bucket_pattern would cause re-grouping.
                consolidated_by_stage = consolidate_paths(
                    object_paths,
                    directory_threshold=bucket_config['directory_threshold'],
                    stop_level=bucket_config['stop_level'],
                    sibling_threshold=bucket_config['sibling_directory_threshold'],
                    bucket_pattern=None  # Don't re-group by stage
                )
                
                logger.info(
                    f"Paths after consolidation",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'stage_id': stage_id,
                        'consolidated_path_count': len(consolidated_by_stage.get('default', [[]])[0]) if consolidated_by_stage.get('default') else 0,
                        'chunk_count': len(consolidated_by_stage.get('default', []))
                    }}
                )
                
                # Step 8: Submit invalidations for each valid distribution
                # Since we passed bucket_pattern=None, consolidate_paths returns {'default': [[paths]]}
                consolidated_path_chunks = consolidated_by_stage.get('default', [[]])
                
                logger.info(
                    f"Submitting {len(consolidated_path_chunks)} invalidation chunk(s) for stage {stage_id}",
                    extra={'extra_fields': {
                        'bucket_name': bucket_name,
                        'stage_id': stage_id,
                        'chunk_count': len(consolidated_path_chunks),
                        'total_paths': sum(len(chunk) for chunk in consolidated_path_chunks)
                    }}
                )
                
                for dist_id in valid_distributions:
                    for chunk_idx, path_chunk in enumerate(consolidated_path_chunks):
                        try:
                            result = create_invalidation(dist_id, path_chunk)
                            
                            if result:
                                summary['invalidations_submitted'] += 1
                                logger.info(
                                    f"Successfully submitted invalidation",
                                    extra={'extra_fields': {
                                        'distribution_id': dist_id,
                                        'bucket_name': bucket_name,
                                        'stage_id': stage_id,
                                        'invalidation_id': result.get('Id'),
                                        'path_count': len(path_chunk),
                                        'chunk_index': chunk_idx,
                                        'total_chunks': len(consolidated_path_chunks)
                                    }}
                                )
                            else:
                                summary['invalidations_failed'] += 1
                                logger.error(
                                    f"Failed to submit invalidation",
                                    extra={'extra_fields': {
                                        'distribution_id': dist_id,
                                        'bucket_name': bucket_name,
                                        'stage_id': stage_id,
                                        'path_count': len(path_chunk),
                                        'chunk_index': chunk_idx
                                    }}
                                )
                        except Exception as e:
                            summary['invalidations_failed'] += 1
                            logger.error(
                                f"Exception submitting invalidation: {str(e)}",
                                extra={'extra_fields': {
                                    'distribution_id': dist_id,
                                    'bucket_name': bucket_name,
                                    'stage_id': stage_id,
                                    'error': str(e),
                                    'path_count': len(path_chunk),
                                    'chunk_index': chunk_idx
                                }}
                            )
                
                # Mark stage messages for deletion (processed successfully)
                messages_to_delete.extend(stage_messages)
        
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