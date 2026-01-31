# Design Document

## Overview

This design addresses a critical bug in the processor Lambda function's stage extraction logic. The current implementation hardcodes extraction of the first path segment as the stage identifier, which fails when `{stageId}` appears at positions other than the first segment in the origin path pattern.

The fix is straightforward: replace the hardcoded logic (lines 502-512 in handler.py) with a call to the existing `extract_stage_from_path()` utility function from the common layer's `path_utils.py` module. This function correctly handles `{stageId}` placeholders at any position by parsing the pattern and extracting the corresponding segment from the object path.

## Architecture

### Current (Buggy) Implementation

```python
# Lines 502-512 in handler.py
stage_id = ''
if '{stageId}' in bucket_pattern:
    # Extract stage from object key
    # Pattern: /{stageId}/public -> extract first path segment
    parts = [p for p in object_key.split('/') if p]
    if len(parts) >= 1:
        # First non-empty segment is the stage
        stage_id = parts[0]
# else: no stage in pattern, use empty string
```

**Problem**: This always extracts `parts[0]`, regardless of where `{stageId}` appears in the pattern.

### Fixed Implementation

```python
# Import at top of file
from common.path_utils import extract_stage_from_path

# Replace lines 502-512 with:
stage_id = extract_stage_from_path(object_key, bucket_pattern)
```

**Solution**: The utility function finds the `{stageId}` position in the pattern and extracts the corresponding segment from the path.

## Components and Interfaces

### Modified Component: handler.py

**Location**: `application-infrastructure/functions/processor/handler.py`

**Changes**:
1. Add import statement for `extract_stage_from_path` from common layer
2. Replace hardcoded stage extraction logic (lines 502-512) with single function call
3. No changes to function signatures or return values

**Import Addition** (add to existing imports from common layer around line 17):
```python
from common.path_utils import extract_stage_from_path # pyright: ignore[reportMissingImports]
```

**Logic Replacement** (replace lines 502-512):
```python
# Extract stage from object key using the bucket pattern
stage_id = extract_stage_from_path(object_key, bucket_pattern)
```

### Existing Component: path_utils.py

**Location**: `application-infrastructure/layers/common/python/common/path_utils.py`

**No changes required** - this module already contains the correct implementation:

```python
def extract_stage_from_path(event_path: str, pattern: str) -> str:
    """
    Extract stage identifier from event path using pattern.
    
    Args:
        event_path: S3 object key
        pattern: Origin path pattern with {stageId} placeholder
    
    Returns:
        Stage identifier or empty string if not found
    """
    if '{stageId}' not in pattern:
        return ''
    
    # Split pattern and path into segments
    pattern_segments = pattern.strip('/').split('/')
    path_segments = event_path.strip('/').split('/')
    
    # Find {stageId} position in pattern
    try:
        stage_index = pattern_segments.index('{stageId}')
        if stage_index < len(path_segments):
            return path_segments[stage_index]
    except (ValueError, IndexError):
        pass
    
    return ''
```

## Data Models

No data model changes required. The function operates on existing data structures:

**Input Data**:
- `object_key` (str): S3 object path from message's parsed_body
- `bucket_pattern` (str): Origin path pattern resolved earlier in the handler

**Output Data**:
- `stage_id` (str): Extracted stage identifier or empty string

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Stage extraction matches pattern position

*For any* origin path pattern containing `{stageId}` at any position and any valid object path that matches the pattern, extracting the stage from the path should return the path segment at the same position where `{stageId}` appears in the pattern.

**Validates: Requirements 1.1, 1.2, 1.3, 1.5**

### Property 2: Empty stage for patterns without placeholder

*For any* origin path pattern that does not contain `{stageId}` and any object path, extracting the stage should return an empty string.

**Validates: Requirements 1.4**

### Property 3: Messages grouped by extracted stage

*For any* set of messages with object keys, when messages are filtered and grouped by stage, all messages with the same extracted stage identifier should be grouped together in the same stage group.

**Validates: Requirements 3.1, 3.3**

### Property 4: Downstream operations use extracted stage

*For any* message being processed, when distribution matching and tag validation occur, the stage identifier passed to these operations should match the stage identifier extracted from the object path using the bucket pattern.

**Validates: Requirements 3.4**

## Error Handling

### Existing Error Handling Preserved

The fix does not change error handling behavior:

1. **Missing object key**: Already handled by existing code that checks `if not sample_event_path`
2. **Pattern resolution failure**: Already handled by existing code that validates `bucket_pattern`
3. **Empty stage extraction**: Returns empty string, which is valid and handled by downstream code

### No New Error Cases

The `extract_stage_from_path()` function is defensive:
- Returns empty string if pattern doesn't contain `{stageId}`
- Returns empty string if extraction fails (ValueError, IndexError)
- Never raises exceptions

## Testing Strategy

### Unit Tests

**Focus**: Verify stage extraction with various pattern positions

**Test Cases**:
1. Stage at first position: `/{stageId}/public` with `/prod/public/file.html` → "prod"
2. Stage at second position: `/app/{stageId}/web` with `/app/prod/web/file.html` → "prod"
3. Stage at third position: `/app/web/{stageId}/public` with `/app/web/prod/public/file.html` → "prod"
4. No stage placeholder: `/public` with `/public/file.html` → ""
5. Multiple segments after stage: `/{stageId}/public` with `/dev/public/assets/images/file.html` → "dev"
6. Edge case - short path: `/{stageId}/public` with `/prod` → "prod"

**Implementation**: Add new test class to `test_handler.py` or create focused test file

### Integration Tests

**Focus**: Verify end-to-end processing with correct stage extraction

**Test Cases**:
1. Process messages with pattern `/app/web/{stageId}/web` and verify correct distribution matching
2. Process messages with pattern `/{stageId}/public` and verify correct tag validation
3. Process messages without `{stageId}` and verify empty stage handling
4. Process messages with multiple stages and verify correct grouping

**Implementation**: Extend existing integration tests or create new focused integration test

### Regression Tests

**Focus**: Ensure existing functionality is preserved

**Test Cases**:
1. Verify message grouping by stage still works correctly
2. Verify distribution matching uses extracted stage
3. Verify tag validation uses extracted stage
4. Verify logging includes correct stage information
5. Verify message deletion occurs for all processed messages

**Implementation**: Run existing test suite to ensure no regressions

### Test Configuration

- **Unit tests**: Fast-running, focused on stage extraction logic
- **Integration tests**: Test end-to-end flow with mocked AWS services
- **No property-based tests**: Per project guidelines, focus on concrete unit tests
- **Test execution**: All tests should complete in under 30 seconds total
