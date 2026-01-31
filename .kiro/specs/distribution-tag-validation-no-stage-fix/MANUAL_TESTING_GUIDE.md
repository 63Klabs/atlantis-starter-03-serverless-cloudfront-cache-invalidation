# Manual Testing Guide: Distribution Tag Validation Fix

## Overview

This guide provides step-by-step instructions for manually testing the distribution tag validation fix for buckets without `{stageId}` in their pattern. The fix implements prefix matching for empty `stage_id` scenarios while maintaining exact matching for non-empty `stage_id` scenarios.

**Feature:** distribution-tag-validation-no-stage-fix  
**Validates:** All requirements (1.1-1.5, 2.1-2.4, 3.1-3.2, FR-1 through FR-5)

## Prerequisites

### Required AWS Resources

1. **S3 Buckets:**
   - Bucket WITHOUT `{stageId}` in pattern (e.g., `xcme-cdninval-a-{bucketId}`)
   - Bucket WITH `{stageId}` in pattern (e.g., `xcme-cdninval-a-{stageId}-{bucketId}`)
   - Both buckets must have `AllowInvalidationEvents=true` tag

2. **CloudFront Distributions:**
   - Distribution with prefix-matching tag (e.g., `ApplicationDeploymentId=xcme-cdninval-a-prod`)
   - Distribution with exact-matching tag (e.g., `ApplicationDeploymentId=xcme-cdninval-a`)
   - All distributions must have `AllowInvalidationEvents=true` tag

3. **Lambda Function:**
   - Deployed Processor Lambda function
   - Access to CloudWatch Logs for the function

4. **SQS Queue:**
   - Test SQS queue for sending events

### Required AWS Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketTagging",
        "cloudfront:ListTagsForResource",
        "lambda:InvokeFunction",
        "sqs:SendMessage",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "logs:FilterLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### Environment Setup

```bash
# Set environment variables for testing
export AWS_PROFILE=your-profile-name
export AWS_REGION=us-east-1

# Test resource identifiers
export TEST_BUCKET_NO_STAGE=xcme-cdninval-a-test1
export TEST_BUCKET_WITH_STAGE=xcme-cdninval-a-prod-test2
export TEST_DISTRIBUTION_PREFIX=E2G4RY69EPFNR7
export TEST_DISTRIBUTION_EXACT=E1234567890ABC
export PROCESSOR_FUNCTION_NAME=xcme-cdninval-a-prod-Processor
export TEST_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/test-queue
```

## Test Scenarios

### Scenario 1: Bucket Without StageId - Prefix Matching

**Objective:** Verify that distributions with `ApplicationDeploymentId` starting with the bucket's application tag are matched when `stage_id` is empty.

**Validates:** Requirements 1.1, 1.2, 1.3, 1.4

#### Step 1: Verify Bucket Tags

```bash
# Get bucket tags
aws s3api get-bucket-tagging \
  --bucket $TEST_BUCKET_NO_STAGE \
  --profile $AWS_PROFILE

# Expected output should include:
# - AllowInvalidationEvents: "true"
# - atlantis:Application: "xcme-cdninval-a" (or similar)
```

**Expected Result:**
```json
{
  "TagSet": [
    {
      "Key": "AllowInvalidationEvents",
      "Value": "true"
    },
    {
      "Key": "atlantis:Application",
      "Value": "xcme-cdninval-a"
    }
  ]
}
```

**Note the `atlantis:Application` value** - this is the `bucket_app_tag` used for validation.

#### Step 2: Verify Distribution Tags

```bash
# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)

# Get distribution tags
aws cloudfront list-tags-for-resource \
  --resource "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${TEST_DISTRIBUTION_PREFIX}" \
  --profile $AWS_PROFILE

# Expected output should include:
# - AllowInvalidationEvents: "true"
# - atlantis:ApplicationDeploymentId: "xcme-cdninval-a-prod" (starts with bucket app tag)
```

**Expected Result:**
```json
{
  "Tags": {
    "Items": [
      {
        "Key": "AllowInvalidationEvents",
        "Value": "true"
      },
      {
        "Key": "atlantis:ApplicationDeploymentId",
        "Value": "xcme-cdninval-a-prod"
      }
    ]
  }
}
```

**Verify:** `ApplicationDeploymentId` starts with the bucket's `atlantis:Application` value.

#### Step 3: Send Test Event

Create a test event file:

```bash
cat > test-event-no-stage.json <<EOF
{
  "bucketName": "$TEST_BUCKET_NO_STAGE",
  "objectKey": "/public/test-prefix-match-$(date +%s).html",
  "originPath": "/public",
  "stageId": "",
  "eventTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "eventType": "ObjectCreated:Put"
}
EOF
```

Send the event to SQS:

```bash
aws sqs send-message \
  --queue-url $TEST_QUEUE_URL \
  --message-body file://test-event-no-stage.json \
  --profile $AWS_PROFILE
```

**Expected Result:** Message ID returned, indicating successful send.

#### Step 4: Invoke Processor Lambda

```bash
# Invoke the Lambda function to process the event
aws lambda invoke \
  --function-name $PROCESSOR_FUNCTION_NAME \
  --invocation-type RequestResponse \
  --profile $AWS_PROFILE \
  response.json

# Check the response
cat response.json
```

**Expected Result:** Status code 200, no function errors.

#### Step 5: Review CloudWatch Logs

```bash
# Get the log group name
LOG_GROUP="/aws/lambda/$PROCESSOR_FUNCTION_NAME"

# Get recent log streams
aws logs describe-log-streams \
  --log-group-name $LOG_GROUP \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --profile $AWS_PROFILE

# Get the latest log stream name
LATEST_STREAM=$(aws logs describe-log-streams \
  --log-group-name $LOG_GROUP \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text \
  --profile $AWS_PROFILE)

# Get log events
aws logs get-log-events \
  --log-group-name $LOG_GROUP \
  --log-stream-name "$LATEST_STREAM" \
  --profile $AWS_PROFILE \
  | jq '.events[] | select(.message | contains("distribution") or contains("validation"))'
```

**Expected Log Entries:**

1. **Validation Input Log:**
```json
{
  "message": "Validating distribution tags for E2G4RY69EPFNR7",
  "extra_fields": {
    "distribution_id": "E2G4RY69EPFNR7",
    "bucket_app_tag": "xcme-cdninval-a",
    "stage_id": "",
    "expected_app_deployment_id": "xcme-cdninval-a",
    "match_type": "prefix"
  }
}
```

**Key Verification Points:**
- ✅ `stage_id` is empty string
- ✅ `expected_app_deployment_id` does NOT have trailing hyphen
- ✅ `match_type` is "prefix"

2. **Validation Comparison Log:**
```json
{
  "message": "Comparing distribution tags for E2G4RY69EPFNR7",
  "extra_fields": {
    "distribution_id": "E2G4RY69EPFNR7",
    "match_type": "prefix",
    "app_deployment_id": "xcme-cdninval-a-prod",
    "expected_app_deployment_id": "xcme-cdninval-a",
    "app_deployment_id_match": true
  }
}
```

**Key Verification Points:**
- ✅ `match_type` is "prefix"
- ✅ `app_deployment_id_match` is true
- ✅ Actual value "xcme-cdninval-a-prod" starts with expected "xcme-cdninval-a"

3. **Validation Success Log:**
```json
{
  "message": "Distribution tag validation passed for E2G4RY69EPFNR7 (prefix match)",
  "extra_fields": {
    "distribution_id": "E2G4RY69EPFNR7",
    "validation_result": true,
    "match_type": "prefix",
    "app_deployment_id": "xcme-cdninval-a-prod",
    "expected_app_deployment_id": "xcme-cdninval-a"
  }
}
```

**Key Verification Points:**
- ✅ Message includes "(prefix match)"
- ✅ `validation_result` is true
- ✅ `match_type` is "prefix"

#### Step 6: Verify Using CloudWatch Logs Insights

Use CloudWatch Logs Insights for more detailed analysis:

```
fields @timestamp, @message, extra_fields.match_type, extra_fields.expected_app_deployment_id, extra_fields.app_deployment_id, extra_fields.validation_result
| filter @message like /distribution tag validation/i
| filter extra_fields.stage_id = ""
| sort @timestamp desc
| limit 20
```

**Expected Results:**
- Entries show `match_type = "prefix"`
- Expected value has no trailing hyphen
- Validation passes for distributions with matching prefix

---

### Scenario 2: Bucket Without StageId - Exact Match Also Valid

**Objective:** Verify that exact match (no suffix) is also valid when using prefix matching.

**Validates:** Requirement 1.5

#### Step 1: Verify Distribution with Exact Match

```bash
# Get distribution tags for exact match distribution
aws cloudfront list-tags-for-resource \
  --resource "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${TEST_DISTRIBUTION_EXACT}" \
  --profile $AWS_PROFILE
```

**Expected Result:**
```json
{
  "Tags": {
    "Items": [
      {
        "Key": "AllowInvalidationEvents",
        "Value": "true"
      },
      {
        "Key": "atlantis:ApplicationDeploymentId",
        "Value": "xcme-cdninval-a"
      }
    ]
  }
}
```

**Verify:** `ApplicationDeploymentId` exactly equals the bucket's `atlantis:Application` value (no suffix).

#### Step 2: Send Test Event and Verify

Follow steps 3-6 from Scenario 1, but verify that:
- Validation still uses `match_type = "prefix"`
- Validation passes because exact match satisfies prefix match
- Logs show successful validation

---

### Scenario 3: Bucket Without StageId - No Match (Negative Test)

**Objective:** Verify that distributions with non-matching prefix are rejected.

**Validates:** Requirements 1.2, 1.3

#### Step 1: Identify Distribution with Different Prefix

Find or create a distribution with `ApplicationDeploymentId` that does NOT start with the bucket's application tag (e.g., `xcme-cdninval-b-prod` when bucket tag is `xcme-cdninval-a`).

#### Step 2: Send Test Event and Verify

Follow steps 3-6 from Scenario 1, but expect:

**Expected Log Entry (Validation Failure):**
```json
{
  "message": "Distribution tag validation failed for E9876543210XYZ: ApplicationDeploymentId mismatch (prefix match): expected=xcme-cdninval-a, actual=xcme-cdninval-b-prod",
  "extra_fields": {
    "distribution_id": "E9876543210XYZ",
    "validation_result": false,
    "match_type": "prefix",
    "app_deployment_id": "xcme-cdninval-b-prod",
    "expected_app_deployment_id": "xcme-cdninval-a"
  }
}
```

**Key Verification Points:**
- ✅ `validation_result` is false
- ✅ `match_type` is "prefix"
- ✅ Message indicates mismatch with "(prefix match)"
- ✅ Distribution is not selected for invalidation

---

### Scenario 4: Bucket With StageId - Exact Matching (Backward Compatibility)

**Objective:** Verify that buckets with `{stageId}` in pattern still use exact matching.

**Validates:** Requirements 2.1, 2.2, 2.3, 2.4, NFR-1

#### Step 1: Verify Bucket Pattern

```bash
# Get bucket tags
aws s3api get-bucket-tagging \
  --bucket $TEST_BUCKET_WITH_STAGE \
  --profile $AWS_PROFILE
```

**Expected:** Bucket should have a pattern like `xcme-cdninval-a-{stageId}-{bucketId}`.

#### Step 2: Send Test Event with Non-Empty StageId

Create test event:

```bash
cat > test-event-with-stage.json <<EOF
{
  "bucketName": "$TEST_BUCKET_WITH_STAGE",
  "objectKey": "/prod/public/test-exact-match-$(date +%s).html",
  "originPath": "/prod/public",
  "stageId": "prod",
  "eventTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "eventType": "ObjectCreated:Put"
}
EOF
```

Send the event:

```bash
aws sqs send-message \
  --queue-url $TEST_QUEUE_URL \
  --message-body file://test-event-with-stage.json \
  --profile $AWS_PROFILE
```

#### Step 3: Invoke Lambda and Review Logs

Follow steps 4-6 from Scenario 1.

**Expected Log Entries:**

1. **Validation Input Log:**
```json
{
  "message": "Validating distribution tags for E2G4RY69EPFNR7",
  "extra_fields": {
    "distribution_id": "E2G4RY69EPFNR7",
    "bucket_app_tag": "xcme-cdninval-a",
    "stage_id": "prod",
    "expected_app_deployment_id": "xcme-cdninval-a-prod",
    "match_type": "exact"
  }
}
```

**Key Verification Points:**
- ✅ `stage_id` is "prod" (non-empty)
- ✅ `expected_app_deployment_id` includes stage: "xcme-cdninval-a-prod"
- ✅ `match_type` is "exact"

2. **Validation Success Log:**
```json
{
  "message": "Distribution tag validation passed for E2G4RY69EPFNR7 (exact match)",
  "extra_fields": {
    "distribution_id": "E2G4RY69EPFNR7",
    "validation_result": true,
    "match_type": "exact",
    "app_deployment_id": "xcme-cdninval-a-prod",
    "expected_app_deployment_id": "xcme-cdninval-a-prod"
  }
}
```

**Key Verification Points:**
- ✅ Message includes "(exact match)"
- ✅ `match_type` is "exact"
- ✅ Actual and expected values are identical

---

### Scenario 5: Bucket With StageId - Wrong Stage (Negative Test)

**Objective:** Verify that distributions with different stage are rejected when using exact matching.

**Validates:** Requirement 2.4

#### Step 1: Send Event with Different Stage

Create test event with stage "dev":

```bash
cat > test-event-wrong-stage.json <<EOF
{
  "bucketName": "$TEST_BUCKET_WITH_STAGE",
  "objectKey": "/dev/public/test-wrong-stage-$(date +%s).html",
  "originPath": "/dev/public",
  "stageId": "dev",
  "eventTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "eventType": "ObjectCreated:Put"
}
EOF
```

Send the event and invoke Lambda.

**Expected Log Entry (Validation Failure):**
```json
{
  "message": "Distribution tag validation failed for E2G4RY69EPFNR7: ApplicationDeploymentId mismatch (exact match): expected=xcme-cdninval-a-dev, actual=xcme-cdninval-a-prod",
  "extra_fields": {
    "distribution_id": "E2G4RY69EPFNR7",
    "validation_result": false,
    "match_type": "exact",
    "app_deployment_id": "xcme-cdninval-a-prod",
    "expected_app_deployment_id": "xcme-cdninval-a-dev"
  }
}
```

**Key Verification Points:**
- ✅ `validation_result` is false
- ✅ `match_type` is "exact"
- ✅ Expected and actual values differ
- ✅ Distribution is not selected for invalidation

---

## CloudWatch Logs Insights Queries

### Query 1: View All Validation Events

```
fields @timestamp, extra_fields.distribution_id, extra_fields.match_type, extra_fields.expected_app_deployment_id, extra_fields.app_deployment_id, extra_fields.validation_result
| filter @message like /distribution tag validation/i
| sort @timestamp desc
| limit 50
```

### Query 2: Compare Prefix vs Exact Match Usage

```
fields extra_fields.match_type, extra_fields.stage_id
| filter @message like /validating distribution tags/i
| stats count() by extra_fields.match_type
```

**Expected Results:**
- Entries with empty `stage_id` use `match_type = "prefix"`
- Entries with non-empty `stage_id` use `match_type = "exact"`

### Query 3: Validation Success Rate by Match Type

```
fields extra_fields.match_type, extra_fields.validation_result
| filter @message like /distribution tag validation/i
| stats count() by extra_fields.match_type, extra_fields.validation_result
```

### Query 4: Find Prefix Match Validations

```
fields @timestamp, @message, extra_fields.distribution_id, extra_fields.expected_app_deployment_id, extra_fields.app_deployment_id
| filter extra_fields.match_type = "prefix"
| filter @message like /validation passed/i
| sort @timestamp desc
| limit 20
```

### Query 5: Find Exact Match Validations

```
fields @timestamp, @message, extra_fields.distribution_id, extra_fields.expected_app_deployment_id, extra_fields.app_deployment_id
| filter extra_fields.match_type = "exact"
| filter @message like /validation passed/i
| sort @timestamp desc
| limit 20
```

### Query 6: Find Validation Failures

```
fields @timestamp, @message, extra_fields.match_type, extra_fields.expected_app_deployment_id, extra_fields.app_deployment_id, extra_fields.reason
| filter @message like /validation failed/i
| sort @timestamp desc
| limit 20
```

---

## Verification Checklist

### Prefix Matching (Empty StageId)

- [ ] Bucket without `{stageId}` pattern identified
- [ ] Bucket has `AllowInvalidationEvents=true` tag
- [ ] Distribution with prefix-matching `ApplicationDeploymentId` identified
- [ ] Test event sent with empty `stage_id`
- [ ] Lambda execution successful
- [ ] Logs show `match_type = "prefix"`
- [ ] Logs show expected value without trailing hyphen
- [ ] Logs show validation passed
- [ ] Distribution with exact match also passes validation
- [ ] Distribution with non-matching prefix fails validation

### Exact Matching (Non-Empty StageId)

- [ ] Bucket with `{stageId}` pattern identified
- [ ] Test event sent with non-empty `stage_id` (e.g., "prod")
- [ ] Lambda execution successful
- [ ] Logs show `match_type = "exact"`
- [ ] Logs show expected value includes stage (e.g., "xcme-cdninval-a-prod")
- [ ] Logs show validation passed for matching stage
- [ ] Distribution with different stage fails validation

### Logging Enhancements

- [ ] All validation logs include `match_type` field
- [ ] Success logs indicate match type in message (e.g., "(prefix match)")
- [ ] Failure logs indicate match type in message
- [ ] Expected and actual values logged in all cases
- [ ] CloudWatch Logs Insights queries return expected results

### Backward Compatibility

- [ ] Existing stage-based validation continues to work
- [ ] No regression in exact match behavior
- [ ] No changes to `AllowInvalidationEvents` validation
- [ ] No changes to API signatures or return types

---

## Troubleshooting

### Issue: Logs Don't Show Match Type

**Symptom:** CloudWatch logs don't include `match_type` field.

**Possible Causes:**
1. Old version of code still deployed
2. Lambda function not updated with latest code

**Resolution:**
```bash
# Check Lambda function last modified time
aws lambda get-function \
  --function-name $PROCESSOR_FUNCTION_NAME \
  --query 'Configuration.LastModified' \
  --profile $AWS_PROFILE

# Redeploy if necessary
```

### Issue: Validation Fails for Valid Prefix

**Symptom:** Distribution with correct prefix fails validation.

**Possible Causes:**
1. `AllowInvalidationEvents` tag missing or incorrect
2. Case sensitivity mismatch
3. Whitespace in tag values

**Resolution:**
```bash
# Verify exact tag values (including case and whitespace)
aws cloudfront list-tags-for-resource \
  --resource "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DISTRIBUTION_ID}" \
  --profile $AWS_PROFILE \
  | jq '.Tags.Items[] | select(.Key == "atlantis:ApplicationDeploymentId")'

# Compare with bucket tag
aws s3api get-bucket-tagging \
  --bucket $BUCKET_NAME \
  --profile $AWS_PROFILE \
  | jq '.TagSet[] | select(.Key == "atlantis:Application")'
```

### Issue: Can't Find Log Events

**Symptom:** CloudWatch Logs queries return no results.

**Possible Causes:**
1. Lambda function not invoked
2. Wrong log group name
3. Time range too narrow

**Resolution:**
```bash
# List all log groups
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/" \
  --profile $AWS_PROFILE

# Check Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=$PROCESSOR_FUNCTION_NAME \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --profile $AWS_PROFILE
```

---

## Success Criteria

Manual testing is successful when:

1. ✅ **Prefix Matching Works:** Distributions with `ApplicationDeploymentId` starting with bucket app tag are validated when `stage_id` is empty
2. ✅ **Exact Match Works:** Distributions with exact `ApplicationDeploymentId` match are validated when `stage_id` is empty
3. ✅ **Exact Matching Preserved:** Distributions with exact stage match are validated when `stage_id` is non-empty
4. ✅ **Logging Enhanced:** All logs include `match_type` field and indicate match type in messages
5. ✅ **No Trailing Hyphen:** Expected value for empty `stage_id` does not have trailing hyphen
6. ✅ **Backward Compatible:** Existing stage-based validation continues to work without regression

---

## Additional Resources

- **Requirements:** `.kiro/specs/distribution-tag-validation-no-stage-fix/requirements.md`
- **Design:** `.kiro/specs/distribution-tag-validation-no-stage-fix/design.md`
- **Implementation:** `application-infrastructure/functions/processor/tag_validator.py`
- **Unit Tests:** `application-infrastructure/tests/unit/test_tag_validator.py`
- **Integration Tests:** `application-infrastructure/tests/integration/test_distribution_tag_validation_empty_stage.py`

---

## Notes

- Manual testing complements automated unit and integration tests
- Focus on verifying CloudWatch logs to ensure logging enhancements are working
- Test both positive (validation passes) and negative (validation fails) scenarios
- Verify backward compatibility with existing stage-based validation
- Document any unexpected behavior or edge cases discovered during testing
