"""Unit tests for MockLambdaContext fixture."""

import json
import pytest
from tests.conftest import MockLambdaContext


class TestMockLambdaContext:
    """Test suite for MockLambdaContext fixture."""
    
    def test_default_attributes(self):
        """Test that MockLambdaContext has all required attributes with defaults."""
        context = MockLambdaContext()
        
        assert context.function_name == 'test-function'
        assert context.function_version == '$LATEST'
        assert context.memory_limit_in_mb == 128
        assert context.aws_request_id == 'test-request-id'
        assert context.invoked_function_arn == 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
        assert context.log_group_name == '/aws/lambda/test-function'
        assert context.log_stream_name == '2024/01/01/[$LATEST]test-stream'
    
    def test_custom_attributes(self):
        """Test that MockLambdaContext accepts custom attribute values."""
        context = MockLambdaContext(
            function_name='custom-function',
            function_version='v1.0',
            memory_limit_in_mb=256,
            aws_request_id='custom-request-id',
            remaining_time_ms=150000
        )
        
        assert context.function_name == 'custom-function'
        assert context.function_version == 'v1.0'
        assert context.memory_limit_in_mb == 256
        assert context.aws_request_id == 'custom-request-id'
        assert context.get_remaining_time_in_millis() == 150000
    
    def test_get_remaining_time_in_millis_returns_integer(self):
        """Test that get_remaining_time_in_millis() returns an integer."""
        context = MockLambdaContext(remaining_time_ms=300000)
        
        remaining_time = context.get_remaining_time_in_millis()
        
        assert isinstance(remaining_time, int)
        assert remaining_time == 300000
    
    def test_context_is_json_serializable(self):
        """Test that MockLambdaContext attributes can be JSON serialized."""
        context = MockLambdaContext()
        
        # Create a dict with context attributes (simulating what logger does)
        context_dict = {
            'functionName': context.function_name,
            'functionVersion': context.function_version,
            'memoryLimitInMB': context.memory_limit_in_mb,
            'remainingTimeInMillis': context.get_remaining_time_in_millis(),
            'awsRequestId': context.aws_request_id,
            'invokedFunctionArn': context.invoked_function_arn,
            'logGroupName': context.log_group_name,
            'logStreamName': context.log_stream_name
        }
        
        # Should not raise TypeError
        json_str = json.dumps(context_dict)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed['functionName'] == 'test-function'
        assert parsed['memoryLimitInMB'] == 128
    
    def test_context_info_dict_serialization(self):
        """Test that context info dict (as used in handler) is JSON serializable."""
        context = MockLambdaContext()
        
        # Simulate what the handler does
        context_info = {
            'functionName': context.function_name if context else 'unknown',
            'functionVersion': context.function_version if context else 'unknown',
            'memoryLimitInMB': context.memory_limit_in_mb if context else 'unknown',
            'remainingTimeInMillis': context.get_remaining_time_in_millis() if context else 'unknown'
        }
        
        # Should not raise TypeError
        json_str = json.dumps(context_info)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed['functionName'] == 'test-function'
        assert parsed['remainingTimeInMillis'] == 300000


class TestLambdaContextFixture:
    """Test suite for lambda_context pytest fixture."""
    
    def test_lambda_context_fixture(self, lambda_context):
        """Test that lambda_context fixture provides a MockLambdaContext."""
        assert isinstance(lambda_context, MockLambdaContext)
        assert lambda_context.function_name == 'test-function'
        assert lambda_context.aws_request_id == 'test-request-id'
    
    def test_lambda_context_factory_fixture(self, lambda_context_factory):
        """Test that lambda_context_factory fixture creates custom contexts."""
        context = lambda_context_factory(
            function_name='factory-function',
            aws_request_id='factory-request-id'
        )
        
        assert isinstance(context, MockLambdaContext)
        assert context.function_name == 'factory-function'
        assert context.aws_request_id == 'factory-request-id'
    
    def test_lambda_context_factory_creates_multiple_contexts(self, lambda_context_factory):
        """Test that factory can create multiple independent contexts."""
        context1 = lambda_context_factory(aws_request_id='request-1')
        context2 = lambda_context_factory(aws_request_id='request-2')
        
        assert context1.aws_request_id == 'request-1'
        assert context2.aws_request_id == 'request-2'
        assert context1 is not context2
