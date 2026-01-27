"""Unit tests for Processor Lambda handler."""

import os
from unittest.mock import Mock, patch, MagicMock, call

import pytest

from functions.processor.handler import handler, group_messages_by_bucket_and_origin


class TestGroupMessagesByBucketAndOrigin:
    """Tests for group_messages_by_bucket_and_origin function."""
    
    def test_groups_messages_correctly(self):
        """Test that messages are grouped by bucket and origin path."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'bucket-a',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            },
            {
                'MessageId': 'msg2',
                'ReceiptHandle': 'handle2',
                'parsed_body': {
                    'bucketName': 'bucket-a',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file2.js',
                    'stageId': 'prod'
                }
            },
            {
                'MessageId': 'msg3',
                'ReceiptHandle': 'handle3',
                'parsed_body': {
                    'bucketName': 'bucket-b',
                    'originPath': '/stage/public',
                    'objectKey': '/stage/public/file3.js',
                    'stageId': 'stage'
                }
            }
        ]
        
        # Act
        grouped = group_messages_by_bucket_and_origin(messages)
        
        # Assert
        assert len(grouped) == 2
        assert ('bucket-a', '/prod/public') in grouped
        assert ('bucket-b', '/stage/public') in grouped
        assert len(grouped[('bucket-a', '/prod/public')]) == 2
        assert len(grouped[('bucket-b', '/stage/public')]) == 1
    
    def test_skips_messages_with_missing_fields(self):
        """Test that messages with missing bucketName or originPath are skipped."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'parsed_body': {
                    'bucketName': 'bucket-a',
                    'originPath': '/prod/public'
                }
            },
            {
                'MessageId': 'msg2',
                'parsed_body': {
                    'bucketName': 'bucket-a'
                    # Missing originPath
                }
            },
            {
                'MessageId': 'msg3',
                'parsed_body': {
                    'originPath': '/prod/public'
                    # Missing bucketName
                }
            }
        ]
        
        # Act
        grouped = group_messages_by_bucket_and_origin(messages)
        
        # Assert
        assert len(grouped) == 1
        assert ('bucket-a', '/prod/public') in grouped
        assert len(grouped[('bucket-a', '/prod/public')]) == 1


class TestProcessorHandler:
    """Tests for the main handler function."""
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_no_messages_to_process(self, mock_close_window, mock_receive):
        """Test handler behavior when queue is empty."""
        # Arrange
        mock_receive.return_value = []
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        assert 'No messages to process' in result['body']
        mock_close_window.assert_called_once()
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_successful_processing_flow(
        self, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test successful end-to-end processing flow."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]  # First call returns messages, second returns empty
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        assert 'Processed 1 messages' in result['body']
        assert 'submitted 1 invalidations' in result['body']
        
        # Verify all steps were called
        mock_validate_bucket.assert_called_once_with('test-bucket')
        mock_get_tags.assert_called_once_with('test-bucket')
        mock_find_dist.assert_called_once_with('test-bucket', '/prod/public')
        mock_validate_dist.assert_called_once_with('DIST123', 'test-app', 'prod')
        mock_consolidate.assert_called_once()
        mock_invalidate.assert_called_once_with('DIST123', ['/file1.js'])
        mock_delete.assert_called_once()
        mock_close_window.assert_called_once()
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_bucket_tag_validation_failure(
        self, mock_close_window, mock_delete, mock_validate_bucket, mock_receive
    ):
        """Test that buckets failing tag validation are skipped."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = False  # Bucket validation fails
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        mock_validate_bucket.assert_called_once_with('test-bucket')
        # Messages should still be deleted even though bucket was rejected
        mock_delete.assert_called_once()
        mock_close_window.assert_called_once()
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_distribution_discovery_no_matches(
        self, mock_close_window, mock_delete, mock_find_dist,
        mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test handling when no distributions match the bucket/origin."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_find_dist.return_value = []  # No distributions found
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        mock_find_dist.assert_called_once_with('test-bucket', '/prod/public')
        # Messages should still be deleted
        mock_delete.assert_called_once()
        mock_close_window.assert_called_once()
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_distribution_tag_validation_failure(
        self, mock_close_window, mock_delete, mock_validate_dist,
        mock_find_dist, mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test that distributions failing tag validation are skipped."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = False  # Distribution validation fails
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        mock_validate_dist.assert_called_once_with('DIST123', 'test-app', 'prod')
        # Messages should still be deleted
        mock_delete.assert_called_once()
        mock_close_window.assert_called_once()
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_path_consolidation_integration(
        self, mock_close_window, mock_delete, mock_consolidate,
        mock_validate_dist, mock_find_dist, mock_get_tags,
        mock_validate_bucket, mock_receive
    ):
        """Test that path consolidation is called with correct paths."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/dir/file1.js',
                    'stageId': 'prod'
                }
            },
            {
                'MessageId': 'msg2',
                'ReceiptHandle': 'handle2',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/dir/file2.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/dir/*']]}  # Consolidated result
        mock_delete.return_value = {'successful': ['handle1', 'handle2'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        # Verify consolidate_paths was called with the correct paths
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args[0][0]
        assert '/dir/file1.js' in call_args
        assert '/dir/file2.js' in call_args
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_invalidation_submission(
        self, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test that invalidations are submitted correctly."""
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_find_dist.return_value = ['DIST123', 'DIST456']  # Multiple distributions
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js'], ['/file2.js']]}  # Multiple chunks
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        # Should be called 4 times: 2 distributions × 2 chunks
        assert mock_invalidate.call_count == 4
        
        # Verify calls for both distributions and both chunks
        expected_calls = [
            call('DIST123', ['/file1.js']),
            call('DIST123', ['/file2.js']),
            call('DIST456', ['/file1.js']),
            call('DIST456', ['/file2.js'])
        ]
        mock_invalidate.assert_has_calls(expected_calls, any_order=True)
    
    @patch.dict(os.environ, {})
    def test_missing_queue_url_environment_variable(self):
        """Test that handler fails gracefully when QUEUE_URL is not set."""
        # Arrange
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 500
        assert 'Configuration error' in result['body']
        assert 'QUEUE_URL' in result['body']

    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}, clear=False)
    @patch('boto3.Session')
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_configuration_resolution_with_bucket_tags(
        self, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive, mock_boto_session
    ):
        """Test configuration resolution for buckets with configuration tags.
        
        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 5.1, 5.2, 5.3
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        bucket_config = {
            'directory_threshold': 5,
            'stop_level': 2,
            'sibling_directory_threshold': 10,  # Default value
            'directory_threshold_source': 'tag',
            'stop_level_source': 'tag',
            'sibling_directory_threshold_source': 'default'
        }
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = bucket_config
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify configuration was retrieved for the bucket
        mock_get_config.assert_called_once_with('test-bucket')
        
        # Verify consolidate_paths was called with bucket-specific configuration
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args
        assert call_args[1]['directory_threshold'] == 5
        assert call_args[1]['stop_level'] == 2

    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}, clear=False)
    @patch('boto3.Session')
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_configuration_resolution_without_bucket_tags(
        self, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive, mock_boto_session
    ):
        """Test configuration resolution for buckets without configuration tags.
        
        Requirements: 1.3, 2.3, 5.2
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        # Configuration with default values
        bucket_config = {
            'directory_threshold': 3,  # Default value
            'stop_level': 1,  # Default value
            'sibling_directory_threshold': 10,  # Default value
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = bucket_config
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify configuration was retrieved for the bucket
        mock_get_config.assert_called_once_with('test-bucket')
        
        # Verify consolidate_paths was called with default configuration
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args
        assert call_args[1]['directory_threshold'] == 3  # Default value
        assert call_args[1]['stop_level'] == 1  # Default value

    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}, clear=False)
    @patch('boto3.Session')
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.DIRECTORY_CONSOLIDATION_THRESHOLD', 3)
    @patch('functions.processor.handler.CONSOLIDATION_STOP_LEVEL', 1)
    def test_configuration_reading_error_fallback(
        self, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive, mock_boto_session
    ):
        """Test error handling when configuration reading fails.
        
        Requirements: 1.3, 2.3, 5.2, 5.3
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.side_effect = Exception("S3 error")  # Simulate configuration reading failure
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify configuration reading was attempted
        mock_get_config.assert_called_once_with('test-bucket')
        
        # Verify consolidate_paths was called with fallback default configuration
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args
        assert call_args[1]['directory_threshold'] == 3  # Fallback default
        assert call_args[1]['stop_level'] == 1  # Fallback default

    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}, clear=False)
    @patch('boto3.Session')
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.logger')
    def test_configuration_decision_logging(
        self, mock_logger, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive, mock_boto_session
    ):
        """Test logging of configuration decisions.
        
        Requirements: 5.1, 5.2, 5.3
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        bucket_config = {
            'directory_threshold': 5,
            'stop_level': 2,
            'sibling_directory_threshold': 10,  # Default value
            'directory_threshold_source': 'tag',
            'stop_level_source': 'tag',
            'sibling_directory_threshold_source': 'default'
        }
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = bucket_config
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify configuration logging occurred
        assert mock_logger.info.called, "Should log configuration decisions"
        
        # Check that configuration was logged
        config_logged = False
        for call in mock_logger.info.call_args_list:
            call_str = str(call)
            if 'Using consolidation configuration for bucket' in call_str and 'test-bucket' in call_str:
                config_logged = True
                break
        
        assert config_logged, "Should log effective configuration being used for bucket"

    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}, clear=False)
    @patch('boto3.Session')
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    def test_sibling_threshold_parameter_passed_to_consolidate_paths(
        self, mock_close_window, mock_delete, mock_invalidate,
        mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive, mock_boto_session
    ):
        """Test that sibling_directory_threshold from bucket config is passed to consolidate_paths.
        
        Requirements: 1.4, 2.1, 2.4
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/file1.js',
                    'stageId': 'prod'
                }
            }
        ]
        
        # Configuration with custom sibling threshold
        bucket_config = {
            'directory_threshold': 5,
            'stop_level': 2,
            'sibling_directory_threshold': 7,  # Custom sibling threshold
            'directory_threshold_source': 'tag',
            'stop_level_source': 'tag',
            'sibling_directory_threshold_source': 'tag'
        }
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = bucket_config
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/file1.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify configuration was retrieved for the bucket
        mock_get_config.assert_called_once_with('test-bucket')
        
        # Verify consolidate_paths was called with bucket-specific sibling threshold
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args
        assert call_args[1]['directory_threshold'] == 5
        assert call_args[1]['stop_level'] == 2
        assert call_args[1]['sibling_threshold'] == 7  # Verify sibling threshold is passed


class TestInvalidationPathGeneration:
    """Tests for CloudFront invalidation path generation from normalized S3 object keys.
    
    Requirements: 3.1, 3.2, 3.3
    """
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    def test_invalidation_path_preserves_leading_slash(
        self, mock_filter, mock_resolve_pattern, mock_close_window, mock_delete, 
        mock_invalidate, mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test that invalidation paths preserve leading slashes from normalized object keys.
        
        Requirement 3.1: When creating a CloudFront invalidation path from a normalized path,
        THE System SHALL preserve the leading slash.
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/prod/public/assets/file.js',  # Normalized with leading slash
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        mock_resolve_pattern.return_value = '/'
        mock_filter.return_value = messages
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/assets/file.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify consolidate_paths was called with paths that have leading slashes
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] == '/assets/file.js'
        assert call_args[0].startswith('/')
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    def test_root_origin_path_generates_correct_invalidation_paths(
        self, mock_filter, mock_resolve_pattern, mock_close_window, mock_delete, 
        mock_invalidate, mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test that root origin path (/) generates correct invalidation paths.
        
        Requirement 3.2: When the origin path is root (/), THE System SHALL use / 
        as the invalidation path prefix.
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/',  # Root origin path
                    'objectKey': '/content/file.js',  # Normalized with leading slash
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        mock_resolve_pattern.return_value = '/'
        mock_filter.return_value = messages
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/content/file.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify consolidate_paths was called with the full path (since origin is root)
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] == '/content/file.js'
        assert call_args[0].startswith('/')
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    def test_non_root_origin_path_generates_correct_invalidation_paths(
        self, mock_filter, mock_resolve_pattern, mock_close_window, mock_delete, 
        mock_invalidate, mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test that non-root origin paths generate correct invalidation paths.
        
        Requirement 3.3: When the origin path is non-root, THE System SHALL ensure 
        the invalidation path starts with the origin path including its leading slash.
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/app/prod/public',  # Non-root origin path
                    'objectKey': '/app/prod/public/assets/file.js',  # Normalized with leading slash
                    'stageId': 'prod'
                }
            },
            {
                'MessageId': 'msg2',
                'ReceiptHandle': 'handle2',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/app/prod/public',
                    'objectKey': '/app/prod/public/css/style.css',  # Normalized with leading slash
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        mock_resolve_pattern.return_value = '/app/{stageId}/public'
        mock_filter.return_value = messages
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/assets/file.js', '/css/style.css']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1', 'handle2'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify consolidate_paths was called with relative paths (origin prefix removed)
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args[0][0]
        assert len(call_args) == 2
        assert '/assets/file.js' in call_args
        assert '/css/style.css' in call_args
        # All paths should start with /
        for path in call_args:
            assert path.startswith('/')
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    def test_fallback_path_generation_with_leading_slash(
        self, mock_filter, mock_resolve_pattern, mock_close_window, mock_delete, 
        mock_invalidate, mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test fallback path generation when object key doesn't start with origin path.
        
        Requirement 3.1: Fallback paths should also preserve leading slashes.
        """
        # Arrange
        messages = [
            {
                'MessageId': 'msg1',
                'ReceiptHandle': 'handle1',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': '/different/path/file.js',  # Doesn't start with origin path
                    'stageId': 'prod'
                }
            }
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        mock_resolve_pattern.return_value = '/'
        mock_filter.return_value = messages
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        mock_consolidate.return_value = {'prod': [['/different/path/file.js']]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': ['handle1'], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify consolidate_paths was called with fallback path that has leading slash
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] == '/different/path/file.js'
        assert call_args[0].startswith('/')
    
    @patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    @patch('functions.processor.handler.receive_messages_batch')
    @patch('functions.processor.handler.validate_bucket_tags')
    @patch('functions.processor.handler.get_bucket_tags')
    @patch('functions.processor.handler.get_bucket_consolidation_config')
    @patch('functions.processor.handler.find_matching_distributions')
    @patch('functions.processor.handler.validate_distribution_tags')
    @patch('functions.processor.handler.consolidate_paths')
    @patch('functions.processor.handler.create_invalidation')
    @patch('functions.processor.handler.delete_messages_batch')
    @patch('functions.processor.handler.close_window')
    @patch('functions.processor.handler.resolve_bucket_pattern')
    @patch('functions.processor.handler.filter_events_by_pattern')
    def test_multiple_paths_all_preserve_leading_slashes(
        self, mock_filter, mock_resolve_pattern, mock_close_window, mock_delete, 
        mock_invalidate, mock_consolidate, mock_validate_dist, mock_find_dist,
        mock_get_config, mock_get_tags, mock_validate_bucket, mock_receive
    ):
        """Test that multiple paths all preserve leading slashes.
        
        Requirement 3.1: All invalidation paths should preserve leading slashes.
        """
        # Arrange
        messages = [
            {
                'MessageId': f'msg{i}',
                'ReceiptHandle': f'handle{i}',
                'parsed_body': {
                    'bucketName': 'test-bucket',
                    'originPath': '/prod/public',
                    'objectKey': f'/prod/public/dir{i}/file{i}.js',
                    'stageId': 'prod'
                }
            }
            for i in range(1, 6)  # 5 messages
        ]
        
        mock_receive.side_effect = [messages, []]
        mock_validate_bucket.return_value = True
        mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
        mock_get_config.return_value = {
            'directory_threshold': 3,
            'stop_level': 1,
            'sibling_directory_threshold': 10,
            'directory_threshold_source': 'default',
            'stop_level_source': 'default',
            'sibling_directory_threshold_source': 'default'
        }
        mock_resolve_pattern.return_value = '/'
        mock_filter.return_value = messages
        mock_find_dist.return_value = ['DIST123']
        mock_validate_dist.return_value = True
        # Return paths as-is for this test
        mock_consolidate.return_value = {'prod': [[f'/dir{i}/file{i}.js' for i in range(1, 6)]]}
        mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
        mock_delete.return_value = {'successful': [f'handle{i}' for i in range(1, 6)], 'failed': []}
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Act
        result = handler({}, context)
        
        # Assert
        assert result['statusCode'] == 200
        
        # Verify all paths passed to consolidate_paths have leading slashes
        mock_consolidate.assert_called_once()
        call_args = mock_consolidate.call_args[0][0]
        assert len(call_args) == 5
        for path in call_args:
            assert path.startswith('/'), f"Path {path} should start with /"
