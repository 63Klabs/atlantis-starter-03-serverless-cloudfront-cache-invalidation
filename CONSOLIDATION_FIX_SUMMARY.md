# Consolidation Fix Summary

## Problem

After the grouping refactor, two issues remained:

1. **Origin path being removed from paths** (e.g., `/beta/public/content/styles.css` → `/content/styles.css`)
2. **Multiple invalidations sent per distribution** (e.g., separate invalidations for `/content/*`, `/static/*`, etc.)

## Root Cause Analysis

### Issue 1: Origin Path Removal
**Status**: NOT A BUG - This is correct behavior!

CloudFront distributions with an origin path expect invalidation paths to be **relative to the origin**. For a distribution with:
- Origin: `mybucket.s3.amazonaws.com`
- Origin Path: `/beta/public`

The file `/beta/public/content/styles.css` in S3 is served as `https://d123.cloudfront.net/content/styles.css`, so the invalidation path should be `/content/styles.css`.

### Issue 2: Multiple Invalidations
**Status**: BUG - Duplicate stage grouping

The handler was grouping by stage, then `consolidate_paths()` was RE-GROUPING by stage:

```
Handler:
  Groups messages by stage → extracts relative paths → calls consolidate_paths()

consolidate_paths():
  Receives paths like ['/content/styles.css', '/static/app.js']
  Tries to extract stage from these paths (fails - no stage prefix!)
  Groups them as 'unknown' or by path pattern
  Returns multiple "stage" groups

Handler:
  Loops over returned "stages" → submits multiple invalidations
```

## The Fix

### Change 1: Don't Pass bucket_pattern to consolidate_paths

**Before**:
```python
consolidated_by_stage = consolidate_paths(
    object_paths,
    directory_threshold=bucket_config['directory_threshold'],
    stop_level=bucket_config['stop_level'],
    sibling_threshold=bucket_config['sibling_directory_threshold'],
    bucket_pattern=bucket_pattern  # ← Causes re-grouping!
)
```

**After**:
```python
consolidated_by_stage = consolidate_paths(
    object_paths,
    directory_threshold=bucket_config['directory_threshold'],
    stop_level=bucket_config['stop_level'],
    sibling_threshold=bucket_config['sibling_directory_threshold'],
    bucket_pattern=None  # ← Prevents re-grouping
)
```

### Change 2: Simplify Invalidation Loop

**Before**:
```python
# Loop over multiple "stages" returned by consolidate_paths
for consolidated_stage, consolidated_path_chunks in consolidated_by_stage.items():
    for dist_id in valid_distributions:
        for chunk_idx, path_chunk in enumerate(consolidated_path_chunks):
            # Submit invalidation
```

**After**:
```python
# Get the single 'default' stage group
consolidated_path_chunks = consolidated_by_stage.get('default', [[]])

for dist_id in valid_distributions:
    for chunk_idx, path_chunk in enumerate(consolidated_path_chunks):
        # Submit invalidation
```

## Result

### Before Fix
For a bucket with prod and beta stages, each with 10 files:
- **Prod stage**: 3-5 separate invalidations to prod distribution (grouped by path pattern)
- **Beta stage**: 3-5 separate invalidations to beta distribution (grouped by path pattern)
- **Total**: 6-10 invalidations

### After Fix
For the same bucket:
- **Prod stage**: 1 consolidated invalidation to prod distribution
- **Beta stage**: 1 consolidated invalidation to beta distribution
- **Total**: 2 invalidations (correct!)

## Code Changes

**File**: `application-infrastructure/functions/processor/handler.py`

**Lines Changed**: ~755-790

**Changes**:
1. Pass `bucket_pattern=None` to `consolidate_paths()`
2. Remove nested loop over consolidated stages
3. Extract `consolidated_path_chunks` directly from `consolidated_by_stage['default']`
4. Updated logging to reflect single consolidation per stage

## Testing

### Manual Testing
1. Upload files to both prod and beta stages
2. Verify only 2 invalidations are created (one per stage)
3. Verify paths are relative to origin (e.g., `/content/styles.css` not `/beta/public/content/styles.css`)
4. Verify consolidation still works (multiple files → `/*` wildcards)

### Expected Behavior
- **One bucket, two stages**: 2 invalidations total
- **Paths**: Relative to CloudFront origin path
- **Consolidation**: Multiple files in same directory → directory wildcard
- **Distribution matching**: Each stage finds only its own distribution

## Risk Assessment

**Risk Level**: Very Low

**Why**:
- Minimal code changes (one parameter, one loop structure)
- No changes to grouping, path extraction, or distribution matching logic
- Maintains all existing consolidation behavior
- Only affects how consolidate_paths is called and results are processed

**Rollback**: Simple - revert the two changes in handler.py
