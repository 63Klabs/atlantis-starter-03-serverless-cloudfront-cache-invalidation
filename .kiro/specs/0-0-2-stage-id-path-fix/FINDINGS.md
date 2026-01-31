# Stage ID Extraction Bug - Findings

## Issue Summary

The processor function incorrectly extracts the stageId from S3 object paths when the OriginPathPattern places {stageId} in a position other than the first path segment.

## Problem Description

**Current Behavior:**
When given a pattern like `/app/web/{stageId}/web` and a path like `/app/web/prod/public/fr3nqxNH/level-1-PKfdYBkt`, the processor extracts `app` as the stageId instead of `prod`.

**Root Cause:**
In `handler.py` (lines 502-512), the stage extraction logic always takes the first path segment:

```python
# Extract stage from object key using the bucket pattern
stage_id = ''
if '{stageId}' in bucket_pattern:
    # Extract stage from object key
    # Pattern: /{stageId}/public -> extract first path segment
    parts = [p for p in object_key.split('/') if p]
    if len(parts) >= 1:
        # First non-empty segment is the stage
        stage_id = parts[0]
```

**The Problem:**
The code comment says "Pattern: /{stageId}/public -> extract first path segment", which only works when {stageId} is in the first position. It doesn't use the actual bucket_pattern to determine where {stageId} is located.

## Correct Solution

The codebase already has a utility function `extract_stage_from_path()` in `path_utils.py` that correctly extracts the stage based on the pattern:

```python
def extract_stage_from_path(event_path: str, pattern: str) -> str:
    """
    Extract stage identifier from event path using pattern.
    
    Examples:
        >>> extract_stage_from_path('/prod/public/file.html', '/{stageId}/public')
        'prod'
        >>> extract_stage_from_path('/app/web/prod/public/file.html', '/app/web/{stageId}/public')
        'prod'
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

This function:
1. Finds the position of `{stageId}` in the pattern
2. Extracts the corresponding segment from the event path
3. Works regardless of where {stageId} appears in the pattern

## Impact

This bug causes:
1. **Incorrect stage identification** - Wrong stage is extracted from paths
2. **Distribution matching failures** - Distributions are looked up with wrong origin paths
3. **Tag validation failures** - Distribution tags are validated against wrong stage
4. **Invalidation failures** - CloudFront invalidations may target wrong distributions or fail entirely

## Example Scenarios

### Scenario 1: Pattern with {stageId} in 3rd position
- **Pattern:** `/app/web/{stageId}/web`
- **Path:** `/app/web/prod/public/file.html`
- **Current (Wrong):** stageId = `app`
- **Expected (Correct):** stageId = `prod`

### Scenario 2: Pattern with {stageId} in 1st position (works correctly)
- **Pattern:** `/{stageId}/public`
- **Path:** `/prod/public/file.html`
- **Current (Correct):** stageId = `prod`
- **Expected (Correct):** stageId = `prod`

### Scenario 3: Pattern with {stageId} in 2nd position
- **Pattern:** `/static/{stageId}/assets`
- **Path:** `/static/staging/assets/file.js`
- **Current (Wrong):** stageId = `static`
- **Expected (Correct):** stageId = `staging`

## Files Affected

### Primary File
- `application-infrastructure/functions/processor/handler.py` (lines 502-512)

### Related Files (for reference)
- `application-infrastructure/layers/common/python/common/path_utils.py` - Contains correct implementation
- `application-infrastructure/functions/processor/pattern_resolver.py` - Uses path_utils correctly

## Recommended Fix

Replace the hardcoded "first segment" extraction logic with a call to the existing `extract_stage_from_path()` utility function:

```python
# Import at top of file
from common.path_utils import extract_stage_from_path  # pyright: ignore[reportMissingImports]

# Replace lines 502-512 with:
for message in filtered_messages:
    parsed_body = message.get('parsed_body', {})
    object_key = parsed_body.get('objectKey', '')
    
    # Extract stage from object key using the bucket pattern
    stage_id = extract_stage_from_path(object_key, bucket_pattern)
    
    # Group by stage
    if stage_id not in messages_by_stage:
        messages_by_stage[stage_id] = []
    messages_by_stage[stage_id].append(message)
```

## Testing Requirements

1. **Unit Tests:**
   - Test stage extraction with {stageId} in various positions (1st, 2nd, 3rd, etc.)
   - Test with patterns without {stageId}
   - Test with malformed paths

2. **Integration Tests:**
   - Test end-to-end flow with multi-segment patterns
   - Verify distribution matching works correctly
   - Verify tag validation uses correct stage

3. **Property-Based Tests (Optional):**
   - Generate random patterns with {stageId} in different positions
   - Verify stage extraction is always correct

## Priority

**HIGH** - This is a critical bug that breaks the core functionality when using non-standard origin path patterns.
