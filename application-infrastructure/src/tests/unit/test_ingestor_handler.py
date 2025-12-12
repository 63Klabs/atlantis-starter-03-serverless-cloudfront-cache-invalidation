"""Unit tests for Ingestor Lambda handler."""

import sys
import os
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from ingestor.handler import process_s3_record, handler, get_queue_url
from ingestor.event_parser import S3EventParseError
from ingestor.queue_client import SQSClientError


class TestProcessS3Record:
    """Tests for process_s3_record function."""
    
    def test_successful_event_processing_flow(self):
        """Test successful processing of a valid S3 event."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send, \
             patch('ingestor.handler.check_active_window') as mock_check_window, \
             patch('ingestor.handler.create_one_time_schedule') as mock_create_schedule, \
             patch('ingestor.handler.create_window') as mock_create_window:
            
            mock_send.return_value = 'message-id-123'
            mock_check_window.return_value = None
            mock_create_schedule.return_value = 'arn:aws:scheduler:us-east-1:123456789012:schedule/test'
            mock_create_window.return_value = True
            
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert
            assert result['success'] is True
            assert 'processed successfully' in result['message'].lower()
            assert result['metadata']['bucketName'] == 'test-bucket'
            assert result['metadata']['stageId'] == 'prod'
            assert result['metadata']['originPath'] == '/prod/public'
            
            # Verify SQS was called
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[1]['bucket_name'] == 'test-bucket'
            assert call_args[1]['stage_id'] == 'prod'
            assert call_args[1]['origin_path'] == '/prod/public'
    
    def test_event_filtering_non_production_stage(self):
        """Test that non-production StageIds are filtered out."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/dev/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send:
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert
            assert result['success'] is True
            assert 'filtered' in result['message'].lower()
            
            # Verify SQS was NOT called
            mock_send.assert_not_called()
    
    def test_event_filtering_non_public_path(self):
        """Test that non-public paths are filtered out."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/private/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send:
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert
            assert result['success'] is True
            assert 'skipped' in result['message'].lower()
            
            # Verify SQS was NOT called
            mock_send.assert_not_called()
    
    def test_sqs_send_failure(self):
        """Test handling of SQS send failures."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send:
            mock_send.side_effect = SQSClientError("Failed to send message")
            
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert - handler catches the exception and returns error result
            assert result['success'] is False
            assert 'processing error' in result['message'].lower()
    
    def test_window_tracking_with_active_window(self):
        """Test that no new schedule is created when active window exists."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        active_window = {
            'windowId': 'current',
            'scheduleArn': 'arn:aws:scheduler:us-east-1:123456789012:schedule/existing',
            'status': 'active'
        }
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send, \
             patch('ingestor.handler.check_active_window') as mock_check_window, \
             patch('ingestor.handler.create_one_time_schedule') as mock_create_schedule, \
             patch('ingestor.handler.create_window') as mock_create_window:
            
            mock_send.return_value = 'message-id-123'
            mock_check_window.return_value = active_window
            
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert
            assert result['success'] is True
            
            # Verify schedule creation was NOT called
            mock_create_schedule.assert_not_called()
            mock_create_window.assert_not_called()
    
    def test_window_tracking_without_active_window(self):
        """Test that new schedule is created when no active window exists."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send, \
             patch('ingestor.handler.check_active_window') as mock_check_window, \
             patch('ingestor.handler.create_one_time_schedule') as mock_create_schedule, \
             patch('ingestor.handler.create_window') as mock_create_window:
            
            mock_send.return_value = 'message-id-123'
            mock_check_window.return_value = None
            mock_create_schedule.return_value = 'arn:aws:scheduler:us-east-1:123456789012:schedule/new'
            mock_create_window.return_value = True
            
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert
            assert result['success'] is True
            
            # Verify schedule creation WAS called
            mock_create_schedule.assert_called_once()
            mock_create_window.assert_called_once_with('arn:aws:scheduler:us-east-1:123456789012:schedule/new')
    
    def test_window_tracking_error_does_not_fail_processing(self):
        """Test that window tracking errors don't fail the entire operation."""
        # Arrange
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        with patch('ingestor.handler.send_event_to_queue') as mock_send, \
             patch('ingestor.handler.check_active_window') as mock_check_window:
            
            mock_send.return_value = 'message-id-123'
            mock_check_window.side_effect = Exception("DynamoDB error")
            
            # Act
            result = process_s3_record(record, queue_url)
            
            # Assert - processing should still succeed
            assert result['success'] is True
    
    def test_parse_error_handling(self):
        """Test handling of S3 event parse errors."""
        # Arrange
        record = {
            's3': {
                'bucket': {},  # Missing 'name'
                'object': {'key': '/prod/public/images/logo.png'}
            },
            'eventTime': '2025-12-09T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        # Act
        result = process_s3_record(record, queue_url)
        
        # Assert
        assert result['success'] is False
        assert 'parse error' in result['message'].lower()


class TestHandler:
    """Tests for Lambda handler function."""
    
    def test_handler_with_valid_event(self):
        """Test handler with valid S3 event."""
        # Arrange
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': '/prod/public/images/logo.png'}
                },
                'eventTime': '2025-12-09T10:30:00.000Z',
                'eventName': 'ObjectCreated:Put'
            }]
        }
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        with patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}), \
             patch('ingestor.handler.send_event_to_queue') as mock_send, \
             patch('ingestor.handler.check_active_window') as mock_check_window, \
             patch('ingestor.handler.create_one_time_schedule') as mock_create_schedule, \
             patch('ingestor.handler.create_window') as mock_create_window:
            
            mock_send.return_value = 'message-id-123'
            mock_check_window.return_value = None
            mock_create_schedule.return_value = 'arn:aws:scheduler:us-east-1:123456789012:schedule/test'
            mock_create_window.return_value = True
            
            # Act
            response = handler(event, context)
            
            # Assert
            assert response['statusCode'] == 200
            assert 'successfully' in response['body'].lower()
    
    def test_handler_with_no_records(self):
        """Test handler with empty Records array."""
        # Arrange
        event = {'Records': []}
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        with patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}):
            # Act
            response = handler(event, context)
            
            # Assert
            assert response['statusCode'] == 200
            assert 'no records' in response['body'].lower()
    
    def test_handler_with_multiple_records(self):
        """Test handler with multiple S3 event records."""
        # Arrange
        event = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-bucket-1'},
                        'object': {'key': '/prod/public/file1.png'}
                    },
                    'eventTime': '2025-12-09T10:30:00.000Z',
                    'eventName': 'ObjectCreated:Put'
                },
                {
                    's3': {
                        'bucket': {'name': 'test-bucket-2'},
                        'object': {'key': '/stage/public/file2.png'}
                    },
                    'eventTime': '2025-12-09T10:31:00.000Z',
                    'eventName': 'ObjectCreated:Put'
                }
            ]
        }
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        with patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}), \
             patch('ingestor.handler.send_event_to_queue') as mock_send, \
             patch('ingestor.handler.check_active_window') as mock_check_window, \
             patch('ingestor.handler.create_one_time_schedule') as mock_create_schedule, \
             patch('ingestor.handler.create_window') as mock_create_window:
            
            mock_send.return_value = 'message-id-123'
            mock_check_window.return_value = None
            mock_create_schedule.return_value = 'arn:aws:scheduler:us-east-1:123456789012:schedule/test'
            mock_create_window.return_value = True
            
            # Act
            response = handler(event, context)
            
            # Assert
            assert response['statusCode'] == 200
            assert '2' in response['body']  # Should mention 2 records
    
    def test_handler_missing_queue_url(self):
        """Test handler when QUEUE_URL environment variable is missing."""
        # Arrange
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': '/prod/public/images/logo.png'}
                },
                'eventTime': '2025-12-09T10:30:00.000Z',
                'eventName': 'ObjectCreated:Put'
            }]
        }
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        with patch.dict(os.environ, {}, clear=True):
            # Act
            response = handler(event, context)
            
            # Assert
            assert response['statusCode'] == 500
            assert 'configuration error' in response['body'].lower()


class TestGetQueueUrl:
    """Tests for get_queue_url function."""
    
    def test_get_queue_url_success(self):
        """Test successful retrieval of queue URL."""
        with patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}):
            url = get_queue_url()
            assert url == 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
    
    def test_get_queue_url_missing(self):
        """Test error when QUEUE_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="QUEUE_URL"):
                get_queue_url()
