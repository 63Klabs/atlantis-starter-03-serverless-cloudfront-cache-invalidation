# Manual Verification Guide: S3 Path Normalization Fix

## Overview

This guide provides instructions for manually verifying that the S3 path normalization fix works correctly in a real AWS environment.

## Prerequisites

- AWS account with appropriate permissions
- S3 bucket configured for CloudFront invalidation
- CloudFront distribution configured with the S3 bucket as origin
- AWS CLI configured with appropriate profile
- Python 3.12+ with virtual environment

## Verification Steps

### Step 1: Upload Test Files

Use the updated upload utility to generate test files:

```bash
cd application-infrastructure
source .venv/bin/activate

# Upload test files to your S3 bucket
python build-scripts/upload-test-files.py \
  --buckets your-test-bucket-name \
  --stages prod \
  --profile your-aws-profile \
  --verbose
```

**Expected Behavior:**
- Files should be uploaded successfully
- S3 object keys should NOT have leading slashes
- Console output should show keys like: `prod/public/assets/file.html` (not `/prod/public/assets/file.html`)

### Step 2: Verify S3 Object Keys

Check the actual S3 object keys in your bucket:

```bash
aws s3 ls s3://your-test-bucket-name/prod/public/ --recursive --profile your-aws-profile
```

**Expected Output:**
```
2026-01-27 12:00:00    1234 prod/public/assets/test-ABC123.html
2026-01-27 12:00:00    1234 prod/public/content/test-XYZ789.html
...
```

**Verify:**
- ✅ Keys do NOT start with `/`
- ✅ Keys follow format: `stage/public/path/to/file.html`

### Step 3: Monitor S3 Event Notifications

If S3 event notifications are configured, check CloudWatch Logs for the ingestor Lambda:

```bash
aws logs tail /aws/lambda/your-ingestor-function-name \
  --follow \
  --profile your-aws-profile
```

**Expected Log Entries:**
```json
{
  "message": "Normalized S3 object key",
  "raw_key": "prod/public/assets/test-ABC123.html",
  "normalized_key": "/prod/public/assets/test-ABC123.html"
}
```

**Verify:**
- ✅ `raw_key` does NOT have leading slash (from S3 event)
- ✅ `normalized_key` DOES have leading slash (after normalization)

### Step 4: Verify Pattern Matching

Check processor Lambda logs to verify pattern matching works:

```bash
aws logs tail /aws/lambda/your-processor-function-name \
  --follow \
  --profile your-aws-profile
```

**Expected Log Entries:**
```json
{
  "message": "Matching normalized path against pattern",
  "normalized_path": "/prod/public/assets/test-ABC123.html",
  "bucket_pattern": "/{stageId}/public",
  "path_has_leading_slash": true
}
```

**Verify:**
- ✅ `normalized_path` has leading slash
- ✅ `path_has_leading_slash` is `true`
- ✅ Pattern matching succeeds (no "filtered out" messages)

### Step 5: Verify CloudFront Invalidations

Check that CloudFront invalidations are created with correct paths:

```bash
# List recent invalidations
aws cloudfront list-invalidations \
  --distribution-id your-distribution-id \
  --profile your-aws-profile
```

Then get details of the most recent invalidation:

```bash
aws cloudfront get-invalidation \
  --distribution-id your-distribution-id \
  --id INVALIDATION_ID \
  --profile your-aws-profile
```

**Expected Output:**
```json
{
  "Invalidation": {
    "InvalidationBatch": {
      "Paths": {
        "Items": [
          "/assets/*",
          "/content/*"
        ]
      }
    }
  }
}
```

**Verify:**
- ✅ Invalidation paths have leading slashes
- ✅ Paths match the expected pattern after consolidation
- ✅ CloudFront accepts the invalidation (status is not "Failed")

## Verification Checklist

Use this checklist to confirm all aspects of the fix:

- [ ] **Upload Utility**: Test files uploaded successfully
- [ ] **S3 Keys**: Object keys in S3 do NOT have leading slashes
- [ ] **Event Parsing**: Ingestor logs show normalization (raw → normalized)
- [ ] **Pattern Matching**: Processor logs show successful pattern matching with normalized paths
- [ ] **CloudFront Invalidations**: Invalidation paths have leading slashes
- [ ] **End-to-End**: Files uploaded → events triggered → invalidations created

## Troubleshooting

### Issue: Files not triggering events

**Check:**
1. S3 bucket has event notification configured
2. Event notification points to correct SQS queue
3. Lambda has permissions to read from queue

### Issue: Events filtered out

**Check:**
1. Bucket pattern matches the uploaded file paths
2. Stage ID in path matches configured stages
3. Check processor logs for "filtered out" messages with reasons

### Issue: CloudFront invalidations not created

**Check:**
1. Distribution ID is correct in configuration
2. Lambda has permissions to create invalidations
3. Check processor logs for invalidation submission errors

## Success Criteria

The fix is working correctly if:

1. ✅ S3 object keys are stored WITHOUT leading slashes (S3 standard)
2. ✅ Event parser normalizes keys by adding leading slashes
3. ✅ Pattern matching works with normalized paths
4. ✅ CloudFront invalidations are created with leading slashes
5. ✅ No events are incorrectly filtered out due to path format mismatch

## Notes

- The normalization happens transparently in the event parser
- S3 continues to use standard format (no leading slashes)
- Internal processing uses normalized format (with leading slashes)
- CloudFront receives correctly formatted invalidation paths
