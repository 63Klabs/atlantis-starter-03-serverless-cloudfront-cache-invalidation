#!/usr/bin/env python3
"""
Integration test for origin path resolution fix.

**Feature: origin-path-resolution-fix, Integration Test: Complete flow**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

This module tests the end-to-end flow to verify that the bucket's origin path pattern
is correctly resolved and used when searching for CloudFront distributions.

The test verifies:
1. Bucket with invalidator:OriginPathPattern tag is processed correctly
2. Stage ID is extracted from events and substituted into the pattern
3. Resolved origin path is used for distribution search (not event origin path)
4. Correct distribution is found and invalidation is submitted

Run with: pytest tests/integration/test_origin_path_resolution.py -v
"""

import json
import os
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import the handler
from functions.processor.handler import handler


class TestOriginPathResolutionIntegration:
    """Integration test for origin path resolution fix."""
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_complete_flow_with_stage_pattern(
        self,
        mock_close_window,
        mock_delete,
        mock_invalidate,
        mock_consolidate,
        mock_validate_dist,
        mock_find_dist,
        mock_filter_events,
        mock_resolve_pattern,
        mock_get_config,
        mock_get_tags,
        mock_validate_bucket,
        mock_receive
    ):
        """
        Test complete flow with bucket having stage-specific origin path pattern.
        
        **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
        
        This test verifies:
        1. Bucket with invalidator:OriginPathPattern=/app/@stageId@ is processed
        2. Stage ID 'prod' is extracted from events
        3. Pattern is resolved to /app/prod
        4. find_matching_distributions is called with resolved path /app/prod (not /)
        5. Correct distribution is found and invalidation is submitted
        """
        # Arrange: Create SQS messages with stageId='prod'
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/',  # Event origin path (should NOT be used)
                    'objectKey': '/app/prod/file1.js',
                    'stageId': 'prod',  # Stage ID to be substituted
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            },
            {
                'MessageId': 'msg2',
                'ReceiptHandle': 'handle2',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/',
                    'objectKey': '/app/prod/file2.js',
                    'stageId': 'prod',
                    'eventTime': '2024-01-01T00:00:01Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket has invalidator:OriginPathPattern tag
        mock_receive.side_effect = [messages, []]  # First call returns messages, second returns empty
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true',
            'invalidator:OriginPathPattern': '/app/@stageId@'  # Pattern with stage placeholder
        }
        
        # Mock: Bucket consolidation config
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern resolution returns /app/{stageId} (normalized)
        mock_resolve_pattern.return_value = '/app/{stageId}'
        
        # Mock: Filter events returns all messages (they match the pattern)
        mock_filter_events.return_value = messages
        
        # Mock: CloudFront distribution with origin path /app/prod
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        
        # Mock: Path consolidation
        mock_consolidate.return_value = {'prod': [['/file1.js', '/file2.js']]}
        
        # Mock: Invalidation creation
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        
        # Mock: Message deletion
        mock_delete.return_value = {'successful': ['handle1', 'handle2'], 'failed': []}
        
        # Create Lambda context
        context = Mock()
        context.aws_request_id = 'test-request-id'
        context.function_name = 'test-processor'
        context.function_version = '1'
        context.memory_limit_in_mb = 128
        context.get_remaining_time_in_millis = Mock(return_value=30000)
        
        # Act: Execute handler
        result = handler({}, context)
        
        # Assert: Handler succeeded
        assert result['statusCode'] == 200
        assert 'Processed 2 messages' in result['body']
        assert 'submitted 1 invalidations' in result['body']
        
        # Assert: Bucket validation was called
        mock_validate_bucket.assert_called_once_with('test-bucket')
        
        # Assert: Bucket tags were retrieved
        mock_get_tags.assert_called_once_with('test-bucket')
        
        # Assert: Pattern resolution was called with sample path
        mock_resolve_pattern.assert_called_once_with('test-bucket', '/app/prod/file1.js')
        
        # Assert: Events were filtered by pattern
        mock_filter_events.assert_called_once_with(messages, '/app/{stageId}')
        
        # Assert: CRITICAL - find_matching_distributions was called with RESOLVED path /app/prod
        # NOT with event origin path /
        mock_find_dist.assert_called_once_with('test-bucket', '/app/prod')
        
        # Assert: Distribution validation was called
        mock_validate_dist.assert_called_once_with('DIST123', 'test-app', 'prod')
        
        # Assert: Path consolidation was called
        mock_consolidate.assert_called_once()
        
        # Assert: Invalidation was created
        mock_invalidate.assert_called_once_with('DIST123', ['/file1.js', '/file2.js'])
        
        # Assert: Messages were deleted
        mock_delete.assert_called_once()
        
        # Assert: Window was closed
        mock_close_window.assert_called_once()
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_complete_flow_with_root_pattern(
        self,
        mock_close_window,
        mock_delete,
        mock_invalidate,
        mock_consolidate,
        mock_validate_dist,
        mock_find_dist,
        mock_filter_events,
        mock_resolve_pattern,
        mock_get_config,
        mock_get_tags,
        mock_validate_bucket,
        mock_receive
    ):
        """
        Test complete flow with bucket having root origin path pattern.
        
        This test verifies:
        1. Bucket with invalidator:OriginPathPattern=/ is processed
        2. Root path / is converted to empty string for CloudFront
        3. find_matching_distributions is called with empty string
        """
        # Arrange: Create SQS messages
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/',
                    'objectKey': '/file1.js',
                    'stageId': 'prod',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket has root pattern
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true',
            'invalidator:OriginPathPattern': '/'  # Root pattern
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern resolution returns / (root)
        mock_resolve_pattern.return_value = '/'
        mock_filter_events.return_value = messages
        
        # Mock: CloudFront distribution with root origin path (empty string)
        mock_find_dist.return_value = ['DIST456']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV456', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        context.function_name = 'test-processor'
        context.function_version = '1'
        context.memory_limit_in_mb = 128
        context.get_remaining_time_in_millis = Mock(return_value=30000)
        
        # Act: Execute handler
        result = handler({}, context)
        
        # Assert: Handler succeeded
        assert result['statusCode'] == 200
        
        # Assert: CRITICAL - find_matching_distributions was called with empty string (not /)
        mock_find_dist.assert_called_once_with('test-bucket', '')
        
        # Assert: Invalidation was created
        mock_invalidate.assert_called_once_with('DIST456', ['/file1.js'])
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_complete_flow_with_multiple_stages(
        self,
        mock_close_window,
        mock_delete,
        mock_invalidate,
        mock_consolidate,
        mock_validate_dist,
        mock_find_dist,
        mock_filter_events,
        mock_resolve_pattern,
        mock_get_config,
        mock_get_tags,
        mock_validate_bucket,
        mock_receive
    ):
        """
        Test complete flow with events from multiple stages in same group.
        
        This test verifies:
        1. Events with same bucket and originPath are grouped together
        2. Filter returns only events matching the first event's stage
        3. Distribution is searched with resolved path for the first stage
        
        Note: Messages are grouped by (bucket, originPath) from the event,
        so prod and staging messages with same originPath='/' are in one group.
        The filter_events_by_pattern then filters to only matching events.
        """
        # Arrange: Create messages for prod and staging (same originPath)
        prod_message = {
            'MessageId': 'msg1',
            'ReceiptHandle': 'handle1',
            'parsed_body': {
                'bucketName': 'test-bucket',
                'originPath': '/',  # Same origin path
                'objectKey': '/app/prod/file1.js',
                'stageId': 'prod',
                'eventTime': '2024-01-01T00:00:00Z',
                'eventType': 'ObjectCreated:Put'
            }
        }
        
        staging_message = {
            'MessageId': 'msg2',
            'ReceiptHandle': 'handle2',
            'parsed_body': {
                'bucketName': 'test-bucket',
                'originPath': '/',  # Same origin path
                'objectKey': '/app/staging/file2.js',
                'stageId': 'staging',
                'eventTime': '2024-01-01T00:00:01Z',
                'eventType': 'ObjectCreated:Put'
            }
        }
        
        all_messages = [prod_message, staging_message]
        
        # Mock: Bucket setup
        mock_receive.side_effect = [all_messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true',
            'invalidator:OriginPathPattern': '/app/@stageId@'
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern resolution
        mock_resolve_pattern.return_value = '/app/{stageId}'
        
        # Mock: Filter events - only prod message matches (first event's stage)
        # The filter will only return events matching the pattern with prod stage
        mock_filter_events.return_value = [prod_message]
        
        # Mock: Distribution for prod stage
        mock_find_dist.return_value = ['DIST_PROD']
        mock_validate_dist.return_value = True
        
        # Mock: Consolidation
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1', 'handle2'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        context.function_name = 'test-processor'
        context.function_version = '1'
        context.memory_limit_in_mb = 128
        context.get_remaining_time_in_millis = Mock(return_value=30000)
        
        # Act: Execute handler
        result = handler({}, context)
        
        # Assert: Handler succeeded
        assert result['statusCode'] == 200
        
        # Assert: find_matching_distributions was called once with prod resolved path
        # (because filter returned only prod message)
        mock_find_dist.assert_called_once_with('test-bucket', '/app/prod')
        
        # Assert: Invalidation was created for prod distribution
        mock_invalidate.assert_called_once_with('DIST_PROD', ['/file1.js'])
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10',
        'ORIGIN_PATH_PATTERN': '/'  # Default pattern for backward compatibility
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_backward_compatibility_without_pattern_tag(
        self,
        mock_close_window,
        mock_delete,
        mock_invalidate,
        mock_consolidate,
        mock_validate_dist,
        mock_find_dist,
        mock_filter_events,
        mock_resolve_pattern,
        mock_get_config,
        mock_get_tags,
        mock_validate_bucket,
        mock_receive
    ):
        """
        Test backward compatibility for buckets without invalidator:OriginPathPattern tag.
        
        **Validates: Requirements 5.1, 5.3, 5.4**
        
        This test verifies:
        1. Bucket without invalidator:OriginPathPattern tag is processed correctly
        2. Default ORIGIN_PATH_PATTERN environment variable is used
        3. Root pattern (/) is converted to empty string for CloudFront
        4. Existing behavior is maintained for legacy buckets
        5. Distribution is found and invalidation is submitted successfully
        """
        # Arrange: Create SQS messages for bucket without pattern tag
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'legacy-bucket',
                    'originPath': '/',  # Event origin path
                    'objectKey': '/file1.js',
                    'stageId': 'prod',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            },
            {
                'MessageId': 'msg2',
                'ReceiptHandle': 'handle2',
                'parsed_body': {
                    'bucketName': 'legacy-bucket',
                    'originPath': '/',
                    'objectKey': '/file2.js',
                    'stageId': 'prod',
                    'eventTime': '2024-01-01T00:00:01Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket WITHOUT invalidator:OriginPathPattern tag (backward compatibility)
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'legacy-app',
            'AllowInvalidationEvents': 'true'
            # NO invalidator:OriginPathPattern tag - should use default
        }
        
        # Mock: Bucket consolidation config
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern resolution returns default ORIGIN_PATH_PATTERN (/)
        # Since bucket has no tag, resolve_bucket_pattern should return the default
        mock_resolve_pattern.return_value = '/'
        
        # Mock: Filter events returns all messages
        mock_filter_events.return_value = messages
        
        # Mock: CloudFront distribution with root origin path (empty string)
        # This is the existing behavior - distributions with root path use empty string
        mock_find_dist.return_value = ['DIST_LEGACY']
        mock_validate_dist.return_value = True
        
        # Mock: Path consolidation
        mock_consolidate.return_value = {'prod': [['/file1.js', '/file2.js']]}
        
        # Mock: Invalidation creation
        mock_invalidate.return_value = {'Id': 'INV_LEGACY', 'Status': 'InProgress'}
        
        # Mock: Message deletion
        mock_delete.return_value = {'successful': ['handle1', 'handle2'], 'failed': []}
        
        # Create Lambda context
        context = Mock()
        context.aws_request_id = 'test-request-id'
        context.function_name = 'test-processor'
        context.function_version = '1'
        context.memory_limit_in_mb = 128
        context.get_remaining_time_in_millis = Mock(return_value=30000)
        
        # Act: Execute handler
        result = handler({}, context)
        
        # Assert: Handler succeeded
        assert result['statusCode'] == 200
        assert 'Processed 2 messages' in result['body']
        assert 'submitted 1 invalidations' in result['body']
        
        # Assert: Bucket validation was called
        mock_validate_bucket.assert_called_once_with('legacy-bucket')
        
        # Assert: Bucket tags were retrieved
        mock_get_tags.assert_called_once_with('legacy-bucket')
        
        # Assert: Pattern resolution was called (should return default pattern)
        mock_resolve_pattern.assert_called_once_with('legacy-bucket', '/file1.js')
        
        # Assert: Events were filtered by default pattern
        mock_filter_events.assert_called_once_with(messages, '/')
        
        # Assert: CRITICAL - find_matching_distributions was called with empty string
        # Root pattern (/) should be converted to empty string for CloudFront
        # This maintains backward compatibility with existing distributions
        mock_find_dist.assert_called_once_with('legacy-bucket', '')
        
        # Assert: Distribution validation was called
        mock_validate_dist.assert_called_once_with('DIST_LEGACY', 'legacy-app', 'prod')
        
        # Assert: Path consolidation was called
        mock_consolidate.assert_called_once()
        
        # Assert: Invalidation was created with correct distribution
        mock_invalidate.assert_called_once_with('DIST_LEGACY', ['/file1.js', '/file2.js'])
        
        # Assert: Messages were deleted
        mock_delete.assert_called_once()
        
        # Assert: Window was closed
        mock_close_window.assert_called_once()
