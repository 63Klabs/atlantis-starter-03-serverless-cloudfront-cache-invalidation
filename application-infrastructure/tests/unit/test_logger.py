"""Unit tests for JSON logger utility."""

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest

from common.logger import ( # pyright: ignore[reportMissingImports]
    DateTimeEncoder,
    JSONFormatter,
    get_log_level,
    setup_logger,
    log_with_context
)


class TestDateTimeEncoder:
    """Tests for DateTimeEncoder class."""
    
    def test_encode_datetime(self):
        """Test encoding datetime objects to ISO format."""
        from datetime import datetime, timezone
        
        encoder = DateTimeEncoder()
        test_datetime = datetime(2023, 12, 15, 10, 30, 45, tzinfo=timezone.utc)
        
        # Test direct encoding
        result = encoder.default(test_datetime)
        assert result == test_datetime.isoformat()
    
    def test_encode_non_datetime(self):
        """Test that non-datetime objects raise TypeError."""
        encoder = DateTimeEncoder()
        
        with pytest.raises(TypeError):
            encoder.default("not a datetime")
    
    def test_json_dumps_with_datetime(self):
        """Test json.dumps with DateTimeEncoder handles datetime objects."""
        from datetime import datetime, timezone
        
        test_datetime = datetime(2023, 12, 15, 10, 30, 45, tzinfo=timezone.utc)
        data = {
            'message': 'test',
            'timestamp': test_datetime,
            'nested': {
                'LastModifiedTime': test_datetime
            }
        }
        
        # This should not raise an error
        result = json.dumps(data, cls=DateTimeEncoder)
        parsed = json.loads(result)
        
        assert parsed['timestamp'] == test_datetime.isoformat()
        assert parsed['nested']['LastModifiedTime'] == test_datetime.isoformat()


class TestJSONFormatter:
    """Tests for JSONFormatter class."""
    
    def test_format_basic_message(self):
        """Test formatting a basic log message as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['logger'] == 'test'
        assert 'timestamp' in log_data
        assert log_data['timestamp'].endswith('Z')
    
    def test_format_with_exception(self):
        """Test formatting a log message with exception info."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='',
            lineno=0,
            msg='Error occurred',
            args=(),
            exc_info=exc_info
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['level'] == 'ERROR'
        assert log_data['message'] == 'Error occurred'
        assert 'exception' in log_data
        assert 'ValueError: Test error' in log_data['exception']
    
    def test_format_with_extra_fields(self):
        """Test formatting a log message with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.extra_fields = {
            'bucket': 'test-bucket',
            'key': 'test-key'
        }
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['bucket'] == 'test-bucket'
        assert log_data['key'] == 'test-key'
    
    def test_format_with_datetime_objects(self):
        """Test formatting a log message with datetime objects in extra fields."""
        from datetime import datetime, timezone
        
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message with datetime',
            args=(),
            exc_info=None
        )
        
        test_datetime = datetime(2023, 12, 15, 10, 30, 45, tzinfo=timezone.utc)
        record.extra_fields = {
            'bucket': 'test-bucket',
            'LastModifiedTime': test_datetime,
            'distributionList': {
                'Items': [
                    {
                        'Id': 'E123456789',
                        'LastModifiedTime': test_datetime
                    }
                ]
            }
        }
        
        # This should not raise a JSON serialization error
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['bucket'] == 'test-bucket'
        assert log_data['LastModifiedTime'] == test_datetime.isoformat()
        assert log_data['distributionList']['Items'][0]['LastModifiedTime'] == test_datetime.isoformat()
    
    def test_format_with_non_serializable_object(self):
        """Test formatting a log message with non-serializable objects in extra fields."""
        from unittest.mock import Mock
        
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message with mock',
            args=(),
            exc_info=None
        )
        
        # Add a Mock object which is not JSON serializable
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-id'
        record.extra_fields = {
            'bucket': 'test-bucket',
            'context': mock_context
        }
        
        # This should not raise an error, but return valid JSON with error info
        result = formatter.format(record)
        log_data = json.loads(result)
        
        # Verify the log contains error information
        assert log_data['message'] == 'Test message with mock'
        assert log_data['level'] == 'INFO'
        assert '_serialization_error' in log_data
        assert log_data['extra_fields'] == '<non-serializable>'
    
    def test_format_with_circular_reference(self):
        """Test formatting a log message with circular references."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message with circular reference',
            args=(),
            exc_info=None
        )
        
        # Create a circular reference
        circular_dict = {'key': 'value'}
        circular_dict['self'] = circular_dict
        record.extra_fields = {
            'bucket': 'test-bucket',
            'circular': circular_dict
        }
        
        # This should not raise an error, but return valid JSON with error info
        result = formatter.format(record)
        log_data = json.loads(result)
        
        # Verify the log contains error information
        assert log_data['message'] == 'Test message with circular reference'
        assert log_data['level'] == 'INFO'
        assert '_serialization_error' in log_data
        assert log_data['extra_fields'] == '<non-serializable>'
    
    def test_format_handles_complete_serialization_failure(self):
        """Test formatting handles complete serialization failure gracefully."""
        formatter = JSONFormatter()
        
        # Create a record with a message that could cause issues
        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='',
            lineno=0,
            msg='Critical error',
            args=(),
            exc_info=None
        )
        
        # Add non-serializable object
        class NonSerializable:
            def __str__(self):
                raise Exception("Cannot convert to string")
        
        record.extra_fields = {
            'bad_object': NonSerializable()
        }
        
        # This should not crash, but return minimal valid JSON
        result = formatter.format(record)
        log_data = json.loads(result)
        
        # Verify we get some valid output
        assert 'message' in log_data
        assert 'level' in log_data
        assert log_data['level'] == 'ERROR'


class TestGetLogLevel:
    """Tests for get_log_level function."""
    
    def test_explicit_log_level(self):
        """Test that explicit LOG_LEVEL env var takes precedence."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'WARNING'}):
            assert get_log_level() == 'WARNING'
    
    def test_prod_environment(self):
        """Test log level for PROD environment."""
        with patch.dict(os.environ, {'DEPLOY_ENVIRONMENT': 'PROD'}, clear=True):
            assert get_log_level() == 'INFO'
    
    def test_test_environment(self):
        """Test log level for TEST environment."""
        with patch.dict(os.environ, {'DEPLOY_ENVIRONMENT': 'TEST'}, clear=True):
            assert get_log_level() == 'DEBUG'
    
    def test_dev_environment(self):
        """Test log level for DEV environment."""
        with patch.dict(os.environ, {'DEPLOY_ENVIRONMENT': 'DEV'}, clear=True):
            assert get_log_level() == 'DEBUG'
    
    def test_default_environment(self):
        """Test log level when no environment is set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_log_level() == 'DEBUG'


class TestSetupLogger:
    """Tests for setup_logger function."""
    
    def test_logger_creation(self):
        """Test that logger is created with correct configuration."""
        logger = setup_logger('test_logger')
        
        assert logger.name == 'test_logger'
        assert len(logger.handlers) > 0
        assert isinstance(logger.handlers[0].formatter, JSONFormatter)
    
    def test_logger_not_reconfigured(self):
        """Test that logger is not reconfigured if already configured."""
        logger1 = setup_logger('test_logger_2')
        handler_count = len(logger1.handlers)
        
        logger2 = setup_logger('test_logger_2')
        
        assert logger1 is logger2
        assert len(logger2.handlers) == handler_count
    
    def test_aws_sdk_logging_configured(self):
        """Test that AWS SDK logging is configured to WARNING level."""
        # Setup a logger to trigger AWS SDK logging configuration
        setup_logger('test_aws_sdk_logging')
        
        # Verify boto3/botocore loggers are set to WARNING
        assert logging.getLogger('boto3').level == logging.WARNING
        assert logging.getLogger('botocore').level == logging.WARNING
        assert logging.getLogger('urllib3').level == logging.WARNING
        assert logging.getLogger('urllib3.connectionpool').level == logging.WARNING


class TestLogWithContext:
    """Tests for log_with_context function."""
    
    def test_log_with_context_info(self, capsys):
        """Test logging with context at INFO level."""
        logger = setup_logger('test_context')
        
        log_with_context(
            logger,
            'info',
            'Test message',
            {'bucket': 'test-bucket', 'key': 'test-key'}
        )
        
        captured = capsys.readouterr()
        log_output = json.loads(captured.out.strip())
        
        assert log_output['message'] == 'Test message'
        assert log_output['level'] == 'INFO'
        assert log_output['bucket'] == 'test-bucket'
        assert log_output['key'] == 'test-key'
    
    def test_log_without_context(self, capsys):
        """Test logging without context."""
        logger = setup_logger('test_no_context')
        
        log_with_context(logger, 'info', 'Simple message')
        
        captured = capsys.readouterr()
        log_output = json.loads(captured.out.strip())
        
        assert log_output['message'] == 'Simple message'
        assert log_output['level'] == 'INFO'
