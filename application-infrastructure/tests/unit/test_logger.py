"""Unit tests for JSON logger utility."""

import sys
import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from common.logger import (
    JSONFormatter,
    get_log_level,
    setup_logger,
    log_with_context
)


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
