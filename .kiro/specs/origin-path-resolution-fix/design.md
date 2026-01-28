# Design Document: Origin Path Resolution Fix

## Overview

This design addresses a defect in the CloudFront invalidation processor where the bucket's resolved origin path pattern is not being used when searching for CloudFront distributions. The current implementation calls `find_matching_distributions(bucket_name, origin_path)` using the `origin_path` from the event grouping (typically `/`), but it should use the resolved bucket pattern with the stage ID substituted.

The pattern resolution and event filtering are working correctly. The only issue is that the wrong origin path value is passed to `find_matching_distributions()`.

The fix is minimal: resolve the origin path from the bucket pattern (with stage substitution) and pass that to `find_matching_distributions()` instead of the event's origin path.

## Architecture

### Current Flow (Problematic)

```
1. Receive messages from SQS
2. Group messages by (bucket_name, event_origin_path)
3. For each group:
   a. Validate bucket tags
   b. Resolve bucket pattern (for filtering)
   c. Filter events by bucket pattern  ← Working correctly
   d. Find distributions using event_origin_path  ← BUG: Uses wrong path!
   e. Submit invalidations
```

### Fixed Flow

```
1. Receive messages from SQS
2. Group messages by (bucket_name, event_origin_path)
3. For each group:
   a. Validate bucket tags
   b. Resolve bucket pattern (for filtering)
   c. Filter events by bucket pattern  ← Working correctly
   d. Extract stage from filtered events
   e. Construct resolved origin path (replace {stageId} with actual stage)
   f. Find distributions using resolved_origin_path  ← FIXED!
   g. Submit invalidations
```

### Key Changes

The fix is minimal and surgical:

1. **After** `filter_events_by_pattern()` completes successfully
2. **Extract** the stage ID from the first filtered event
3. **Construct** the resolved origin path by replacing `{stageId}` in the bucket pattern with the actual stage
4. **Convert** root path `/` to empty string `""` (CloudFront convention)
5. **Pass** the resolved origin path to `find_matching_distributions()` instead of the event's origin path

No changes to pattern resolution or event filtering logic - those are working correctly.

## Components and Interfaces

### Modified Component: handler.py

#### Function: `handler(event, context)`

**Changes Required**:
- After `filter_events_by_pattern()` succeeds, add logic to construct resolved origin path
- Pass resolved origin path to `find_matching_distributions()` instead of `origin_path` variable

**New Logic** (inserted after existing filter_events_by_pattern call):
```python
# Existing code (already in place):
bucket_pattern = resolve_bucket_pattern(bucket_name, sample_event_path)
filtered_messages = filter_events_by_pattern(messages, bucket_pattern)

if not filtered_messages:
    logger.info(f"No events match bucket pattern for {bucket_name}, skipping")
    messages_to_delete.extend(messages)
    continue

# NEW CODE - Extract stage and construct resolved origin path
first_filtered_message = filtered_messages[0]
first_filtered_body = first_filtered_message.get('parsed_body', {})
stage_id = first_filtered_body.get('stageId', '')

# Construct resolved origin path for distribution lookup
if '{stageId}' in bucket_pattern:
    if not stage_id:
        logger.warning(
            f"Pattern contains {{stageId}} but no stage found for bucket {bucket_name}, skipping",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'bucket_pattern': bucket_pattern
            }}
        )
        messages_to_delete.extend(messages)
        continue
    resolved_origin_path = bucket_pattern.replace('{stageId}', stage_id)
else:
    resolved_origin_path = bucket_pattern

# Convert root path to empty string for CloudFront
if resolved_origin_path == '/':
    resolved_origin_path = ''

logger.info(
    f"Resolved origin path for distribution lookup",
    extra={'extra_fields': {
        'bucket_name': bucket_name,
        'bucket_pattern': bucket_pattern,
        'stage_id': stage_id,
        'resolved_origin_path': resolved_origin_path
    }}
)

# MODIFIED - Use resolved_origin_path instead of origin_path
distribution_ids = find_matching_distributions(bucket_name, resolved_origin_path)
```

### Unchanged Components

#### pattern_resolver.py
- `resolve_bucket_pattern()` - No changes needed
- `filter_events_by_pattern()` - No changes needed

#### distribution_finder.py
- `find_matching_distributions()` - No changes needed
- `_matches_bucket_origin()` - No changes needed

## Data Models

### Input Data

**SQS Message Structure** (unchanged):
```python
{
    'MessageId': str,
    'ReceiptHandle': str,
    'Body': str,  # JSON string
    'parsed_body': {
        'bucketName': str,
        'objectKey': str,  # Normalized with leading slash
        'originPath': str,  # From event, typically '/'
        'stageId': str,  # Extracted from object key
        'eventTime': str,
        'eventType': str
    }
}
```

### Internal Data

**Resolved Origin Path**:
- Type: `str`
- Format: Path with stage substituted (e.g., `/app/prod`)
- Special case: Empty string `""` for root path (CloudFront convention)

**Bucket Pattern**:
- Type: `str`
- Format: Path with `{stageId}` placeholder (e.g., `/app/{stageId}`)
- Source: Bucket tag `invalidator:OriginPathPattern` or default

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Bucket Pattern Takes Precedence

*For any* bucket with an `invalidator:OriginPathPattern` tag, the resolved origin path used for distribution search should be derived from the bucket's pattern, not the event's origin path.

**Validates: Requirements 1.1, 1.2**

### Property 2: Stage Substitution Correctness

*For any* bucket pattern containing `{stageId}` and events with a valid stage ID, the resolved origin path should have the placeholder replaced with the actual stage value.

**Validates: Requirements 1.3**

### Property 3: Root Path Normalization

*For any* resolved origin path equal to `/`, the value passed to `find_matching_distributions()` should be converted to an empty string `""` to match CloudFront's root origin convention.

**Validates: Requirements 5.2**

### Property 4: Fallback to Default Pattern

*For any* bucket without an `invalidator:OriginPathPattern` tag, the system should use the default ORIGIN_PATH_PATTERN environment variable for distribution search.

**Validates: Requirements 1.5, 5.1**

### Property 5: Pattern Without Placeholder

*For any* bucket pattern that does not contain `{stageId}`, the resolved origin path should equal the bucket pattern exactly (after root normalization).

**Validates: Requirements 4.1**

### Property 6: Missing Stage Handling

*For any* bucket pattern containing `{stageId}` where the stage ID cannot be extracted from events, the system should log a warning and skip those events without crashing.

**Validates: Requirements 4.2**

## Error Handling

### Error Scenarios

1. **Missing objectKey in First Message**
   - **Detection**: Check `first_parsed_body.get('objectKey', '')`
   - **Action**: Log error, add messages to deletion queue, continue to next group
   - **Logging**: Error level with bucket name and group details

2. **Missing stageId When Pattern Has Placeholder**
   - **Detection**: Check `stage_id` is empty when `'{stageId}' in bucket_pattern`
   - **Action**: Log warning, add messages to deletion queue, continue to next group
   - **Logging**: Warning level with bucket name, pattern, and event details

3. **Pattern Resolution Failure**
   - **Detection**: Exception from `resolve_bucket_pattern()`
   - **Action**: Log error, add messages to deletion queue, continue to next group
   - **Logging**: Error level with exception details

4. **Invalid Resolved Origin Path**
   - **Detection**: Check if resolved path is empty (after stage substitution)
   - **Action**: Log error, add messages to deletion queue, continue to next group
   - **Logging**: Error level with pattern and stage details

### Logging Requirements

All logging should include:
- Bucket name
- Original bucket pattern
- Extracted stage ID (if applicable)
- Resolved origin path
- Event count in group

Example log structure:
```python
logger.info(
    f"Resolved origin path for bucket {bucket_name}",
    extra={'extra_fields': {
        'bucket_name': bucket_name,
        'bucket_pattern': bucket_pattern,
        'stage_id': stage_id,
        'resolved_origin_path': resolved_origin_path,
        'event_count': len(messages),
        'operation': 'origin_path_resolution'
    }}
)
```

## Testing Strategy

### Unit Tests

Unit tests will verify specific scenarios and edge cases:

1. **Test: Bucket with stage-specific pattern**
   - Setup: Bucket with tag `invalidator:OriginPathPattern=/app/@stageId@`
   - Events: Messages with `stageId='prod'`
   - Expected: `find_matching_distributions()` called with `resolved_origin_path='/app/prod'`

2. **Test: Bucket with root pattern**
   - Setup: Bucket with tag `invalidator:OriginPathPattern=/`
   - Expected: `find_matching_distributions()` called with `resolved_origin_path=''` (empty string)

3. **Test: Bucket without pattern tag**
   - Setup: Bucket without `invalidator:OriginPathPattern` tag
   - Expected: `find_matching_distributions()` called with default ORIGIN_PATH_PATTERN

4. **Test: Pattern without stage placeholder**
   - Setup: Bucket with tag `invalidator:OriginPathPattern=/public`
   - Expected: `find_matching_distributions()` called with `resolved_origin_path='/public'`

5. **Test: Missing stageId with stage placeholder**
   - Setup: Bucket with pattern containing `{stageId}`, events missing `stageId`
   - Expected: Warning logged, events skipped, no crash

6. **Test: Missing objectKey**
   - Setup: First message missing `objectKey` field
   - Expected: Error logged, events skipped, no crash

7. **Test: Multiple stages in same bucket**
   - Setup: Events with different `stageId` values for same bucket
   - Expected: Each stage group processed separately with correct resolved path

### Integration Tests

Integration tests will verify end-to-end behavior:

1. **Test: Complete flow with stage-specific pattern**
   - Setup: Mock S3 bucket with pattern tag, mock CloudFront distributions
   - Execute: Process messages through handler
   - Verify: Correct distribution found and invalidation submitted

2. **Test: Backward compatibility**
   - Setup: Bucket without pattern tag, existing distributions
   - Execute: Process messages through handler
   - Verify: Existing behavior maintained

### Test Configuration

- **Framework**: pytest (Kiro's preferred framework)
- **Mocking**: Use `unittest.mock` for AWS service calls
- **Coverage**: Aim for 90%+ coverage of modified code paths
- **Fast execution**: All unit tests should complete in < 5 seconds total

### Property-Based Testing

Given the testing guidelines for this repository, property-based tests are marked as optional. The comprehensive unit tests above provide sufficient coverage for this fix.

If property-based tests are implemented, they should:
- Run with minimal iterations (10-20 instead of 100+)
- Focus on the core invariants (Properties 1-6 above)
- Be kept in separate test files for easy identification
