# S3 API Optimization - Design Document

**Feature:** s3-api-optimization  
**Created:** January 30, 2026  
**Status:** Draft

---

## Architecture Overview

This design implements a **single fetch with shared state** pattern to eliminate redundant S3 API calls when retrieving bucket tags during processor Lambda execution.

### Current Architecture (Before)

```
handler()
  ├─> validate_bucket_tags(bucket_name)
  │    └─> get_bucket_tags(bucket_name) ← S3 API CALL #1
  │
  ├─> get_bucket_tags(bucket_name)       ← S3 API CALL #2
  │
  └─> get_bucket_consolidation_config(bucket_name)
       └─> get_bucket_tags(bucket_name) ← S3 API CALL #3
```

**Problem:** 3 API calls per bucket for identical data

### Proposed Architecture (After)

```
handler()
  ├─> get_bucket_tags(bucket_name)       ← S3 API CALL (once)
  │
  ├─> validate_bucket_tags_from_dict(tags)
  │
  └─> get_bucket_consolidation_config_from_dict(tags, bucket_name)
```

**Solution:** 1 API call per bucket, tags passed to functions

---

## Design Principles

1. **Explicit Data Flow:** Tags are explicitly fetched and passed, no hidden caching
2. **Backward Compatibility:** Existing functions remain unchanged for other use cases
3. **Fail Fast:** Tag fetch failures stop processing early with clear errors
4. **Testability:** New functions accept dictionaries, easy to unit test
5. **Minimal Changes:** Smallest possible change to achieve optimization

---

## Component Design

### 1. New Function: validate_bucket_tags_from_dict()

**Location:** `application-infrastructure/functions/processor/tag_validator.py`

**Purpose:** Validate bucket authorization from pre-fetched tags


**Signature:**
```python
def validate_bucket_tags_from_dict(tags: Optional[Dict[str, str]]) -> bool:
    """Validate bucket tags from pre-fetched tag dictionary.
    
    Checks that the bucket has AllowInvalidationEvents tag set to "true".
    This function does not make any API calls.
    
    Args:
        tags: Dictionary of bucket tags (key-value pairs), or None if fetch failed
        
    Returns:
        True if AllowInvalidationEvents=true, False otherwise
        
    **Validates: Requirements FR-2**
    """
```

**Implementation Logic:**
1. Check if tags is None → return False
2. Get 'AllowInvalidationEvents' tag value (default to empty string)
3. Return True if value equals "true", False otherwise
4. Log validation result with context

**Error Handling:**
- None input: Return False, log warning
- Missing tag: Return False, log warning
- Invalid value: Return False, log warning

**Testing Strategy:**
- Unit tests: Valid tags, invalid tags, None input, missing tag
- Property-based tests: Various tag value formats
- Integration tests: Handler usage verification

---

### 2. New Function: get_bucket_consolidation_config_from_dict()

**Location:** `application-infrastructure/functions/processor/tag_validator.py`

**Purpose:** Extract consolidation configuration from pre-fetched tags

**Signature:**
```python
def get_bucket_consolidation_config_from_dict(
    tags: Optional[Dict[str, str]], 
    bucket_name: str
) -> Dict[str, any]:
    """Get consolidation config from pre-fetched tag dictionary.
    
    Extracts DirectoryConsolidationThreshold, ConsolidationStopLevel, and
    SiblingDirectoryConsolidationThreshold from tags. Falls back to defaults
    for missing or invalid values. This function does not make any API calls.
    
    Args:
        tags: Dictionary of bucket tags (key-value pairs), or None if fetch failed
        bucket_name: Bucket name (for logging context only)
        
    Returns:
        Dictionary with keys:
        - 'directory_threshold': int
        - 'stop_level': int
        - 'sibling_directory_threshold': int
        - 'directory_threshold_source': 'tag' or 'default'
        - 'stop_level_source': 'tag' or 'default'
        - 'sibling_directory_threshold_source': 'tag' or 'default'
        
    **Validates: Requirements FR-3**
    """
```

**Implementation Logic:**
1. Initialize config with default values from constants
2. If tags is None, return default config with warning log
3. Extract 'invalidator:DirectoryConsolidationThreshold' tag
4. Validate and apply if valid (1-1000 range)
5. Extract 'invalidator:ConsolidationStopLevel' tag
6. Validate and apply if valid (0-20 range)
7. Extract 'invalidator:SiblingDirectoryConsolidationThreshold' tag
8. Validate and apply if valid (1-1000 range)
9. Log final configuration with sources
10. Return configuration dictionary

**Error Handling:**
- None input: Use defaults, log warning
- Invalid tag values: Use defaults, log warning with details
- Missing tags: Use defaults, log info

**Testing Strategy:**
- Unit tests: All tag combinations, invalid values, None input
- Property-based tests: Tag value validation logic
- Integration tests: Configuration application in handler

---

### 3. Handler Refactoring

**Location:** `application-infrastructure/functions/processor/handler.py`

**Purpose:** Fetch tags once per bucket and use new functions

**Current Code (Lines ~330-395):**
```python
# Step 3: Validate bucket tags
bucket_validation_result = validate_bucket_tags(bucket_name)

if not bucket_validation_result:
    # Skip bucket
    continue

# Get bucket tags for later use
bucket_tags = get_bucket_tags(bucket_name)

if not bucket_tags:
    # Skip bucket
    continue

# ... later ...

# Step 6: Get bucket-specific consolidation configuration
bucket_config = get_bucket_consolidation_config(bucket_name)
```

**New Code:**
```python
# Step 3: Fetch bucket tags once
bucket_tags = get_bucket_tags(bucket_name)

if bucket_tags is None:
    logger.error(
        f"Failed to retrieve bucket tags for {bucket_name}, skipping",
        extra={'extra_fields': {
            'bucket_name': bucket_name,
            'bucketTagsRetrievalFailed': True
        }}
    )
    messages_to_delete.extend(messages)
    continue

# Step 3.1: Validate bucket tags from fetched dictionary
bucket_validation_result = validate_bucket_tags_from_dict(bucket_tags)

if not bucket_validation_result:
    logger.warning(
        f"Bucket {bucket_name} failed tag validation, skipping",
        extra={'extra_fields': {
            'bucket_name': bucket_name,
            'bucketValidationFailed': True,
            'messagesBeingDeleted': len(messages)
        }}
    )
    summary['buckets_rejected'] += 1
    messages_to_delete.extend(messages)
    continue

summary['buckets_validated'] += 1

# ... later ...

# Step 6: Get bucket-specific consolidation configuration from fetched tags
try:
    bucket_config = get_bucket_consolidation_config_from_dict(bucket_tags, bucket_name)
    
    logger.info(
        f"Using consolidation configuration for bucket {bucket_name}",
        extra={'extra_fields': {
            'bucket_name': bucket_name,
            'directory_threshold': bucket_config['directory_threshold'],
            'stop_level': bucket_config['stop_level'],
            'sibling_directory_threshold': bucket_config['sibling_directory_threshold'],
            'directory_threshold_source': bucket_config['directory_threshold_source'],
            'stop_level_source': bucket_config['stop_level_source'],
            'sibling_directory_threshold_source': bucket_config['sibling_directory_threshold_source'],
            'operation': 'consolidation_config_applied'
        }}
    )
    
except Exception as e:
    logger.error(
        f"Failed to resolve consolidation configuration for bucket {bucket_name}, using defaults: {str(e)}",
        extra={'extra_fields': {
            'bucket_name': bucket_name,
            'error': str(e),
            'fallback_directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
            'fallback_stop_level': CONSOLIDATION_STOP_LEVEL,
            'fallback_sibling_directory_threshold': SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
            'fallback_reason': 'config_resolution_error'
        }}
    )
    
    bucket_config = {
        'directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
        'stop_level': CONSOLIDATION_STOP_LEVEL,
        'sibling_directory_threshold': SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
        'directory_threshold_source': 'default_fallback',
        'stop_level_source': 'default_fallback',
        'sibling_directory_threshold_source': 'default_fallback'
    }
```

**Key Changes:**
1. Single `get_bucket_tags()` call at the start
2. Early exit if tag fetch fails
3. Use `validate_bucket_tags_from_dict()` with fetched tags
4. Use `get_bucket_consolidation_config_from_dict()` with fetched tags
5. Remove redundant `get_bucket_tags()` calls

**Error Handling:**
- Tag fetch failure: Skip bucket, log error, delete messages
- Validation failure: Skip bucket, log warning, delete messages
- Config extraction failure: Use defaults, log error, continue processing

---

## Data Flow

### Sequence Diagram

```
┌─────────┐         ┌─────────┐         ┌──────────┐         ┌─────────┐
│ Handler │         │   S3    │         │Validator │         │  Config │
└────┬────┘         └────┬────┘         └────┬─────┘         └────┬────┘
     │                   │                   │                    │
     │ get_bucket_tags() │                   │                    │
     ├──────────────────>│                   │                    │
     │                   │                   │                    │
     │   tags dict       │                   │                    │
     │<──────────────────┤                   │                    │
     │                   │                   │                    │
     │ validate_bucket_tags_from_dict(tags)  │                    │
     ├──────────────────────────────────────>│                    │
     │                   │                   │                    │
     │   validation result                   │                    │
     │<──────────────────────────────────────┤                    │
     │                   │                   │                    │
     │ get_bucket_consolidation_config_from_dict(tags, name)      │
     ├───────────────────────────────────────────────────────────>│
     │                   │                   │                    │
     │   config dict     │                   │                    │
     │<───────────────────────────────────────────────────────────┤
     │                   │                   │                    │
```

**Key Points:**
- Single S3 API call per bucket
- Tags passed explicitly to all consumers
- No hidden state or caching
- Clear error propagation

---

## Error Handling Strategy

### Error Scenarios and Responses

| Scenario | Detection | Response | Logging |
|----------|-----------|----------|---------|
| S3 API failure | `get_bucket_tags()` returns None | Skip bucket, delete messages | ERROR level with details |
| No tags on bucket | `get_bucket_tags()` returns {} | Continue with empty dict | INFO level |
| Validation failure | `validate_bucket_tags_from_dict()` returns False | Skip bucket, delete messages | WARNING level |
| Invalid config tag | Tag value out of range | Use default value | WARNING level with tag details |
| Config extraction error | Exception in config function | Use all defaults | ERROR level with exception |

### Error Recovery

1. **Tag Fetch Failure:**
   - Log error with bucket name and error details
   - Skip all processing for that bucket
   - Mark messages for deletion (prevent reprocessing)
   - Continue with next bucket

2. **Validation Failure:**
   - Log warning with bucket name and tag values
   - Skip all processing for that bucket
   - Mark messages for deletion
   - Increment rejection counter
   - Continue with next bucket

3. **Config Extraction Failure:**
   - Log error with bucket name and exception
   - Use default configuration values
   - Continue processing with defaults
   - Track fallback in metrics

---

## Performance Analysis

### API Call Reduction

**Before Optimization:**
- Buckets processed: N
- API calls per bucket: 3
- Total API calls: 3N

**After Optimization:**
- Buckets processed: N
- API calls per bucket: 1
- Total API calls: N

**Reduction:** 67% (2N fewer calls)

### Latency Improvement

**Assumptions:**
- Average S3 API latency: 100ms
- Buckets per invocation: 5

**Before:**
- API time: 5 buckets × 3 calls × 100ms = 1500ms

**After:**
- API time: 5 buckets × 1 call × 100ms = 500ms

**Improvement:** 1000ms saved (67% reduction)

### Memory Impact

**Additional Memory:**
- Tag dictionary per bucket: ~1KB
- 5 buckets: ~5KB additional memory
- Negligible impact on Lambda memory usage

---

## Testing Strategy

### Unit Tests

**New Functions:**
```python
# test_tag_validator.py

def test_validate_bucket_tags_from_dict_valid():
    """Test validation with valid tags."""
    tags = {'AllowInvalidationEvents': 'true'}
    assert validate_bucket_tags_from_dict(tags) == True

def test_validate_bucket_tags_from_dict_invalid():
    """Test validation with invalid tags."""
    tags = {'AllowInvalidationEvents': 'false'}
    assert validate_bucket_tags_from_dict(tags) == False

def test_validate_bucket_tags_from_dict_none():
    """Test validation with None input."""
    assert validate_bucket_tags_from_dict(None) == False

def test_validate_bucket_tags_from_dict_missing():
    """Test validation with missing tag."""
    tags = {'SomeOtherTag': 'value'}
    assert validate_bucket_tags_from_dict(tags) == False

def test_get_bucket_consolidation_config_from_dict_with_tags():
    """Test config extraction with valid tags."""
    tags = {
        'invalidator:DirectoryConsolidationThreshold': '5',
        'invalidator:ConsolidationStopLevel': '2',
        'invalidator:SiblingDirectoryConsolidationThreshold': '15'
    }
    config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
    assert config['directory_threshold'] == 5
    assert config['stop_level'] == 2
    assert config['sibling_directory_threshold'] == 15
    assert config['directory_threshold_source'] == 'tag'

def test_get_bucket_consolidation_config_from_dict_defaults():
    """Test config extraction with no tags."""
    config = get_bucket_consolidation_config_from_dict({}, 'test-bucket')
    assert config['directory_threshold'] == DIRECTORY_CONSOLIDATION_THRESHOLD
    assert config['directory_threshold_source'] == 'default'

def test_get_bucket_consolidation_config_from_dict_invalid_values():
    """Test config extraction with invalid tag values."""
    tags = {
        'invalidator:DirectoryConsolidationThreshold': 'invalid',
        'invalidator:ConsolidationStopLevel': '999'
    }
    config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
    assert config['directory_threshold'] == DIRECTORY_CONSOLIDATION_THRESHOLD
    assert config['stop_level'] == CONSOLIDATION_STOP_LEVEL
```

### Property-Based Tests

```python
# test_properties_tag_validation.py

from hypothesis import given, strategies as st

@given(st.dictionaries(st.text(), st.text()))
def test_validate_bucket_tags_from_dict_never_crashes(tags):
    """Property: Validation never crashes regardless of input."""
    result = validate_bucket_tags_from_dict(tags)
    assert isinstance(result, bool)

@given(st.text())
def test_consolidation_threshold_validation(value):
    """Property: Threshold validation handles any string input."""
    result = validate_consolidation_tag_value(value, 1, 1000)
    if result is not None:
        assert 1 <= result <= 1000
```

### Integration Tests

```python
# test_processor_handler.py

def test_handler_single_api_call_per_bucket(mock_s3, mock_sqs, mock_cloudfront):
    """Test that handler makes only one S3 API call per bucket."""
    call_count = {}
    
    def mock_get_bucket_tagging(**kwargs):
        bucket = kwargs['Bucket']
        call_count[bucket] = call_count.get(bucket, 0) + 1
        return {
            'TagSet': [
                {'Key': 'AllowInvalidationEvents', 'Value': 'true'},
                {'Key': 'atlantis:Application', 'Value': 'test-app'}
            ]
        }
    
    mock_s3.get_bucket_tagging = mock_get_bucket_tagging
    
    # Create test event with multiple buckets
    event = create_test_event_with_buckets(['bucket1', 'bucket2', 'bucket3'])
    
    # Process
    handler(event, mock_context)
    
    # Verify exactly 1 call per bucket
    assert call_count['bucket1'] == 1
    assert call_count['bucket2'] == 1
    assert call_count['bucket3'] == 1
```

---

## Deployment Strategy

### Phase 1: Development and Testing (Week 1)
- Implement new functions in tag_validator.py
- Add comprehensive unit tests
- Add property-based tests
- Achieve 100% code coverage

### Phase 2: Handler Integration (Week 1)
- Refactor handler to use new functions
- Add integration tests
- Verify API call reduction
- Performance testing

### Phase 3: Staging Deployment (Week 2)
- Deploy to staging environment
- Monitor CloudWatch metrics
- Verify API call reduction
- Performance validation

### Phase 4: Production Deployment (Week 2)
- Deploy to production with monitoring
- Track metrics for 48 hours
- Verify no regressions
- Document results

---

## Monitoring and Observability

### CloudWatch Metrics

**Custom Metrics:**
- `S3APICallsPerBucket` - Track calls per bucket
- `TagFetchDuration` - Time to fetch tags
- `ValidationFailures` - Count of validation failures

**Standard Metrics:**
- Lambda Duration - Track execution time
- Lambda Errors - Track error rate
- Lambda Invocations - Track invocation count

### CloudWatch Logs

**Key Log Messages:**
- "Fetching bucket tags for {bucket_name}" - Tag fetch start
- "Retrieved {count} tags for bucket: {bucket_name}" - Tag fetch success
- "Failed to retrieve bucket tags for {bucket_name}" - Tag fetch failure
- "Bucket tag validation passed/failed for {bucket_name}" - Validation result
- "Using consolidation configuration for bucket {bucket_name}" - Config applied

### Alarms

**Critical Alarms:**
- Lambda error rate > 1%
- Lambda duration > P99 baseline + 20%
- S3 API throttling errors

**Warning Alarms:**
- Tag fetch failures > 5% of buckets
- Validation failures > 10% of buckets

---

## Rollback Plan

### Rollback Triggers
- Error rate increase > 5%
- Performance degradation > 20%
- S3 API throttling
- Critical bugs discovered

### Rollback Procedure
1. Revert Lambda function code to previous version
2. Monitor metrics for 30 minutes
3. Verify error rate returns to baseline
4. Investigate root cause
5. Fix issues before redeployment

### Rollback Testing
- Test rollback procedure in staging
- Document rollback steps
- Ensure team knows rollback process

---

## Security Considerations

### IAM Permissions
No changes required - existing S3 GetBucketTagging permissions sufficient

### Data Handling
- Tags contain no sensitive data
- No PII in bucket tags
- Standard CloudWatch log retention applies

### API Rate Limiting
- Reduced API calls decrease throttling risk
- No new rate limit concerns introduced

---

## Documentation Updates

### Code Documentation
- Docstrings for new functions
- Inline comments for handler changes
- Type hints for all parameters

### Architecture Documentation
- Update ARCHITECTURE.md with optimization details
- Add sequence diagrams
- Document API call reduction

### Operational Documentation
- Update runbooks with new log messages
- Document new CloudWatch metrics
- Update troubleshooting guides

---

## Correctness Properties

### Property 1: Single Fetch Per Bucket
**Statement:** For each unique bucket name in a batch of messages, `get_bucket_tags()` is called exactly once.

**Validation:** Integration test tracking API call count per bucket

**Validates:** Requirements FR-1

---

### Property 2: Tag Dictionary Validation Equivalence
**Statement:** For any tag dictionary, `validate_bucket_tags_from_dict(tags)` returns the same result as `validate_bucket_tags(bucket_name)` would return if it fetched those tags.

**Validation:** Property-based test comparing both functions with same tag data

**Validates:** Requirements FR-2, FR-5

---

### Property 3: Configuration Extraction Equivalence
**Statement:** For any tag dictionary, `get_bucket_consolidation_config_from_dict(tags, name)` returns the same configuration as `get_bucket_consolidation_config(name)` would return if it fetched those tags.

**Validation:** Property-based test comparing both functions with same tag data

**Validates:** Requirements FR-3, FR-5

---

### Property 4: Error Handling Preservation
**Statement:** All error conditions handled by original functions are also handled by new functions with equivalent behavior.

**Validation:** Unit tests covering all error scenarios for both old and new functions

**Validates:** Requirements FR-4, FR-5

---

### Property 5: Performance Improvement
**Statement:** Lambda execution time decreases by at least 10% when processing the same event batch.

**Validation:** Performance tests comparing execution time before and after optimization

**Validates:** Requirements NFR-1

---

## Success Criteria

This design is considered successful when:

✅ S3 API calls reduced by 60-70% per Lambda invocation  
✅ Lambda execution time reduced by 10-20%  
✅ No increase in error rate  
✅ 100% test coverage for new code  
✅ All existing tests pass  
✅ CloudWatch metrics show improvement  
✅ Production deployment stable for 48 hours  

---

**Design Status:** Ready for Implementation  
**Next Step:** Create implementation tasks
