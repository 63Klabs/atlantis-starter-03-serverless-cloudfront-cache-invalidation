# Grouping Refactor Summary

## Problem

The previous implementation was grouping messages by `(bucket, origin, stage)` before reading bucket tags. This meant:
1. Stage and origin path were being determined from event data (which may not be present when ingestor filtering is off)
2. Events were pre-grouped by stage before we knew the bucket's actual pattern
3. The processor couldn't independently determine stage and origin from bucket tags

## Solution

Refactored to group messages by **bucket only**, then determine stage and origin path from bucket tags:

### Key Changes

1. **Renamed function**: `group_messages_by_bucket_and_origin()` → `group_messages_by_bucket()`
   - Now returns `Dict[str, List[Dict]]` instead of `Dict[Tuple[str, str, str], List[Dict]]`
   - Groups only by bucket name
   - Much simpler logic - just extract bucket name and group

2. **Processing flow updated**:
   ```
   OLD FLOW:
   Messages → Group by (bucket, origin, stage) → Process each group
   
   NEW FLOW:
   Messages → Group by bucket → For each bucket:
     - Validate bucket tags
     - Resolve bucket pattern from tags
     - Filter events by pattern
     - Group filtered events by stage (extracted from object keys using pattern)
     - For each stage:
       - Resolve origin path (pattern + stage)
       - Find distributions
       - Validate distribution tags
       - Consolidate paths
       - Submit invalidations
   ```

3. **Stage extraction moved**:
   - OLD: Attempted to extract stage during initial grouping (unreliable)
   - NEW: Extract stage AFTER reading bucket pattern, using the pattern to parse object keys correctly

4. **Origin path resolution moved**:
   - OLD: Used `originPath` from event (may not be present)
   - NEW: Resolve from bucket's `OriginPathPattern` tag, then substitute `{stageId}` with actual stage

### Benefits

1. **Processor independence**: Processor now determines stage and origin independently, doesn't rely on ingestor
2. **Correct stage separation**: Events are grouped by stage AFTER we know the bucket pattern, ensuring accurate extraction
3. **Handles all patterns**: Works correctly whether pattern is `/`, `/{stageId}/public`, or any other format
4. **Proper distribution matching**: Each stage finds only its own distributions because:
   - Stage is correctly extracted from object keys using bucket pattern
   - Origin path is correctly resolved (pattern + stage substitution)
   - Distribution lookup uses the resolved origin path
   - Tag validation ensures distribution matches the stage

### Example Flow

For a bucket with pattern `/{stageId}/public` and events for both prod and beta:

```
1. Group messages by bucket:
   - mybucket: [10 messages]

2. Process mybucket:
   - Read tags → pattern = "/{stageId}/public"
   - Filter events by pattern
   - Group by stage:
     - prod: [5 messages with /prod/public/...]
     - beta: [5 messages with /beta/public/...]

3. Process prod stage:
   - Resolve origin: /{stageId}/public + prod → /prod/public
   - Find distributions with origin /prod/public → [PROD-DIST]
   - Validate PROD-DIST tags (expects myapp-prod) → PASS
   - Consolidate prod paths
   - Submit to PROD-DIST

4. Process beta stage:
   - Resolve origin: /{stageId}/public + beta → /beta/public
   - Find distributions with origin /beta/public → [BETA-DIST]
   - Validate BETA-DIST tags (expects myapp-beta) → PASS
   - Consolidate beta paths
   - Submit to BETA-DIST
```

## Code Structure

### New Function Signature

```python
def group_messages_by_bucket(messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group SQS messages by bucketName only.
    
    Returns:
        Dictionary where:
            - Keys are bucket names (strings)
            - Values are lists of messages belonging to that bucket
    """
```

### Processing Loop Structure

```python
for bucket_name, messages in grouped_messages.items():
    # Validate bucket
    # Get bucket tags and pattern
    # Filter events by pattern
    
    # Group by stage
    messages_by_stage = {}
    for message in filtered_messages:
        stage_id = extract_stage_from_object_key(message, bucket_pattern)
        messages_by_stage[stage_id].append(message)
    
    # Process each stage
    for stage_id, stage_messages in messages_by_stage.items():
        resolved_origin_path = resolve_origin_path(bucket_pattern, stage_id)
        distributions = find_matching_distributions(bucket_name, resolved_origin_path)
        valid_distributions = validate_tags(distributions, bucket_app_tag, stage_id)
        # ... consolidate and invalidate
```

## Testing Note

Tests will need to be updated to reflect:
1. New function name: `group_messages_by_bucket`
2. New return type: `Dict[str, List]` instead of `Dict[Tuple[str, str, str], List]`
3. New processing flow with nested stage loop

## Migration Impact

- **Breaking change**: Function signature changed
- **Behavior change**: Stage extraction and grouping happens at different point in flow
- **Result**: Should now correctly separate prod and beta stages and send to separate distributions
