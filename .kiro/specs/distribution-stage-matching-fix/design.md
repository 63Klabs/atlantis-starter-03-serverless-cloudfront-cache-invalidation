# Distribution Stage Matching Fix - Design Document

## Overview

This design document specifies the minimal surgical changes required to fix the distribution stage matching bug in the Lambda Processor. The bug causes events from different stages (e.g., prod, beta) to be incorrectly grouped together, resulting in invalidations being sent to the wrong CloudFront distributions.

**Design Principle**: Make the absolute minimum changes necessary to fix the bug while preserving all existing functionality.

## Architecture Context

### Current System (Working Components)

The Lambda Processor has a complex, well-tested flow that is working correctly:

```
SQS Messages → Parse → Group → Validate Bucket → Resolve Pattern → 
Filter Events → Find Distributions → Validate Distributions → 
Consolidate Paths → Submit Invalidations → Delete Messages → Close Window
```

**What's Working Perfectly** (DO NOT MODIFY):
- ✅ Path consolidation algorithm with thresholds and stop levels
- ✅ Distribution matching by domain name AND origin path
- ✅ Tag validation for buckets and distributions
- ✅ Pattern resolution and event filtering
- ✅ Invalidation submission and chunking
- ✅ Message handling and deletion
- ✅ Window tracking

**What's Broken** (ONLY THIS):
- ❌ Event grouping uses 2-tuple `(bucket, origin_path)` instead of 3-tuple `(bucket, origin_path, stage)`
- ❌ Stage ID extracted from first event instead of group key
- ❌ Multiple stages get mixed in same group

## Design Solution

### High-Level Approach

**Change the grouping key from 2-tuple to 3-tuple**:
- Before: `(bucketName, originPath)` → groups prod and beta together
- After: `(bucketName, originPath, stageId)` → separates prod and beta

This single change cascades through the handler to ensure each stage is processed independently.

### Detailed Design

#### 1. Function: `group_messages_by_bucket_and_origin()`

**Location**: `application-infrastructure/functions/processor/handler.py` (lines ~50-200)

**Current Signature**:
```python
def group_messages_by_bucket_and_origin(
    messages: List[Dict[str, Any]]
) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
```

**New Signature**:
```python
def group_messages_by_bucket_and_origin(
    messages: List[Dict[str, Any]]
) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
```

**Changes Required**:

1. **Extract stage ID from each message**:
```python
# Current code (lines ~120-130):
bucket_name = parsed_body.get('bucketName')
origin_path = parsed_body.get('originPath')

# Add this line:
stage_id = parsed_body.get('stageId', '')  # Default to empty string if missing
```

2. **Update grouping key**:
```python
# Current code (line ~140):
group_key = (bucket_name, origin_path)

# Change to:
group_key = (bucket_name, origin_path, stage_id)
```

3. **Update skip validation**:
```python
# Current code (line ~145):
if not bucket_name or not origin_path:
    # skip message

# Keep as-is (stage_id can be empty string, that's valid)
# Empty stage_id means "no stage" and should be grouped separately
```

4. **Update docstring**:
```python
"""Group SQS messages by bucketName, originPath, and stageId.

Groups events to enable batch processing of invalidations for the same
bucket, origin, and stage combination. This ensures different stages
are processed independently with their own distribution searches.

Args:
    messages: List of SQS messages with parsed_body containing:
        - bucketName: S3 bucket name
        - objectKey: Full S3 object key
        - originPath: Origin path (/<StageId>/public)
        - stageId: Stage identifier (may be empty string)
        - eventTime: ISO 8601 timestamp
        - eventType: S3 event type
        
Returns:
    Dictionary where:
        - Keys are tuples of (bucketName, originPath, stageId)
        - Values are lists of messages belonging to that group
"""
```

5. **Update logging** (optional but recommended):
```python
# Add stage_id to log messages:
logger.info(
    f"Grouped {len(messages)} messages into {len(grouped)} bucket/origin/stage combinations",
    extra={'extra_fields': {
        'total_messages': len(messages),
        'group_count': len(grouped),
        'groups': [
            {
                'bucket': bucket,
                'origin': origin,
                'stage': stage,  # ADD THIS
                'message_count': len(msgs)
            }
            for (bucket, origin, stage), msgs in grouped.items()
        ]
    }}
)
```

**Correctness Properties**:
- **Property 1**: Messages with same `(bucket, origin, stage)` are grouped together
- **Property 2**: Messages with different stages are in different groups
- **Property 3**: Messages with missing `stageId` are grouped separately (empty string)
- **Property 4**: All messages are assigned to exactly one group

#### 2. Function: `handler()` - Main Processing Loop

**Location**: `application-infrastructure/functions/processor/handler.py` (lines ~400-900)

**Change 1: Loop Unpacking** (line ~400):
```python
# Current code:
for (bucket_name, origin_path), messages in grouped_messages.items():

# Change to:
for (bucket_name, origin_path, stage_id), messages in grouped_messages.items():
```

**Change 2: Remove Stage Extraction** (lines ~550-560):
```python
# Current code (DELETE THESE LINES):
# Step 3.7: Resolve origin path for distribution lookup
# Extract stage ID from first filtered event
first_filtered_message = filtered_messages[0]
first_filtered_body = first_filtered_message.get('parsed_body', {})
stage_id = first_filtered_body.get('stageId', '')

# After deletion:
# Step 3.7: Resolve origin path for distribution lookup
# (stage_id already available from group key)
```

**Change 3: Update Logging** (multiple locations):

Add `stage_id` to all log messages in the group processing loop:

```python
# Line ~410:
logger.info(
    f"Step 3-8: Processing group {group_index}/{len(grouped_messages)}",
    extra={'extra_fields': {
        'groupIndex': group_index,
        'totalGroups': len(grouped_messages),
        'bucket_name': bucket_name,
        'origin_path': origin_path,
        'stage_id': stage_id,  # ADD THIS
        'message_count': len(messages),
        # ... rest
    }}
)

# Line ~570:
logger.info(
    f"Resolved origin path for distribution lookup",
    extra={'extra_fields': {
        'bucket_name': bucket_name,
        'bucket_pattern': bucket_pattern,
        'stage_id': stage_id,  # ADD THIS (already there, verify it's used)
        'resolved_origin_path': resolved_origin_path,
        # ... rest
    }}
)

# Line ~650:
logger.info(
    f"Step 4: Distribution search results",
    extra={'extra_fields': {
        'bucketName': bucket_name,
        'originPath': origin_path,
        'stage_id': stage_id,  # ADD THIS
        'resolvedOriginPath': resolved_origin_path,
        # ... rest
    }}
)

# Line ~680:
logger.warning(
    f"Distribution {dist_id} failed tag validation",
    extra={'extra_fields': {
        'distribution_id': dist_id,
        'bucket_name': bucket_name,
        'origin_path': origin_path,
        'stage_id': stage_id,  # ADD THIS
    }}
)

# Line ~850:
logger.info(
    f"Processing stage {stage} with {len(consolidated_path_chunks)} chunks",
    extra={'extra_fields': {
        'bucket_name': bucket_name,
        'stage': stage,
        'stage_id': stage_id,  # ADD THIS for correlation
        'chunk_count': len(consolidated_path_chunks)
    }}
)
```

**Correctness Properties**:
- **Property 5**: Each group is processed with its own `stage_id` from the group key
- **Property 6**: Distribution validation uses the group's `stage_id`, not first event's
- **Property 7**: All events in a group have the same `stage_id` (enforced by grouping)
- **Property 8**: Logging includes `stage_id` for traceability

#### 3. No Changes Required to Other Files

**Files that DO NOT need changes**:
- ❌ `distribution_finder.py` - Already matches by origin path correctly
- ❌ `path_consolidator.py` - Consolidation algorithm is perfect
- ❌ `tag_validator.py` - Validation logic is correct
- ❌ `pattern_resolver.py` - Pattern resolution works correctly
- ❌ `invalidation_client.py` - Invalidation submission is correct
- ❌ `queue_client.py` - Message handling is correct

## Data Flow

### Before Fix (Broken)

```
Event 1: bucket=A, path=/prod/public, stage=prod, file=x.js
Event 2: bucket=A, path=/beta/public, stage=beta, file=y.js

↓ Grouping (2-tuple)
Group 1: (A, /prod/public) → [Event 1, Event 2]  ❌ WRONG

↓ Processing Group 1
stage_id = "prod" (from Event 1)  ❌ WRONG
resolved_origin_path = /prod/public

↓ Find Distributions
Finds: [Dist-Prod, Dist-Beta] (both have bucket A)

↓ Validate Distributions
validate(Dist-Prod, "my-app", "prod") → ✅ PASS
validate(Dist-Beta, "my-app", "prod") → ❌ FAIL (expects "my-app-beta")

↓ Invalidate
Dist-Prod gets: [x.js, y.js]  ❌ WRONG (beta file on prod dist)
Dist-Beta gets: nothing  ❌ WRONG (beta file not invalidated)
```

### After Fix (Correct)

```
Event 1: bucket=A, path=/prod/public, stage=prod, file=x.js
Event 2: bucket=A, path=/beta/public, stage=beta, file=y.js

↓ Grouping (3-tuple)
Group 1: (A, /prod/public, prod) → [Event 1]  ✅ CORRECT
Group 2: (A, /beta/public, beta) → [Event 2]  ✅ CORRECT

↓ Processing Group 1
stage_id = "prod" (from group key)  ✅ CORRECT
resolved_origin_path = /prod/public

↓ Find Distributions
Finds: [Dist-Prod, Dist-Beta] (both have bucket A)

↓ Validate Distributions
validate(Dist-Prod, "my-app", "prod") → ✅ PASS
validate(Dist-Beta, "my-app", "prod") → ❌ FAIL

↓ Invalidate
Dist-Prod gets: [x.js]  ✅ CORRECT

↓ Processing Group 2
stage_id = "beta" (from group key)  ✅ CORRECT
resolved_origin_path = /beta/public

↓ Find Distributions
Finds: [Dist-Prod, Dist-Beta] (both have bucket A)

↓ Validate Distributions
validate(Dist-Prod, "my-app", "beta") → ❌ FAIL
validate(Dist-Beta, "my-app", "beta") → ✅ PASS

↓ Invalidate
Dist-Beta gets: [y.js]  ✅ CORRECT
```

## Edge Cases

### 1. Missing Stage ID

**Scenario**: Event has no `stageId` field in `parsed_body`

**Handling**:
```python
stage_id = parsed_body.get('stageId', '')  # Empty string
group_key = (bucket_name, origin_path, '')  # Valid group
```

**Result**: Events without stage ID are grouped separately and processed together. This is correct behavior for root-level buckets without stage patterns.

### 2. Empty String Stage ID

**Scenario**: Event has `stageId: ""` explicitly

**Handling**: Same as missing - treated as empty string, grouped separately.

### 3. Mixed Stages in Same Batch

**Scenario**: SQS batch contains prod, beta, and staging events

**Handling**: Each stage gets its own group, processed independently. This is the desired behavior.

### 4. Single Stage Bucket

**Scenario**: Bucket only has prod stage, no beta

**Handling**: 
- Before: Grouped as `(bucket, /prod/public)` → works
- After: Grouped as `(bucket, /prod/public, prod)` → still works

**Backward Compatible**: ✅ Yes

### 5. Root-Level Bucket (No Stages)

**Scenario**: Bucket pattern is `/` (no `{stageId}`)

**Handling**:
- Events have `stageId: ""` (empty)
- Grouped as `(bucket, /, "")`
- Processed correctly with empty stage

**Backward Compatible**: ✅ Yes

## Testing Strategy

### Unit Tests

**Test File**: `application-infrastructure/tests/unit/test_handler_grouping.py` (new file)

**Test Cases**:

1. **test_group_by_bucket_origin_stage_separates_stages**
   - Input: 2 events, same bucket/origin, different stages
   - Expected: 2 groups
   - Validates: Property 2

2. **test_group_by_bucket_origin_stage_combines_same_stage**
   - Input: 3 events, same bucket/origin/stage
   - Expected: 1 group with 3 messages
   - Validates: Property 1

3. **test_group_by_bucket_origin_stage_handles_missing_stage**
   - Input: 2 events, one with stage, one without
   - Expected: 2 groups (empty string is separate)
   - Validates: Property 3

4. **test_group_by_bucket_origin_stage_multiple_buckets_stages**
   - Input: 6 events (2 buckets × 3 stages)
   - Expected: 6 groups
   - Validates: Property 1, 2

5. **test_handler_uses_group_stage_not_first_event**
   - Mock: `validate_distribution_tags` to capture stage_id argument
   - Input: Group with stage="beta"
   - Expected: validate called with stage="beta"
   - Validates: Property 6

### Integration Tests

**Test File**: `application-infrastructure/tests/integration/test_multi_stage_invalidation.py` (new file)

**Test Cases**:

1. **test_multi_stage_bucket_separate_invalidations**
   - Setup: Bucket with prod and beta distributions
   - Input: Events for both stages
   - Expected: Prod dist gets prod paths, beta dist gets beta paths
   - Validates: End-to-end correctness

2. **test_single_stage_bucket_backward_compatible**
   - Setup: Bucket with only prod distribution
   - Input: Prod events only
   - Expected: Works exactly as before
   - Validates: Backward compatibility

3. **test_root_level_bucket_no_stages**
   - Setup: Bucket with pattern `/` (no stages)
   - Input: Events with empty stage
   - Expected: Invalidations work correctly
   - Validates: Root-level bucket support

### Regression Tests

**Requirement**: All existing tests must pass without modification

**Test Suites to Run**:
- `tests/unit/test_ingestor_handler.py` - Should pass (no changes)
- `tests/unit/test_processor_handler.py` - Should pass (compatible changes)
- `tests/unit/test_path_consolidator.py` - Should pass (no changes)
- `tests/unit/test_distribution_finder.py` - Should pass (no changes)
- `tests/integration/test_complete_enhanced_functionality.py` - Should pass
- `tests/property/test_properties_*.py` - Should all pass

## Deployment Strategy

### Phase 1: Code Changes
1. Update `group_messages_by_bucket_and_origin()` function
2. Update `handler()` loop and stage extraction
3. Update logging statements
4. Update docstrings and type hints

### Phase 2: Testing
1. Run all unit tests (existing + new)
2. Run all integration tests (existing + new)
3. Run all property-based tests
4. Manual testing with multi-stage bucket

### Phase 3: Deployment
1. Deploy to dev environment
2. Test with real multi-stage bucket
3. Verify CloudWatch logs show correct stage grouping
4. Deploy to staging
5. Deploy to production

### Rollback Plan

If issues are detected:
1. Revert the single commit (only 1 file changed)
2. Events will go back to incorrect grouping (known issue)
3. Fix can be re-applied after investigation

**Risk**: LOW - Changes are minimal and isolated

## Monitoring and Validation

### CloudWatch Logs

**What to Look For**:

1. **Grouping Logs**:
```json
{
  "message": "Grouped 10 messages into 3 bucket/origin/stage combinations",
  "groups": [
    {"bucket": "my-app", "origin": "/prod/public", "stage": "prod", "message_count": 5},
    {"bucket": "my-app", "origin": "/beta/public", "stage": "beta", "message_count": 3},
    {"bucket": "other", "origin": "/", "stage": "", "message_count": 2}
  ]
}
```

2. **Processing Logs**:
```json
{
  "message": "Step 3-8: Processing group 1/3",
  "bucket_name": "my-app",
  "origin_path": "/prod/public",
  "stage_id": "prod"  // ← Should match the group
}
```

3. **Distribution Validation Logs**:
```json
{
  "message": "Distribution tag validation passed for E1234567890ABC",
  "distribution_id": "E1234567890ABC",
  "expected_app_deployment_id": "my-app-prod"  // ← Should match stage
}
```

### Success Metrics

- ✅ Each stage creates separate groups in logs
- ✅ Distribution validation uses correct stage per group
- ✅ Invalidations target correct distributions
- ✅ No cross-stage contamination
- ✅ All existing single-stage buckets continue working

### Failure Indicators

- ❌ Multiple stages in same group
- ❌ Distribution validation failures for correct distributions
- ❌ Invalidations sent to wrong distributions
- ❌ Existing tests failing

## Correctness Properties Summary

### Grouping Properties
1. Messages with same `(bucket, origin, stage)` are grouped together
2. Messages with different stages are in different groups
3. Messages with missing `stageId` are grouped separately
4. All messages are assigned to exactly one group

### Processing Properties
5. Each group is processed with its own `stage_id` from the group key
6. Distribution validation uses the group's `stage_id`, not first event's
7. All events in a group have the same `stage_id` (enforced by grouping)
8. Logging includes `stage_id` for traceability

### Backward Compatibility Properties
9. Single-stage buckets continue to work correctly
10. Root-level buckets (no stages) continue to work correctly
11. All existing tests pass without modification
12. No changes to consolidation, matching, or validation logic

## Risk Assessment

**Overall Risk**: LOW

**Risk Factors**:
- ✅ Changes are minimal (15-20 lines in 1 file)
- ✅ Changes are isolated to grouping logic
- ✅ No changes to complex algorithms (consolidation, matching)
- ✅ Backward compatible with existing buckets
- ✅ Easy to test and validate
- ✅ Easy to rollback (single commit)

**Mitigation**:
- Comprehensive unit tests for new grouping logic
- Integration tests for multi-stage scenarios
- Regression tests to ensure nothing breaks
- Gradual rollout (dev → staging → prod)
- Monitoring and validation in each environment

## Implementation Checklist

- [ ] Update `group_messages_by_bucket_and_origin()` function signature
- [ ] Add `stage_id` extraction in grouping function
- [ ] Update grouping key to 3-tuple
- [ ] Update function docstring
- [ ] Update handler loop to unpack 3-tuple
- [ ] Remove stage extraction from first event
- [ ] Add `stage_id` to all relevant log messages
- [ ] Write unit tests for grouping logic
- [ ] Write integration tests for multi-stage scenarios
- [ ] Run all existing tests (verify they pass)
- [ ] Update any affected test mocks
- [ ] Manual testing with multi-stage bucket
- [ ] Deploy to dev and validate
- [ ] Deploy to staging and validate
- [ ] Deploy to production and monitor

## Conclusion

This design provides a surgical fix for the distribution stage matching bug by changing the grouping key from a 2-tuple to a 3-tuple. The changes are minimal, isolated, and backward compatible. All existing functionality is preserved, and the fix enables correct multi-stage bucket support.

**Key Success Factors**:
- Minimal code changes (15-20 lines)
- No changes to working algorithms
- Comprehensive testing strategy
- Clear monitoring and validation plan
- Low risk with easy rollback
