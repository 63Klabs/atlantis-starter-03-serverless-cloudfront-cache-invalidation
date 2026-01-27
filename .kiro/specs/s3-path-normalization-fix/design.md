# Design Document: S3 Path Normalization Fix

## Overview

This design addresses a critical path format mismatch in the CloudFront invalidation system. S3 events contain object keys without leading slashes (standard S3 format), but the pattern matching logic expects paths with leading slashes. This causes valid events to be filtered out incorrectly.

The solution normalizes S3 object keys by adding a leading slash immediately after extraction from events. This ensures consistent path handling throughout the system while maintaining compatibility with CloudFront's invalidation path requirements.

### Key Design Decisions

1. **Normalize at extraction point**: Add leading slash in `event_parser.py` immediately after extracting the object key from S3 events
2. **Single normalization point**: Perform normalization once at the entry point to avoid repeated transformations
3. **Preserve CloudFront compatibility**: Maintain leading slashes through the entire pipeline since CloudFront expects them
4. **Fix test utility**: Update `upload-test-files.py` to generate S3 keys without leading slashes (matching S3 standard)
5. **Backward compatibility**: Ensure the fix works with existing bucket configurations without requiring changes

## Architecture

### Component Interaction Flow

```
S3 Event (objectKey: "app/prod/content/js/file.html")
    ↓
Event Parser (extract_event_metadata)
    ↓ [NORMALIZATION POINT]
Normalized Path ("/app/prod/content/js/file.html")
    ↓
Pattern Resolver (filter_events_by_pattern)
    ↓
Path Utils (matches_pattern)
    ↓
CloudFront Invalidation (path: "/app/prod/content/js/file.html")
```

### Affected Components

1. **functions/ingestor/event_parser.py**
   - `extract_event_metadata()`: Add normalization logic after extracting objectKey
   - Add helper function `normalize_s3_path()` for path normalization

2. **functions/processor/pattern_resolver.py**
   - `filter_events_by_pattern()`: Receives normalized paths, no changes needed
   - Logging: Update to show normalized paths

3. **layers/common/python/common/path_utils.py**
   - `matches_pattern()`: Already expects leading slashes, no changes needed
   - `extract_stage_from_path()`: Already expects leading slashes, no changes needed
   - `derive_pattern_from_path()`: Already expects leading slashes, no changes needed

4. **build-scripts/upload-test-files.py**
   - `PathGenerator.generate_upload_paths()`: Remove leading slashes from generated keys
   - `NestedStructureGenerator.generate_nested_structure()`: Remove leading slashes from generated keys
   - `S3Uploader.upload_file()`: Already strips leading slashes before upload, verify behavior

## Components and Interfaces

### Path Normalization Module

**Location**: `functions/ingestor/event_parser.py`

**New Function**: `normalize_s3_path(object_key: str) -> str`

```python
def normalize_s3_path(object_key: str) -> str:
    """
    Normalize an S3 object key by ensuring it has a leading slash.
    
    S3 object keys do not include leading slashes, but internal processing
    requires them for pattern matching and CloudFront invalidation paths.
    
    Args:
        object_key: S3 object key from event (e.g., "app/prod/content/js/file.html")
        
    Returns:
        Normalized path with leading slash (e.g., "/app/prod/content/js/file.html")
        
    Examples:
        >>> normalize_s3_path("app/prod/content/js/file.html")
        "/app/prod/content/js/file.html"
        
        >>> normalize_s3_path("/app/prod/content/js/file.html")
        "/app/prod/content/js/file.html"
        
        >>> normalize_s3_path("")
        ""
        
        >>> normalize_s3_path("//double/slash")
        "/double/slash"
    """
    if not object_key:
        return object_key
    
    # Add leading slash if not present
    if not object_key.startswith('/'):
        normalized = '/' + object_key
    else:
        normalized = object_key
    
    # Collapse multiple consecutive slashes to single slash
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
    
    return normalized
```

**Modified Function**: `extract_event_metadata(record: Dict) -> Dict[str, str]`

```python
def extract_event_metadata(record: Dict) -> Dict[str, str]:
    """Extract metadata from an S3 event record.
    
    Extracts bucketName, objectKey, eventTime, and eventType from an S3 event notification.
    Normalizes the objectKey by adding a leading slash for internal processing.
    
    Args:
        record: S3 event record from the Records array
        
    Returns:
        Dictionary containing:
            - bucketName: Name of the S3 bucket
            - objectKey: Normalized S3 object key with leading slash
            - eventTime: ISO 8601 timestamp of the event
            - eventType: S3 event type (e.g., ObjectCreated:Put)
            
    Raises:
        S3EventParseError: If required fields are missing or malformed
    """
    logger = setup_logger(__name__)
    
    try:
        bucket_name = record['s3']['bucket']['name']
        raw_object_key = record['s3']['object']['key']
        event_time = record['eventTime']
        event_type = record['eventName']
        
        # Normalize the object key by adding leading slash
        object_key = normalize_s3_path(raw_object_key)
        
        # Log normalization for debugging
        if raw_object_key != object_key:
            logger.debug(
                "Normalized S3 object key",
                extra={'extra_fields': {
                    'raw_key': raw_object_key,
                    'normalized_key': object_key
                }}
            )
        
        # Validate that all fields are non-empty strings
        if not all([bucket_name, object_key, event_time, event_type]):
            logger.error(
                "Validation failed - empty fields",
                extra={'extra_fields': {
                    'bucketNameEmpty': not bucket_name,
                    'objectKeyEmpty': not object_key,
                    'eventTimeEmpty': not event_time,
                    'eventTypeEmpty': not event_type
                }}
            )
            raise S3EventParseError("One or more required fields are empty")
        
        result = {
            'bucketName': bucket_name,
            'objectKey': object_key,  # Now normalized with leading slash
            'eventTime': event_time,
            'eventType': event_type
        }
        
        return result
        
    except KeyError as e:
        logger.error(
            "KeyError during extraction",
            extra={'extra_fields': {
                'missingKey': str(e),
                'recordStructure': record
            }}
        )
        raise S3EventParseError(f"Missing required field in S3 event: {e}")
    except TypeError as e:
        logger.error(
            "TypeError during extraction",
            extra={'extra_fields': {
                'typeError': str(e),
                'recordType': type(record).__name__
            }}
        )
        raise S3EventParseError(f"Invalid S3 event structure: {e}")
```

### Test File Generator Updates

**Location**: `build-scripts/upload-test-files.py`

**Modified Method**: `PathGenerator.generate_upload_paths()`

Current implementation generates paths like:
```python
s3_key = f"{base_path.rstrip('/')}/{dir_path}/{filename}"
# Example: "/prod/public/assets/test-ABC123.html"
```

Updated implementation should generate:
```python
# Remove leading slash from base_path before constructing key
clean_base = base_path.strip('/')
s3_key = f"{clean_base}/{dir_path}/{filename}" if clean_base else f"{dir_path}/{filename}"
# Example: "prod/public/assets/test-ABC123.html"
```

**Modified Method**: `NestedStructureGenerator.generate_nested_structure()`

Current implementation generates paths like:
```python
current_path = f"{base_path.rstrip('/')}/{root_dir}"
s3_key = f"{current_path}/{filename}"
# Example: "/prod/public/ABC12345/nested-XYZ789.html"
```

Updated implementation should generate:
```python
# Remove leading slash from base_path before constructing key
clean_base = base_path.strip('/')
current_path = f"{clean_base}/{root_dir}" if clean_base else root_dir
s3_key = f"{current_path}/{filename}"
# Example: "prod/public/ABC12345/nested-XYZ789.html"
```

**Verification**: `S3Uploader.upload_file()` and `S3Uploader.upload_with_retry()`

These methods already strip leading slashes before upload:
```python
clean_key = key.lstrip('/')
```

This behavior is correct and should be preserved. The methods will now receive keys without leading slashes, so the `lstrip('/')` becomes a safety measure.

## Data Models

### Event Metadata Structure

```python
{
    'bucketName': str,      # S3 bucket name
    'objectKey': str,       # Normalized path with leading slash
    'eventTime': str,       # ISO 8601 timestamp
    'eventType': str        # S3 event type
}
```

**Before Fix**:
```python
{
    'bucketName': 'my-bucket',
    'objectKey': 'app/prod/content/js/file.html',  # No leading slash
    'eventTime': '2024-01-15T10:30:00Z',
    'eventType': 'ObjectCreated:Put'
}
```

**After Fix**:
```python
{
    'bucketName': 'my-bucket',
    'objectKey': '/app/prod/content/js/file.html',  # Leading slash added
    'eventTime': '2024-01-15T10:30:00Z',
    'eventType': 'ObjectCreated:Put'
}
```

### S3 Upload Task Structure

```python
{
    'bucket': str,          # S3 bucket name
    'key': str,             # S3 object key WITHOUT leading slash
    'content': str,         # File content
    'filename': str         # Original filename for logging
}
```

**Before Fix**:
```python
{
    'bucket': 'my-bucket',
    'key': '/prod/public/assets/test-ABC123.html',  # Incorrect: has leading slash
    'content': '<html>...</html>',
    'filename': 'test-ABC123.html'
}
```

**After Fix**:
```python
{
    'bucket': 'my-bucket',
    'key': 'prod/public/assets/test-ABC123.html',  # Correct: no leading slash
    'content': '<html>...</html>',
    'filename': 'test-ABC123.html'
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Path Normalization Idempotence

*For any* S3 object key string, normalizing it once or multiple times should produce the same result with exactly one leading slash (unless the path is empty).

**Validates: Requirements 1.1, 1.2**

### Property 2: Pattern Matching with Normalized Paths

*For any* normalized path and any valid origin path pattern, the pattern matching function should correctly identify whether the path matches the pattern according to the pattern rules (root matches all, {stageId} matches with valid stages, literal patterns match prefixes).

**Validates: Requirements 2.2, 2.4**

### Property 3: Stage Extraction from Normalized Paths

*For any* normalized path and any pattern containing {stageId}, if the path matches the pattern, then extracting the stage identifier should return the correct stage value from the path.

**Validates: Requirements 2.3**

### Property 4: Invalidation Path Preserves Leading Slash

*For any* normalized path with a leading slash, creating a CloudFront invalidation path from it should preserve the leading slash in the resulting invalidation path.

**Validates: Requirements 3.1, 3.3**

### Property 5: Test File Keys Without Leading Slashes

*For any* test file path generated by the upload utility, the S3 object key should not start with a leading slash (matching S3 standard format).

**Validates: Requirements 4.1**

### Property 6: Upload Function Strips Leading Slashes

*For any* S3 object key passed to the upload function (with or without leading slash), the actual key used in the S3 API call should not have a leading slash.

**Validates: Requirements 4.2**

### Property 7: Generated Keys Match S3 Format

*For any* S3 object key generated by the test utility, it should conform to S3 standard format (no leading slash, valid characters, reasonable length).

**Validates: Requirements 4.4**

### Property 8: Tag Notation Conversion

*For any* bucket tag value containing @stageId@, the system should convert it to {stageId} for internal pattern matching.

**Validates: Requirements 5.2**

### Property 9: Multiple Slash Normalization

*For any* path containing multiple consecutive slashes, normalization should collapse them to single slashes while preserving the overall path structure.

**Validates: Requirements 6.2**

### Property 10: Trailing Slash Preservation

*For any* path with trailing slashes, normalization should preserve them (only leading slashes are added/normalized, trailing slashes remain unchanged).

**Validates: Requirements 6.3**

## Error Handling

### Path Normalization Errors

**Empty or Null Paths**:
- Empty strings return empty strings (no leading slash added)
- Null values are handled gracefully without throwing exceptions
- Log warning when encountering unexpected null values

**Malformed Paths**:
- Paths with only slashes (e.g., "///") are normalized to "/"
- Paths with unusual characters are preserved as-is (S3 allows many characters)
- URL-encoded characters are handled by S3 SDK automatically

**Error Recovery**:
- If normalization fails for a single event, log the error and continue processing other events
- Include original path in error logs for debugging
- Increment error metrics for monitoring

### Pattern Matching Errors

**Pattern Mismatch**:
- Log the event path, bucket pattern, and reason for mismatch
- Include structured logging fields for easy filtering
- Continue processing other events

**Invalid Patterns**:
- Validate patterns when loaded from bucket tags
- Fall back to ORIGIN_PATH_PATTERN if bucket tag is invalid
- Log warning about invalid pattern

### Upload Utility Errors

**Invalid Key Format**:
- Validate generated keys before upload
- Reject keys that exceed S3 length limits (1024 characters)
- Log validation failures with key details

**Upload Failures**:
- Retry with exponential backoff (already implemented)
- Log failures with bucket, key, and error details
- Continue with remaining uploads even if some fail

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests to ensure comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

### Unit Testing Focus

Unit tests should cover:

1. **Specific Examples**:
   - Normalize "app/prod/file.html" → "/app/prod/file.html"
   - Normalize "/app/prod/file.html" → "/app/prod/file.html" (idempotent)
   - Normalize "" → "" (empty string)
   - Normalize "/" → "/" (root path)

2. **Edge Cases**:
   - Multiple slashes: "app//prod///file.html" → "/app/prod/file.html"
   - Trailing slashes: "app/prod/" → "/app/prod/"
   - URL-encoded characters: "app/prod/file%20name.html" → "/app/prod/file%20name.html"

3. **Integration Points**:
   - Event parser extracts and normalizes object keys correctly
   - Pattern resolver receives normalized paths
   - Upload utility generates keys without leading slashes

4. **Error Conditions**:
   - Null object key handling
   - Malformed event structure
   - Invalid pattern formats

### Property-Based Testing Configuration

**Note**: Per repository testing guidelines, property-based tests are minimized in favor of fast-running unit tests. Property tests are only included for core validation logic where they provide significant value.

**Testing Library**: pytest with Hypothesis (Python's property-based testing library)

**Test Configuration**:
- Minimal iterations (10-20) to keep tests fast
- Each test tagged with feature name and property number
- Tag format: `# Feature: s3-path-normalization-fix, Property {N}: {property_text}`
- Total test suite should complete in under 30 seconds

**Limited Property Test Coverage** (only critical properties):

1. **Property 1: Path Normalization Idempotence** (CRITICAL)
   - Generate random strings (with/without leading slashes)
   - Verify normalize(normalize(x)) == normalize(x)
   - Verify normalized paths have exactly one leading slash (unless empty)
   - **Justification**: Core normalization logic with complex input space

2. **Property 9: Multiple Slash Normalization** (CRITICAL)
   - Generate paths with various slash patterns
   - Verify consecutive slashes collapse to single slashes
   - Verify path structure is preserved
   - **Justification**: Edge case handling that's difficult to cover exhaustively with unit tests

**Properties Covered by Unit Tests Instead**:
- Properties 2-8, 10: These will be thoroughly tested with concrete unit test examples rather than property-based tests
- Unit tests provide faster feedback and clearer failure messages
- Specific examples cover the most important cases without randomization overhead

### Test Execution

**Local Development**:
```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/unit/

# Run only property tests
pytest tests/property/ -v

# Run with coverage
pytest --cov=functions --cov=layers tests/
```

**CI/CD Pipeline**:
- Run all tests on every commit
- Fail build if any test fails
- Generate coverage reports
- Property tests run with 100 iterations minimum

### Test Organization

```
tests/
├── unit/
│   ├── test_event_parser.py          # Unit tests for event parsing and normalization
│   ├── test_pattern_resolver.py      # Unit tests for pattern matching
│   ├── test_path_utils.py            # Unit tests for path utilities
│   └── test_upload_utility.py        # Unit tests for upload utility
└── property/
    └── test_normalization_properties.py    # Minimal property tests (Properties 1, 9 only)
```

**Note**: Most validation is done through comprehensive unit tests rather than property-based tests to maintain fast test execution times.
