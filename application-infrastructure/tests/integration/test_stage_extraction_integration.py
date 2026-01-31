#!/usr/bin/env python3
"""
Integration tests for stage extraction fix.

**Feature: 0-0-2-stage-id-path-fix, Integration Test: End-to-end processing**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 3.4**

This module tests the end-to-end flow to verify that the stage extraction fix
correctly handles {stageId} placeholders at any position in the origin path pattern.

The tests verify:
1. Stage extraction with {stageId} at various positions in the pattern
2. Distribution matching receives the correct stage identifier
3. Tag validation receives the correct stage identifier
4. Messages are grouped correctly by extracted stage

Run with: pytest tests/integration/test_stage_extraction_integration.py -v
"""

import json
import os
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import the handler
from functions.processor.handler import handler


class TestStageExtractionIntegration:
    """Integration tests for stage extraction with various pattern positions."""
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags_from_dict')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config_from_dict')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_stage_at_first_position(
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
        Test stage extraction with {stageId} at first position.
        
        **Validates: Requirements 1.1, 3.4**
        
        Pattern: /{stageId}/public
        Object key: /prod/public/file.html
        Expected stage: "prod"
        """
        # Arrange: Create SQS messages with stage at first position
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/prod/public/file.html',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket setup
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true'
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern with stage at first position
        mock_resolve_pattern.return_value = '/{stageId}/public'
        mock_filter_events.return_value = messages
        
        # Mock: Distribution matching and validation
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        
        # Mock: Consolidation and invalidation
        mock_consolidate.return_value = {'default': [['/file.html']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
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
        
        # Assert: Distribution matching was called with correct resolved origin path
        # Pattern /{stageId}/public + stage "prod" = /prod/public
        mock_find_dist.assert_called_once_with('test-bucket', '/prod/public')
        
        # Assert: Tag validation was called with correct stage identifier
        mock_validate_dist.assert_called_once_with('DIST123', 'test-app', 'prod')
        
        # Assert: Invalidation was created
        mock_invalidate.assert_called_once_with('DIST123', ['/file.html'])
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags_from_dict')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config_from_dict')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_stage_at_second_position(
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
        Test stage extraction with {stageId} at second position.
        
        **Validates: Requirements 1.2, 3.4**
        
        Pattern: /app/web/{stageId}/web
        Object key: /app/web/prod/public/file.html
        Expected stage: "prod"
        """
        # Arrange: Create SQS messages with stage at second position
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/app/web/prod/public/file.html',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket setup
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true'
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern with stage at second position (after /app/web)
        mock_resolve_pattern.return_value = '/app/web/{stageId}/web'
        mock_filter_events.return_value = messages
        
        # Mock: Distribution matching and validation
        mock_find_dist.return_value = ['DIST456']
        mock_validate_dist.return_value = True
        
        # Mock: Consolidation and invalidation
        mock_consolidate.return_value = {'default': [['/public/file.html']]}
        mock_invalidate.return_value = {'Id': 'INV456', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
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
        
        # Assert: Distribution matching was called with correct resolved origin path
        # Pattern /app/web/{stageId}/web + stage "prod" = /app/web/prod/web
        mock_find_dist.assert_called_once_with('test-bucket', '/app/web/prod/web')
        
        # Assert: Tag validation was called with correct stage identifier
        mock_validate_dist.assert_called_once_with('DIST456', 'test-app', 'prod')
        
        # Assert: Invalidation was created
        mock_invalidate.assert_called_once()
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags_from_dict')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config_from_dict')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_stage_at_third_position(
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
        Test stage extraction with {stageId} at third position.
        
        **Validates: Requirements 1.3, 3.4**
        
        Pattern: /app/web/{stageId}/public
        Object key: /app/web/prod/public/file.html
        Expected stage: "prod"
        """
        # Arrange: Create SQS messages with stage at third position
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/app/web/prod/public/file.html',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket setup
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true'
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern with stage at third position
        mock_resolve_pattern.return_value = '/app/web/{stageId}/public'
        mock_filter_events.return_value = messages
        
        # Mock: Distribution matching and validation
        mock_find_dist.return_value = ['DIST789']
        mock_validate_dist.return_value = True
        
        # Mock: Consolidation and invalidation
        mock_consolidate.return_value = {'default': [['/file.html']]}
        mock_invalidate.return_value = {'Id': 'INV789', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
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
        
        # Assert: Distribution matching was called with correct resolved origin path
        # Pattern /app/web/{stageId}/public + stage "prod" = /app/web/prod/public
        mock_find_dist.assert_called_once_with('test-bucket', '/app/web/prod/public')
        
        # Assert: Tag validation was called with correct stage identifier
        mock_validate_dist.assert_called_once_with('DIST789', 'test-app', 'prod')
        
        # Assert: Invalidation was created
        mock_invalidate.assert_called_once()
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags_from_dict')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config_from_dict')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_no_stage_placeholder(
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
        Test stage extraction without {stageId} placeholder.
        
        **Validates: Requirements 1.4, 3.4**
        
        Pattern: /public
        Object key: /public/file.html
        Expected stage: ""
        """
        # Arrange: Create SQS messages without stage placeholder
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/public/file.html',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        # Mock: Bucket setup
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true'
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern without stage placeholder
        mock_resolve_pattern.return_value = '/public'
        mock_filter_events.return_value = messages
        
        # Mock: Distribution matching and validation
        mock_find_dist.return_value = ['DIST_NO_STAGE']
        mock_validate_dist.return_value = True
        
        # Mock: Consolidation and invalidation
        mock_consolidate.return_value = {'default': [['/file.html']]}
        mock_invalidate.return_value = {'Id': 'INV_NO_STAGE', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
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
        
        # Assert: Distribution matching was called with pattern as-is (no stage substitution)
        mock_find_dist.assert_called_once_with('test-bucket', '/public')
        
        # Assert: Tag validation was called with empty stage identifier
        mock_validate_dist.assert_called_once_with('DIST_NO_STAGE', 'test-app', '')
        
        # Assert: Invalidation was created
        mock_invalidate.assert_called_once()
    
    @patch.dict(os.environ, {
        'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'DIRECTORY_CONSOLIDATION_THRESHOLD': '3',
        'CONSOLIDATION_STOP_LEVEL': '1',
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '10'
    })
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags_from_dict')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config_from_dict')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_multiple_stages_grouped_correctly(
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
        Test that messages with different stages are grouped correctly.
        
        **Validates: Requirements 3.4**
        
        This test verifies that when messages have the same bucket but different
        stages, they are processed separately with correct stage identifiers.
        """
        # Arrange: Create messages with different stages
        prod_messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/prod/public/file1.html',
                    'eventTime': '2024-01-01T00:00:00Z',
                    'eventType': 'ObjectCreated:Put'
                }
            },
            {
                'MessageId': 'msg2',
                'ReceiptHandle': 'handle2',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/prod/public/file2.html',
                    'eventTime': '2024-01-01T00:00:01Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        staging_messages = [
            {
                'MessageId': 'msg3',
                'ReceiptHandle': 'handle3',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'objectKey': '/staging/public/file3.html',
                    'eventTime': '2024-01-01T00:00:02Z',
                    'eventType': 'ObjectCreated:Put'
                }
            }
        ]
        
        all_messages = prod_messages + staging_messages
        
        # Mock: Bucket setup
        mock_receive.side_effect = [all_messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {
            'atlantis:Application': 'test-app',
            'AllowInvalidationEvents': 'true'
        }
        
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        # Mock: Pattern with stage at first position
        mock_resolve_pattern.return_value = '/{stageId}/public'
        mock_filter_events.return_value = all_messages
        
        # Mock: Distribution matching and validation for both stages
        # The handler will call find_matching_distributions twice (once per stage)
        mock_find_dist.side_effect = [['DIST_PROD'], ['DIST_STAGING']]
        mock_validate_dist.return_value = True
        
        # Mock: Consolidation for both stages
        mock_consolidate.side_effect = [
            {'default': [['/file1.html', '/file2.html']]},  # prod
            {'default': [['/file3.html']]}  # staging
        ]
        
        # Mock: Invalidation for both stages
        mock_invalidate.side_effect = [
            {'Id': 'INV_PROD', 'Status': 'InProgress'},
            {'Id': 'INV_STAGING', 'Status': 'InProgress'}
        ]
        
        mock_delete.return_value = {'successful': ['handle1', 'handle2', 'handle3'], 'failed': []}
        
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
        
        # Assert: Distribution matching was called twice with correct resolved paths
        assert mock_find_dist.call_count == 2
        # Check that both stages were processed
        find_dist_calls = [call[0] for call in mock_find_dist.call_args_list]
        assert ('test-bucket', '/prod/public') in find_dist_calls
        assert ('test-bucket', '/staging/public') in find_dist_calls
        
        # Assert: Tag validation was called twice with correct stage identifiers
        assert mock_validate_dist.call_count == 2
        validate_dist_calls = [call[0] for call in mock_validate_dist.call_args_list]
        assert ('DIST_PROD', 'test-app', 'prod') in validate_dist_calls
        assert ('DIST_STAGING', 'test-app', 'staging') in validate_dist_calls
        
        # Assert: Invalidations were created for both stages
        assert mock_invalidate.call_count == 2
