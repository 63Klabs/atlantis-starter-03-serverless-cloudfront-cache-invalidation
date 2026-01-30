# Path Issue Analysis

## Problem 1: Origin Path Being Removed

### Current Behavior
`/beta/public/content/styles.css` becomes `/content/styles.css`

### Root Cause
In `handler.py` around line 720, we're removing the `resolved_origin_path` from the object key:

```python
if resolved_origin_path and object_key.startswith(resolved_origin_path):
    relative_path = object_key[len(resolved_origin_path):]
    # Ensure path starts with /
    if not relative_path.startswith('/'):
        relative_path = '/' + relative_path
    object_paths.append(relative_path)
```

**Example**:
- `object_key` = `/beta/public/content/styles.css`
- `resolved_origin_path` = `/beta/public`
- Result: `/content/styles.css` (origin path removed!)

### Why This Is Wrong
CloudFront distributions with origin path `/beta/public` expect invalidation paths to be **relative to the origin**, but we're already processing events that are **stage-specific**. The object keys in S3 include the full path including the stage prefix.

For a CloudFront distribution with:
- Origin: `mybucket.s3.amazonaws.com`
- Origin Path: `/beta/public`

When a file at `/beta/public/content/styles.css` in S3 is accessed, CloudFront serves it as:
- URL: `https://d123.cloudfront.net/content/styles.css`

So the invalidation path should be `/content/styles.css` (relative to origin).

**BUT WAIT** - This is actually CORRECT behavior! The issue is elsewhere.

## Problem 2: Multiple Invalidations Per Distribution

### Current Behavior
Multiple invalidations are being sent to each distribution:
- One for `/content/*`
- One for `/static/*`
- etc.

### Root Cause
The `consolidate_paths()` function returns `Dict[str, List[List[str]]]` where:
- First key: stage name (e.g., 'prod', 'beta', 'unknown')
- Value: List of chunks (each chunk is a list of paths)

**The issue**: After we've already grouped by stage in the handler, we're passing stage-specific paths to `consolidate_paths()`, which then RE-GROUPS them by stage again!

### Code Flow

1. **Handler groups by stage** (line ~530):
```python
messages_by_stage: Dict[str, List[Dict[str, Any]]] = {}
for message in filtered_messages:
    stage_id = extract_stage_from_object_key(message, bucket_pattern)
    messages_by_stage[stage_id].append(message)
```

2. **Handler processes each stage** (line ~560):
```python
for stage_id, stage_messages in messages_by_stage.items():
    # ... extract paths from stage_messages
    # ... call consolidate_paths
```

3. **consolidate_paths RE-GROUPS by stage** (line ~1020 in path_consolidator.py):
```python
if bucket_pattern and '{stageId}' in bucket_pattern:
    for path in cleaned_paths:
        stage = extract_stage_from_path(path, bucket_pattern)
        stage_key = stage if stage else 'unknown'
        stage_groups[stage_key].append(path)
```

4. **Handler iterates over consolidated stages** (line ~780):
```python
for consolidated_stage, consolidated_path_chunks in consolidated_by_stage.items():
    # Submits invalidations
```

### The Problem
We're grouping by stage TWICE:
1. Once in the handler (correctly)
2. Again in consolidate_paths (unnecessarily)

When we pass paths like `/content/styles.css` (already relative to origin) to `consolidate_paths()` with `bucket_pattern='/{stageId}/public'`, it tries to extract stage from `/content/styles.css` but can't find it (no stage prefix!), so it groups everything as 'unknown' or 'default'.

Then the handler loops over the returned stages and submits multiple invalidations.

## Solution Plan

### Option 1: Don't Pass bucket_pattern to consolidate_paths (RECOMMENDED)
Since we've already grouped by stage in the handler and extracted relative paths, we should NOT pass `bucket_pattern` to `consolidate_paths()`. This will:
- Prevent re-grouping by stage
- Use the 'default' stage group
- Return a single consolidated list per stage

**Changes needed**:
```python
# In handler.py, around line 755
consolidated_by_stage = consolidate_paths(
    object_paths,
    directory_threshold=bucket_config['directory_threshold'],
    stop_level=bucket_config['stop_level'],
    sibling_threshold=bucket_config['sibling_directory_threshold'],
    bucket_pattern=None  # <-- Change this to None!
)
```

### Option 2: Pass Full Paths and Let consolidate_paths Handle Everything
Keep the full S3 paths (with stage prefix) and let `consolidate_paths()` do all the grouping and path manipulation.

**Changes needed**:
- Don't remove origin path in handler
- Pass full object keys to consolidate_paths
- Let consolidate_paths group by stage and return stage-specific paths

This is more complex and changes more code.

## Recommendation

**Use Option 1** because:
1. Minimal code changes (one line!)
2. Clear separation of concerns:
   - Handler: Groups by stage, extracts relative paths
   - consolidate_paths: Consolidates paths (no stage logic needed)
3. Maintains backward compatibility for buckets without stage patterns
4. The path extraction logic (removing origin path) is actually CORRECT

## Implementation

Change line ~755 in handler.py:
```python
# OLD:
consolidated_by_stage = consolidate_paths(
    object_paths,
    directory_threshold=bucket_config['directory_threshold'],
    stop_level=bucket_config['stop_level'],
    sibling_threshold=bucket_config['sibling_directory_threshold'],
    bucket_pattern=bucket_pattern  # <-- REMOVE THIS
)

# NEW:
consolidated_by_stage = consolidate_paths(
    object_paths,
    directory_threshold=bucket_config['directory_threshold'],
    stop_level=bucket_config['stop_level'],
    sibling_threshold=bucket_config['sibling_directory_threshold'],
    bucket_pattern=None  # <-- Pass None to prevent re-grouping
)
```

Then update the loop to expect only 'default' stage:
```python
# OLD:
for consolidated_stage, consolidated_path_chunks in consolidated_by_stage.items():
    # ...

# NEW:
# Since we're not passing bucket_pattern, consolidate_paths returns {'default': [[paths]]}
consolidated_path_chunks = consolidated_by_stage.get('default', [[]])
for chunk_idx, path_chunk in enumerate(consolidated_path_chunks):
    # ... submit invalidations
```

This ensures:
- One consolidation per stage (not multiple)
- Paths are relative to origin (correct for CloudFront)
- No duplicate stage grouping
