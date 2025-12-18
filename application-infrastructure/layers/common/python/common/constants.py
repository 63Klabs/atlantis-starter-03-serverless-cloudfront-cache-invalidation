"""Shared constants for the invalidation service."""

import os

def _get_validated_int_env(env_var: str, default: int, min_val: int, max_val: int) -> int:
    """Get and validate integer environment variable with fallback to default."""
    try:
        value = int(os.environ.get(env_var, str(default)))
        if min_val <= value <= max_val:
            return value
        else:
            return default
    except (ValueError, TypeError):
        return default

# Aggregation window configuration
AGGREGATION_WINDOW_SECONDS = _get_validated_int_env('AGGREGATION_WINDOW_SECONDS', 300, 1, 86400)  # 5 minutes default, max 24 hours

# Retry configuration
MAX_RETRY_ATTEMPTS_SQS = 3
MAX_RETRY_ATTEMPTS_DYNAMODB = 3
MAX_RETRY_ATTEMPTS_SCHEDULER = 3
MAX_RETRY_ATTEMPTS_CLOUDFRONT_LIST = 3
MAX_RETRY_ATTEMPTS_CLOUDFRONT_INVALIDATION = 5

# Exponential backoff configuration
RETRY_INITIAL_DELAY_MS = 100
RETRY_MAX_DELAY_MS = 5000
RETRY_BACKOFF_MULTIPLIER = 2
RETRY_JITTER_PERCENT = 0.25

# CloudFront limits
MAX_PATHS_PER_INVALIDATION = 1000
MAX_INVALIDATIONS_PER_DISTRIBUTION_PER_HOUR = 3000

# Path consolidation thresholds
DIRECTORY_CONSOLIDATION_THRESHOLD = _get_validated_int_env('DIRECTORY_CONSOLIDATION_THRESHOLD', 3, 1, 1000)
CONSOLIDATION_STOP_LEVEL = _get_validated_int_env('CONSOLIDATION_STOP_LEVEL', 1, 0, 1000)
SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD = 10

# SQS configuration
SQS_MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', '10'))
SQS_VISIBILITY_TIMEOUT_SECONDS = 300
SQS_LONG_POLL_WAIT_TIME_SECONDS = 20

# StageId patterns for production environments
PRODUCTION_STAGE_PREFIXES = ['p', 's', 'b']

# Path patterns
PUBLIC_PATH_SEGMENT = 'public'
ORIGIN_PATH_DEPTH = 3  # ['', stageId, 'public']

# Index and default file patterns
INDEX_FILE_PATTERNS = ['index.', 'default.']

# DynamoDB window tracking
WINDOW_ID_FIXED_VALUE = 'current'
WINDOW_STATUS_ACTIVE = 'active'
WINDOW_STATUS_CLOSED = 'closed'
WINDOW_TTL_BUFFER_SECONDS = 3600  # 1 hour after window end

# Log levels
LOG_LEVEL_PROD = 'INFO'
LOG_LEVEL_TEST = 'DEBUG'
LOG_LEVEL_DEV = 'DEBUG'