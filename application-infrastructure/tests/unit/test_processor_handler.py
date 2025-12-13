"""Unit tests for Processor Lambda handler."""

import sys
import os
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from processor.handler import handler, group_messages_by_bucket_and_origin


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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.close_window')
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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.validate_bucket_tags')
    @patch('processor.handler.get_bucket_tags')
    @patch('processor.handler.find_matching_distributions')
    @patch('processor.handler.validate_distribution_tags')
    @patch('processor.handler.consolidate_paths')
    @patch('processor.handler.create_invalidation')
    @patch('processor.handler.delete_messages_batch')
    @patch('processor.handler.close_window')
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
        mock_consolidate.return_value = [['/file1.js']]
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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.validate_bucket_tags')
    @patch('processor.handler.delete_messages_batch')
    @patch('processor.handler.close_window')
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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.validate_bucket_tags')
    @patch('processor.handler.get_bucket_tags')
    @patch('processor.handler.find_matching_distributions')
    @patch('processor.handler.delete_messages_batch')
    @patch('processor.handler.close_window')
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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.validate_bucket_tags')
    @patch('processor.handler.get_bucket_tags')
    @patch('processor.handler.find_matching_distributions')
    @patch('processor.handler.validate_distribution_tags')
    @patch('processor.handler.delete_messages_batch')
    @patch('processor.handler.close_window')
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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.validate_bucket_tags')
    @patch('processor.handler.get_bucket_tags')
    @patch('processor.handler.find_matching_distributions')
    @patch('processor.handler.validate_distribution_tags')
    @patch('processor.handler.consolidate_paths')
    @patch('processor.handler.delete_messages_batch')
    @patch('processor.handler.close_window')
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
        mock_consolidate.return_value = [['/dir/*']]  # Consolidated result
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
    @patch('processor.handler.receive_messages_batch')
    @patch('processor.handler.validate_bucket_tags')
    @patch('processor.handler.get_bucket_tags')
    @patch('processor.handler.find_matching_distributions')
    @patch('processor.handler.validate_distribution_tags')
    @patch('processor.handler.consolidate_paths')
    @patch('processor.handler.create_invalidation')
    @patch('processor.handler.delete_messages_batch')
    @patch('processor.handler.close_window')
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
        mock_consolidate.return_value = [['/file1.js'], ['/file2.js']]  # Multiple chunks
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
