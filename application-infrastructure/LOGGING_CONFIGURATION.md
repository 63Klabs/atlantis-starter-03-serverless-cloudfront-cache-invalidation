# Logging Configuration

## Overview

The common logger module automatically configures boto3, botocore, and urllib3 logging to reduce verbosity. This prevents excessive DEBUG-level logs from AWS SDK operations cluttering your application logs.

Refer to template.yml for each Lambda function's `LOG_LEVEL` and `AWS_LAMBDA_LOG_LEVEL` settings. Typical settings rely on environment conditionals set in the template: `!If [ IsProduction, "INFO",  "DEBUG"]`

You can modify the common logger if you want more verbose AWS SDK logs.

## Implementation

### Automatic Configuration

When you call `setup_logger()`, it automatically configures AWS SDK logging:

```python
from common.logger import setup_logger

# This automatically sets boto3/botocore to WARNING level
logger = setup_logger(__name__)
```

### What Gets Configured

The following loggers are set to `WARNING` level:
- `boto3` - Main boto3 library
- `botocore` - Core AWS SDK functionality
- `urllib3` - HTTP library used by botocore
- `urllib3.connectionpool` - Connection pooling logs

This means you'll only see WARNING, ERROR, and CRITICAL logs from these libraries, not the verbose DEBUG and INFO logs.

## Why This Approach?

### Centralized Configuration
By configuring boto3 logging in the common logger module, you get:
- **Consistency**: All Lambda functions automatically have the same boto3 logging behavior
- **No Duplication**: No need to configure boto3 logging in each script
- **Easy Maintenance**: Change logging behavior in one place

### Alternative Approaches

If you need different boto3 logging levels for specific scripts, you have options:

#### Option 1: Override in Specific Scripts (After setup_logger)
```python
import logging
from common.logger import setup_logger

logger = setup_logger(__name__)

# Override for this script only
logging.getLogger('boto3').setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.DEBUG)
```

#### Option 2: Environment Variable Control
You could modify the common logger to respect an environment variable:

```python
# In common/logger.py
def _configure_aws_sdk_logging() -> None:
    """Configure AWS SDK logging based on environment."""
    # Allow override via environment variable
    boto_log_level = os.environ.get('BOTO_LOG_LEVEL', 'WARNING')
    level = getattr(logging, boto_log_level.upper())
    
    logging.getLogger('boto3').setLevel(level)
    logging.getLogger('botocore').setLevel(level)
    logging.getLogger('urllib3').setLevel(level)
    logging.getLogger('urllib3.connectionpool').setLevel(level)
```

Then in your Lambda environment variables:
```yaml
Environment:
  Variables:
    BOTO_LOG_LEVEL: DEBUG  # Only for debugging
```

#### Option 3: Per-Script Configuration (Not Recommended)
You could configure boto3 logging in each script, but this leads to:
- Code duplication
- Inconsistent behavior across functions
- More maintenance burden

## Testing Impact

### Tests Updated
The unit test `test_logger.py` includes a test to verify boto3 logging configuration:
```python
def test_aws_sdk_logging_configured(self):
    """Test that AWS SDK logging is configured to WARNING level."""
    setup_logger('test_aws_sdk_logging')
    
    assert logging.getLogger('boto3').level == logging.WARNING
    assert logging.getLogger('botocore').level == logging.WARNING
```

### No Test Changes Required
Existing tests don't need updates because:
- Tests don't assert on boto3/botocore log output
- Tests mock boto3 clients, so actual boto3 logging doesn't occur
- The configuration only affects log output, not functionality

## Usage Examples

### Standard Usage (Recommended)
```python
from common.logger import setup_logger
import boto3

logger = setup_logger(__name__)

# boto3 operations will only log WARNING and above
s3_client = boto3.client('s3')
response = s3_client.list_buckets()
```

### Debug Mode for Troubleshooting
```python
import logging
from common.logger import setup_logger
import boto3

logger = setup_logger(__name__)

# Temporarily enable boto3 debug logs for troubleshooting
logging.getLogger('boto3').setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.DEBUG)

s3_client = boto3.client('s3')
response = s3_client.list_buckets()  # Will show verbose boto3 logs
```

## Benefits

1. **Cleaner Logs**: Application logs focus on your code, not AWS SDK internals
2. **Better Performance**: Less log output means faster Lambda execution
3. **Easier Debugging**: Important messages aren't buried in boto3 debug output
4. **Cost Savings**: Reduced CloudWatch Logs storage costs

## Verification

To verify the configuration is working:

1. Run the demo script:
   ```bash
   python application-infrastructure/demo_logging.py
   ```

2. Check that no boto3 DEBUG logs appear in the output

3. Run unit tests:
   ```bash
   pytest application-infrastructure/tests/unit/test_logger.py -v
   ```

## Recommendation

**Use the centralized approach** (current implementation) for consistency across all Lambda functions. Only override in specific scripts when debugging AWS SDK issues.
