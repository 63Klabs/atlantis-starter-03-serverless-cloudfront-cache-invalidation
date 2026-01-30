# Distribution Stage Matching Debugging Guide

## Problem Description

Invalidations are being sent, but they're going to only one distribution instead of two separate ones (prod and beta).

## Root Cause Analysis

The issue is likely one of the following:

1. **Distribution Lookup Issue**: `find_matching_distributions()` is finding both distributions, but they're not being properly separated by stage
2. **Tag Validation Issue**: The `validate_distribution_tags()` function is rejecting one of the distributions due to incorrect tags
3. **Stage Extraction Issue**: The `stage_id` being extracted from events is incorrect or empty

## Enhanced Logging Added

I've added detailed logging at key points in the process to help diagnose the issue:

### 1. Distribution Search (Step 4)
```
Step 4: Finding CloudFront distributions
- bucketName: <bucket>
- originPath: <original origin path from event>
- stageId: <extracted stage>
- resolvedOriginPath: <bucket pattern with stage substituted>
```

### 2. Distribution Tag Validation (Step 5)
```
Step 5: Starting distribution tag validation
- bucket_name: <bucket>
- bucket_app_tag: <atlantis:Application value>
- stage_id: <extracted stage>
- distribution_count: <number found>
- distribution_ids: [list of distribution IDs]
- expected_app_deployment_id: <bucket-app>-<stage>
```

For each distribution:
```
Validating distribution tags for <dist-id>
- distribution_id: <dist-id>
- bucket_app_tag: <app>
- stage_id: <stage>
- expected_app_deployment_id: <app>-<stage>

Retrieved tags for distribution <dist-id>
- tags: {all tags}
- tag_count: <count>

Comparing distribution tags for <dist-id>
- allow_invalidation_events: <value>
- app_deployment_id: <actual value>
- expected_app_deployment_id: <expected value>
- allow_invalidation_match: <true/false>
- app_deployment_id_match: <true/false>

Distribution <dist-id> validation result: <true/false>
```

## What to Look For in CloudWatch Logs

### Scenario 1: Both distributions found, but only one validated

**Look for:**
```
Step 4: Distribution search results
- distributionCount: 2
- distributionIds: [DIST1, DIST2]

Step 5: Starting distribution tag validation
- distribution_count: 2
- distribution_ids: [DIST1, DIST2]
- expected_app_deployment_id: myapp-prod  (or myapp-beta)
```

Then check each distribution's validation:
```
Comparing distribution tags for DIST1
- app_deployment_id: myapp-prod
- expected_app_deployment_id: myapp-prod
- app_deployment_id_match: true

Comparing distribution tags for DIST2
- app_deployment_id: myapp-beta
- expected_app_deployment_id: myapp-prod  <-- MISMATCH!
- app_deployment_id_match: false
```

**Problem**: Events for both stages are being grouped together with the same `stage_id`, so only distributions matching that stage pass validation.

**Solution**: Check the grouping logic - ensure events are properly separated by stage.

### Scenario 2: Only one distribution found

**Look for:**
```
Step 4: Distribution search results
- distributionCount: 1
- distributionIds: [DIST1]
- resolvedOriginPath: /prod/public  (or /beta/public)
```

**Problem**: The `find_matching_distributions()` function is only finding one distribution because:
- The `resolved_origin_path` is specific to one stage (e.g., `/prod/public`)
- Only distributions with that exact origin path are found

**This is actually CORRECT behavior!** Each stage should be processed separately:
- Prod events → grouped with stage_id="prod" → resolved_origin_path="/prod/public" → finds prod distribution
- Beta events → grouped with stage_id="beta" → resolved_origin_path="/beta/public" → finds beta distribution

### Scenario 3: Events not properly grouped by stage

**Look for:**
```
Step 2: Message grouping complete
- totalGroups: 1  <-- Should be 2 (one for prod, one for beta)
- groupDetails: [
    {
      bucketName: mybucket,
      originPath: /,
      stageId: prod,  <-- All events have same stage!
      messageCount: 10
    }
  ]
```

**Problem**: All events are being grouped with the same `stage_id`, so they're processed together.

**Solution**: Check the stage extraction logic in `group_messages_by_bucket_and_origin()`.

## Expected Correct Behavior

For a bucket with both prod and beta stages:

1. **Grouping** (Step 2):
   ```
   totalGroups: 2
   groupDetails: [
     { bucketName: mybucket, originPath: /, stageId: prod, messageCount: 5 },
     { bucketName: mybucket, originPath: /, stageId: beta, messageCount: 5 }
   ]
   ```

2. **Distribution Search** (Step 4) - First group (prod):
   ```
   resolvedOriginPath: /prod/public
   distributionCount: 1
   distributionIds: [PROD-DIST-ID]
   ```

3. **Distribution Search** (Step 4) - Second group (beta):
   ```
   resolvedOriginPath: /beta/public
   distributionCount: 1
   distributionIds: [BETA-DIST-ID]
   ```

4. **Tag Validation** (Step 5) - Prod group:
   ```
   expected_app_deployment_id: myapp-prod
   Distribution PROD-DIST-ID validation result: true
   ```

5. **Tag Validation** (Step 5) - Beta group:
   ```
   expected_app_deployment_id: myapp-beta
   Distribution BETA-DIST-ID validation result: true
   ```

## Next Steps

1. **Deploy the updated code** with enhanced logging
2. **Trigger invalidations** for both prod and beta stages
3. **Check CloudWatch Logs** for the processor Lambda
4. **Look for the log entries** described above
5. **Identify which scenario** matches your situation
6. **Report back** with the relevant log entries

## Key Questions to Answer

1. How many groups are created in Step 2? (Should be 2 for prod and beta)
2. What is the `stage_id` for each group?
3. What is the `resolved_origin_path` for each group?
4. How many distributions are found for each group?
5. What are the actual vs expected `app_deployment_id` values during validation?
