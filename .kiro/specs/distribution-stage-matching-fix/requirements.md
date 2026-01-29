# Distribution Stage Matching Fix - Requirements

## Problem Statement

The Lambda Processor currently has a critical bug in how it matches CloudFront distributions to S3 bucket stages. When a bucket has multiple distributions (one for each stage like `prod` and `beta`), the system incorrectly groups all events by bucket and origin path, then searches for distributions once per group. This causes the wrong distribution to be used for invalidations.

### Current Broken Flow

1. Events are grouped by `(bucketName, originPath)` - e.g., `(my-bucket, /prod/public)`
2. For each group, the system:
   - Resolves a single `resolved_origin_path` based on the first event's stage
   - Calls `find_matching_distributions(bucket_name, resolved_origin_path)` **once**
   - Gets back multiple distributions (e.g., prod and beta distributions)
   - Validates each distribution against the **first event's stage_id**
   - Only the distribution matching the first stage passes validation
   - All events in the group (which may include multiple stages) get invalidated on only that one distribution

### Example Failure Scenario

**Bucket**: `my-app-bucket`
**Distributions**:
- Distribution A: origin `my-app-bucket.s3.amazonaws.com` with path `/prod/public`, tags: `ApplicationDeploymentId=my-app-prod`
- Distribution B: origin `my-app-bucket.s3.amazonaws.com` with path `/beta/public`, tags: `ApplicationDeploymentId=my-app-beta`

**Events**:
- Event 1: `my-app-bucket`, key `/prod/public/file1.js`, stage `prod`
- Event 2: `my-app-bucket`, key `/beta/public/file2.js`, stage `beta`

**Current Behavior** (WRONG):
1. Both events grouped together as `(my-app-bucket, /prod/public)` because grouping uses the event's `originPath` field
2. System resolves origin path as `/prod/public` (from first event)
3. Finds both Distribution A and Distribution B (both have same bucket origin)
4. Validates distributions against stage `prod` (from first event)
5. Only Distribution A passes validation
6. Both files invalidated on Distribution A only
7. **Beta distribution never gets invalidated!**

## Root Cause Analysis

The problem occurs in `handler.py` at these key points:

1. **Line ~50-200**: `group_messages_by_bucket_and_origin()` groups by `(bucketName, originPath)` where `originPath` comes from the event metadata (e.g., `/prod/public`)

2. **Line ~400-500**: For each group, the system:
   - Extracts `stage_id` from the **first filtered message only**
   - Resolves a single `resolved_origin_path` for distribution lookup
   - Calls `find_matching_distributions()` once with that single origin path

3. **Line ~600-700**: Distribution validation uses the **first event's stage_id** to validate all distributions

4. **`distribution_finder.py`**: The `find_matching_distributions()` function matches distributions by bucket domain name only, not by origin path, so it returns ALL distributions for that bucket regardless of stage

## What's Already Working Correctly

**IMPORTANT**: The following components are working perfectly and must NOT be modified:

### ✅ Path Consolidation Algorithm
- `path_consolidator.py` correctly consolidates paths using thresholds
- Handles index/default files correctly
- Respects stop levels and sibling thresholds
- Bucket-specific configuration is working
- **DO NOT TOUCH THIS CODE**

### ✅ Distribution Matching by Origin Path
- `_matches_bucket_origin()` in `distribution_finder.py` already checks BOTH domain name AND origin path
- Correctly normalizes `""` and `"/"` as equivalent root paths
- Handles regional and global S3 domain formats
- **This function is correct - the problem is it's not being called with the right origin path per stage**

### ✅ Tag Validation Logic
- `validate_distribution_tags()` correctly validates `AllowInvalidationEvents` and `ApplicationDeploymentId`
- Correctly checks `<bucket-app>-<stageId>` pattern
- **This function is correct - the problem is it's being passed the wrong stage_id**

### ✅ Event Parsing and Filtering
- `pattern_resolver.py` correctly resolves bucket patterns
- `filter_events_by_pattern()` correctly filters events
- Stage ID extraction from object keys is working
- **DO NOT MODIFY THESE**

### ✅ Invalidation Submission
- `create_invalidation()` correctly submits to CloudFront
- Path chunking for 1000-path limit works correctly
- **DO NOT MODIFY THIS**

### ✅ Message Handling
- SQS message receiving works correctly
- Message deletion works correctly
- Receipt handle management is correct
- **DO NOT MODIFY THESE**

## The Actual Bug (Isolated)

The bug is **ONLY** in these specific locations:

1. **Grouping Key**: `group_messages_by_bucket_and_origin()` uses 2-tuple instead of 3-tuple
2. **Stage Extraction**: Handler extracts stage from first event instead of using group's stage
3. **Loop Structure**: Handler loop unpacks 2-tuple instead of 3-tuple

**That's it.** Everything else works perfectly.

## Visual Change Summary

### Before (BROKEN):
```
Events → Group by (bucket, origin_path) → Process each group:
                                            ├─ Extract stage from FIRST event
                                            ├─ Find distributions (gets ALL for bucket)
                                            ├─ Validate with FIRST event's stage
                                            └─ Invalidate (WRONG distributions get hit)

Example:
  prod event + beta event → grouped together
                         → stage = "prod" (from first)
                         → finds prod + beta distributions
                         → validates with "prod"
                         → only prod dist passes
                         → BOTH events hit prod dist ❌
```

### After (FIXED):
```
Events → Group by (bucket, origin_path, stage) → Process each group:
                                                  ├─ Use stage from GROUP KEY
                                                  ├─ Find distributions (gets ALL for bucket)
                                                  ├─ Validate with GROUP's stage
                                                  └─ Invalidate (CORRECT distributions)

Example:
  prod event → group (bucket, /prod/public, prod)
            → stage = "prod" (from group)
            → finds prod + beta distributions
            → validates with "prod"
            → only prod dist passes
            → prod event hits prod dist ✅
            
  beta event → group (bucket, /beta/public, beta)
            → stage = "beta" (from group)
            → finds prod + beta distributions
            → validates with "beta"
            → only beta dist passes
            → beta event hits beta dist ✅
```

## Code Changes Required (Exact Locations)

### Change 1: Function Signature
**File**: `handler.py`
**Function**: `group_messages_by_bucket_and_origin()`
**Line**: ~50

```python
# BEFORE:
def group_messages_by_bucket_and_origin(messages: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:

# AFTER:
def group_messages_by_bucket_and_origin(messages: List[Dict[str, Any]]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
```

### Change 2: Grouping Logic
**File**: `handler.py`
**Function**: `group_messages_by_bucket_and_origin()`
**Line**: ~120-140

```python
# BEFORE:
bucket_name = parsed_body.get('bucketName')
origin_path = parsed_body.get('originPath')
group_key = (bucket_name, origin_path)

# AFTER:
bucket_name = parsed_body.get('bucketName')
origin_path = parsed_body.get('originPath')
stage_id = parsed_body.get('stageId', '')  # NEW LINE
group_key = (bucket_name, origin_path, stage_id)  # MODIFIED LINE
```

### Change 3: Handler Loop
**File**: `handler.py`
**Function**: `handler()`
**Line**: ~400

```python
# BEFORE:
for (bucket_name, origin_path), messages in grouped_messages.items():

# AFTER:
for (bucket_name, origin_path, stage_id), messages in grouped_messages.items():
```

### Change 4: Remove Stage Extraction
**File**: `handler.py`
**Function**: `handler()`
**Line**: ~550-560

```python
# BEFORE (DELETE THESE LINES):
first_filtered_message = filtered_messages[0]
first_filtered_body = first_filtered_message.get('parsed_body', {})
stage_id = first_filtered_body.get('stageId', '')

# AFTER:
# (stage_id already available from group key - no extraction needed)
```

### Change 5: Update Logging
**File**: `handler.py`
**Function**: `handler()`
**Multiple locations**

```python
# Add stage_id to log messages:
logger.info(
    f"Step 3-8: Processing group {group_index}/{len(grouped_messages)}",
    extra={'extra_fields': {
        'bucket_name': bucket_name,
        'origin_path': origin_path,
        'stage_id': stage_id,  # ADD THIS
        # ... rest of fields
    }}
)
```

**Total Lines Changed**: ~15-20 lines across 5 locations
**Files Modified**: 1 file (`handler.py`)
**Functions Modified**: 2 functions (`group_messages_by_bucket_and_origin()`, `handler()`)
**Risk Level**: LOW (surgical changes only)

## User Stories

### 1. Multi-Stage Bucket Invalidation
**As a** developer deploying to multiple stages
**I want** CloudFront invalidations to target the correct distribution for each stage
**So that** beta deployments invalidate beta distributions and prod deployments invalidate prod distributions

**Acceptance Criteria**:
1.1. Events from different stages in the same bucket must be processed separately
1.2. Each stage's events must only invalidate the distribution matching that stage's origin path
1.3. Distribution search must filter by both bucket AND origin path
1.4. Distribution validation must use the stage from the events being processed, not just the first event

### 2. Correct Distribution Matching
**As a** system processing S3 events
**I want** to find distributions that match both the bucket origin AND the origin path
**So that** I don't send invalidations to the wrong stage's distribution

**Acceptance Criteria**:
2.1. `find_matching_distributions()` must match on both domain name AND origin path
2.2. A distribution with origin path `/prod/public` must NOT match events for `/beta/public`
2.3. Distribution matching must be case-sensitive for origin paths
2.4. Empty origin path (`""`) and root path (`"/"`) must be treated as equivalent

### 3. Stage-Specific Event Grouping
**As a** system grouping events for processing
**I want** to group events by bucket, origin path, AND stage
**So that** different stages are processed in separate batches

**Acceptance Criteria**:
3.1. Events must be grouped by `(bucketName, originPath, stageId)` tuple
3.2. Events for `prod` stage must be in a different group than `beta` stage
3.3. Each group must only contain events for a single stage
3.4. Grouping must handle missing or empty stage IDs gracefully

### 4. Distribution Validation Per Stage
**As a** system validating distributions
**I want** to validate each distribution against the correct stage for the events being processed
**So that** only the appropriate distribution receives invalidations

**Acceptance Criteria**:
4.1. Distribution validation must use the stage ID from the current event group
4.2. All events in a group must have the same stage ID (enforced by grouping)
4.3. Validation must check `ApplicationDeploymentId` matches `<bucket-app>-<stageId>`
4.4. Distributions that don't match the group's stage must be rejected

## Technical Requirements

### 5. Event Grouping Changes
**Requirement**: Modify `group_messages_by_bucket_and_origin()` to group by stage

**MINIMAL CHANGE APPROACH**:
- Change return type from `Dict[Tuple[str, str], List[Dict]]` to `Dict[Tuple[str, str, str], List[Dict]]`
- Change grouping key from `(bucket_name, origin_path)` to `(bucket_name, origin_path, stage_id)`
- Extract `stage_id` from `parsed_body.get('stageId', '')` for each message
- **That's the only change to this function**

5.1. Change grouping key from `(bucketName, originPath)` to `(bucketName, originPath, stageId)`
5.2. Extract `stageId` from each message's `parsed_body`
5.3. Handle missing `stageId` by using empty string as default
5.4. Log warning when `stageId` is missing from events
5.5. Update function docstring to reflect 3-tuple grouping
5.6. Update type hints to reflect new return type

### 6. Distribution Finder Changes
**Requirement**: Verify `find_matching_distributions()` works correctly (NO CHANGES NEEDED)

**VERIFICATION ONLY - NO CODE CHANGES**:
- The `_matches_bucket_origin()` function already checks origin path correctly
- It already normalizes `""` and `"/"` as root
- It already supports regional and global S3 domains
- **The bug is NOT in this file - it's being called correctly, just not per-stage**

6.1. Verify `_matches_bucket_origin()` checks both domain AND origin path (already does)
6.2. Verify origin path normalization handles both `""` and `"/"` as root (already does)
6.3. Verify regional and global S3 domain formats are both supported (already are)
6.4. Add logging to show which distributions were rejected due to origin path mismatch (optional enhancement)
6.5. **NO FUNCTIONAL CHANGES TO THIS FILE**

### 7. Handler Processing Changes
**Requirement**: Update handler to process stage-specific groups correctly

**MINIMAL CHANGE APPROACH**:
- Change loop from `for (bucket_name, origin_path), messages in grouped_messages.items():`
- To: `for (bucket_name, origin_path, stage_id), messages in grouped_messages.items():`
- Use `stage_id` from the tuple instead of extracting from first event
- **That's the primary change - just unpacking 3 values instead of 2**

7.1. Update loop to iterate over `(bucketName, originPath, stageId)` groups
7.2. Use the group's `stageId` for distribution validation (not first event's stage)
7.3. Remove the code that extracts `stage_id` from first filtered message (now comes from group key)
7.4. Update logging to include stage information in all relevant log messages
7.5. Ensure `resolved_origin_path` calculation uses the group's `stage_id`
7.6. **NO OTHER CHANGES TO HANDLER LOGIC**

### 8. Backward Compatibility
**Requirement**: Ensure changes don't break existing single-stage buckets

8.1. Buckets with only one stage must continue to work correctly
8.2. Buckets without stage patterns (root-level buckets) must continue to work
8.3. Existing distribution matching logic must not be broken for simple cases
8.4. All existing tests must continue to pass
8.5. Events without `stageId` must be grouped separately and processed correctly
8.6. Existing log analysis and monitoring must continue to work (log format preserved)

## Non-Functional Requirements

### 9. Performance
9.1. Grouping by stage must not significantly increase processing time
9.2. Distribution searches should be cached if the same bucket/origin/stage is processed multiple times
9.3. Memory usage must remain within Lambda limits even with many stage groups

### 10. Logging and Observability
10.1. Log the grouping key structure for debugging
10.2. Log when distributions are rejected due to origin path mismatch
10.3. Log when distributions are rejected due to stage mismatch
10.4. Include stage information in all invalidation success/failure logs

### 11. Error Handling
11.1. Handle missing `stageId` gracefully (use empty string, log warning)
11.2. Handle distributions with missing origin path tags
11.3. Continue processing other groups if one group fails
11.4. Ensure messages are deleted even if distribution matching fails

## Success Metrics

- All events for a given stage only invalidate distributions matching that stage
- No cross-stage invalidation pollution
- Distribution matching correctly filters by origin path
- Existing single-stage buckets continue to work without changes
- All unit and integration tests pass

## Testing Requirements

### 12. Comprehensive Regression Testing
**Requirement**: Ensure no existing functionality is broken by the changes

12.1. **All existing unit tests must pass** without modification
12.2. **All existing integration tests must pass** without modification
12.3. **All existing property-based tests must pass** without modification
12.4. Create new tests specifically for multi-stage scenarios
12.5. Test single-stage buckets to ensure backward compatibility
12.6. Test buckets without stage patterns (root-level) to ensure they still work

### 13. Multi-Stage Scenario Testing
**Requirement**: Validate the fix works correctly for multi-stage buckets

13.1. Test bucket with 2 stages (prod, beta) - events should go to correct distributions
13.2. Test bucket with 3+ stages to ensure scalability
13.3. Test mixed events (some prod, some beta) arriving in same batch
13.4. Test events arriving in different order (beta first, then prod)
13.5. Verify each stage's invalidation paths are correctly consolidated independently

### 14. Edge Case Testing
**Requirement**: Handle edge cases without breaking

14.1. Test events with missing `stageId` field
14.2. Test events with empty string `stageId`
14.3. Test bucket with distributions for some stages but not others
14.4. Test distribution validation when stage doesn't match any distribution
14.5. Test origin path matching with both `""` and `"/"` root paths

### 15. Integration Testing
**Requirement**: Verify end-to-end flow works correctly

15.1. Test complete flow: SQS → grouping → distribution search → validation → invalidation
15.2. Verify message deletion happens correctly for multi-stage groups
15.3. Verify window closing happens correctly after processing all stage groups
15.4. Test with real AWS CloudFront API responses (mocked in tests)
15.5. Verify logging includes stage information at all key points

## Implementation Constraints

### 16. Surgical Changes Only
**Requirement**: Minimize changes to reduce risk of introducing bugs

16.1. **Only modify these specific areas**:
   - `group_messages_by_bucket_and_origin()` function signature and grouping logic
   - Handler loop that processes groups (to handle 3-tuple instead of 2-tuple)
   - Distribution validation call (to use group's stage instead of first event's stage)
   - Related logging statements to include stage information

16.2. **Do NOT modify**:
   - Path consolidation algorithm (`path_consolidator.py`)
   - Distribution finder matching logic (`_matches_bucket_origin()` - it already works correctly)
   - Tag validation logic (already correct, just needs correct stage passed in)
   - Queue client operations
   - Invalidation client operations
   - Pattern resolver logic
   - Event filtering logic
   - Message deletion logic
   - Window tracking logic

16.3. **Preserve existing behavior**:
   - All existing function signatures must remain compatible (add optional parameters if needed)
   - All existing return types must remain the same
   - All existing error handling must remain unchanged
   - All existing logging patterns must be preserved (only add stage info)

### 17. Code Review Checklist
**Requirement**: Changes must pass strict review criteria

17.1. Diff must show minimal changes (< 50 lines modified)
17.2. No changes to consolidation algorithm
17.3. No changes to path extraction logic
17.4. No changes to invalidation submission logic
17.5. All changes must have clear comments explaining the stage grouping fix
17.6. All new code must follow existing code style and patterns

## Out of Scope

- Changes to the ingestor Lambda (event parsing)
- Changes to the distribution tagging requirements
- Changes to the consolidation algorithm
- Changes to the SQS queue structure
- Changes to the DynamoDB window tracking
- Refactoring of existing working code
- Performance optimizations beyond the fix
- Changes to error handling patterns
- Changes to retry logic
