"""
Test configuration for simplified import structure.
Adds the layer path once for all tests to mirror Lambda runtime behavior.
"""
import sys
from pathlib import Path
import pytest

print(f"🔧 conftest.py loading from: {__file__}")

# Add layer path once for all tests - mirrors Lambda's /opt/python
layer_path = Path(__file__).parent.parent / "layers" / "common" / "python"
if str(layer_path) not in sys.path:
    sys.path.insert(0, str(layer_path))
    print(f"✅ Added layer path to sys.path: {layer_path}")
else:
    print(f"ℹ️  Layer path already in sys.path: {layer_path}")

# Add functions directory to path for function-specific imports
functions_path = Path(__file__).parent.parent / "functions"
if str(functions_path) not in sys.path:
    sys.path.insert(0, str(functions_path))
    print(f"✅ Added functions path to sys.path: {functions_path}")
else:
    print(f"ℹ️  Functions path already in sys.path: {functions_path}")

print(f"🔍 Current sys.path after conftest.py setup:")
for i, path in enumerate(sys.path[:10]):  # Show first 10 paths
    print(f"  {i}: {path}")

# Note: Individual function directories are not added to avoid module name conflicts.
# Each function's internal imports should work when the function is imported via its full path.


# ============================================================================
# Test Fixtures
# ============================================================================

class MockLambdaContext:
    """Mock Lambda context for testing.
    
    Provides a realistic Lambda context object that can be JSON serialized.
    All attributes and methods return JSON-serializable values.
    """
    
    def __init__(self, 
                 function_name='test-function',
                 function_version='$LATEST',
                 memory_limit_in_mb=128,
                 aws_request_id='test-request-id',
                 remaining_time_ms=300000,
                 invoked_function_arn='arn:aws:lambda:us-east-1:123456789012:function:test-function',
                 log_group_name='/aws/lambda/test-function',
                 log_stream_name='2024/01/01/[$LATEST]test-stream'):
        """Initialize mock Lambda context.
        
        Args:
            function_name: Name of the Lambda function
            function_version: Version of the Lambda function
            memory_limit_in_mb: Memory limit in MB
            aws_request_id: AWS request ID
            remaining_time_ms: Remaining execution time in milliseconds
            invoked_function_arn: ARN of the invoked function
            log_group_name: CloudWatch log group name
            log_stream_name: CloudWatch log stream name
        """
        self.function_name = function_name
        self.function_version = function_version
        self.memory_limit_in_mb = memory_limit_in_mb
        self.aws_request_id = aws_request_id
        self._remaining_time_ms = remaining_time_ms
        self.invoked_function_arn = invoked_function_arn
        self.log_group_name = log_group_name
        self.log_stream_name = log_stream_name
    
    def get_remaining_time_in_millis(self):
        """Return remaining execution time in milliseconds.
        
        Returns:
            int: Remaining time in milliseconds
        """
        return self._remaining_time_ms


@pytest.fixture
def lambda_context():
    """Pytest fixture providing a mock Lambda context.
    
    Returns:
        MockLambdaContext: A mock Lambda context with default values
    """
    return MockLambdaContext()


@pytest.fixture
def lambda_context_factory():
    """Pytest fixture providing a factory for creating custom Lambda contexts.
    
    Returns:
        callable: Factory function that creates MockLambdaContext instances
    """
    def _create_context(**kwargs):
        return MockLambdaContext(**kwargs)
    return _create_context
