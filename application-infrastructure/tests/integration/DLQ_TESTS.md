# Dead Letter Queue (DLQ) Integration Tests

## Overview

This document describes the integration tests for the Dead Letter Queue (DLQ) functionality in the Multi-Bucket CloudFront Invalidation Service.

## What is Tested

The DLQ integration tests verify the following requirements:

### Requirement 3.3: DLQ Message Movement

**Requirement**: WHEN a message fails processing in the Event Queue THEN the Invalidation Service SHALL move the message to the Dead Letter Queue after the maximum receive count is exceeded.

The tests verify:
1. Messages that fail processing are automatically moved to the DLQ after 3 receive attempts
2. Malformed messages (invalid JSON structure) are moved to DLQ
3. Messages with missing required fields are moved to DLQ
4. Messages are removed from the main queue after moving to DLQ

### DLQ Alarm Monitoring

The tests also verify:
1. CloudWatch alarm triggers when messages appear in DLQ
2. CloudWatch metrics accurately reflect DLQ message count
3. DLQ is configured with correct retention period (14 days)
4. Main queue has correct redrive policy configuration

## Test Structure

### Test Classes

1. **TestDLQMessageMovement**
   - `test_malformed_message_moves_to_dlq`: Verifies malformed messages move to DLQ
   - `test_message_with_missing_fields_moves_to_dlq`: Verifies incomplete messages move to DLQ

2. **TestDLQAlarm**
   - `test_dlq_alarm_triggers_on_message`: Verifies CloudWatch alarm triggers
   - `test_dlq_metric_reflects_message_count`: Verifies metrics are accurate

3. **TestDLQEdgeCases**
   - `test_dlq_retains_messages_for_configured_period`: Verifies 14-day retention
   - `test_main_queue_has_dlq_configured`: Verifies redrive policy configuration

## Running the Tests

### Prerequisites

1. **Deployed CloudFormation Stack**: The application must be deployed to AWS
2. **AWS Credentials**: Configured with appropriate permissions
3. **Python Dependencies**: Install with `pip install -r requirements.txt`

### Quick Start

Use the provided shell script:

```bash
cd application-infrastructure/tests/integration
./run_dlq_tests.sh
```

The script will:
1. Prompt for CloudFormation stack name
2. Fetch Lambda function names and queue URLs from stack outputs
3. Automatically discover the DLQ URL from the main queue's redrive policy
4. Attempt to find the DLQ CloudWatch alarm
5. Set environment variables
6. Run the DLQ integration tests

### Manual Setup

If you prefer to set up manually:

```bash
# Set required environment variables
export RUN_INTEGRATION_TESTS=1
export PROCESSOR_FUNCTION_NAME="acme-project-prod-Processor"
export TEST_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/acme-project-prod-EventQueue"
export TEST_DLQ_URL="https://sqs.us-east-1.amazonaws.com/123456789012/acme-project-prod-EventQueueDLQ"
export DLQ_ALARM_NAME="acme-project-prod-DLQMessageAlarm"  # Optional

# Run tests
cd application-infrastructure
pytest tests/integration/test_dlq.py -v
```

### Running Specific Test Classes

```bash
# Test only message movement
pytest tests/integration/test_dlq.py::TestDLQMessageMovement -v

# Test only alarm functionality
pytest tests/integration/test_dlq.py::TestDLQAlarm -v

# Test only edge cases
pytest tests/integration/test_dlq.py::TestDLQEdgeCases -v
```

### Running Individual Tests

```bash
# Test malformed message handling
pytest tests/integration/test_dlq.py::TestDLQMessageMovement::test_malformed_message_moves_to_dlq -v

# Test alarm triggering
pytest tests/integration/test_dlq.py::TestDLQAlarm::test_dlq_alarm_triggers_on_message -v
```

## How the Tests Work

### Message Movement Tests

1. **Send Test Message**: A malformed or incomplete message is sent to the main queue
2. **Trigger Processing**: The Processor Lambda is invoked multiple times (4 times to exceed maxReceiveCount of 3)
3. **Wait for DLQ**: After exceeding max receives, SQS automatically moves the message to DLQ
4. **Verify**: The test confirms the message appears in DLQ and is removed from main queue
5. **Cleanup**: Test messages are deleted from DLQ

### Alarm Tests

1. **Send to DLQ**: A test message is sent directly to the DLQ
2. **Wait for Metrics**: CloudWatch metrics take time to update (up to 5 minutes)
3. **Check Alarm State**: The alarm state is checked (may still be OK due to timing)
4. **Verify Message**: The test confirms the message is actually in DLQ
5. **Cleanup**: Test message is deleted

### Configuration Tests

1. **Query Attributes**: SQS queue attributes are queried
2. **Verify Settings**: Retention period, redrive policy, and maxReceiveCount are verified
3. **No Cleanup Needed**: These tests only read configuration

## Understanding Test Results

### Successful Test Output

```
test_dlq.py::TestDLQMessageMovement::test_malformed_message_moves_to_dlq PASSED
test_dlq.py::TestDLQMessageMovement::test_message_with_missing_fields_moves_to_dlq PASSED
test_dlq.py::TestDLQAlarm::test_dlq_alarm_triggers_on_message PASSED
test_dlq.py::TestDLQAlarm::test_dlq_metric_reflects_message_count PASSED
test_dlq.py::TestDLQEdgeCases::test_dlq_retains_messages_for_configured_period PASSED
test_dlq.py::TestDLQEdgeCases::test_main_queue_has_dlq_configured PASSED
```

### Common Issues

#### 1. Messages Not Moving to DLQ

**Symptom**: Test fails with "Expected message in DLQ"

**Possible Causes**:
- Processor Lambda is successfully processing the messages (not failing)
- maxReceiveCount is higher than expected
- Visibility timeout is too long

**Solution**:
- Verify the message is truly malformed
- Check CloudWatch Logs for Processor Lambda errors
- Verify queue redrive policy configuration

#### 2. Alarm Not Triggering

**Symptom**: Alarm remains in OK state

**Possible Causes**:
- CloudWatch metrics take time to update (up to 5 minutes)
- Alarm evaluation period hasn't completed
- Alarm threshold is configured differently

**Solution**:
- Wait longer for metrics to propagate
- Check alarm configuration in CloudWatch console
- Verify message is actually in DLQ (more important than alarm state)

#### 3. Queue Purge Errors

**Symptom**: "PurgeQueueInProgress" error

**Possible Causes**:
- Queue was recently purged (60 second cooldown)
- Multiple tests running concurrently

**Solution**:
- Wait 60 seconds between test runs
- The test fixture handles this by falling back to manual deletion

## Test Timing Considerations

### Message Movement Tests
- **Duration**: 30-60 seconds per test
- **Why**: Multiple Lambda invocations with delays between attempts

### Alarm Tests
- **Duration**: 60-120 seconds per test
- **Why**: CloudWatch metrics can take up to 5 minutes to update

### Configuration Tests
- **Duration**: 1-2 seconds per test
- **Why**: Simple attribute queries

## Cost Considerations

DLQ integration tests interact with real AWS services and incur minimal costs:

| Service | Cost Factor | Estimated Cost |
|---------|-------------|----------------|
| Lambda Invocations | 4-5 invocations per test | < $0.001 |
| SQS Messages | ~10 messages per test run | < $0.001 |
| CloudWatch Metrics | Metric queries | Free tier |
| CloudWatch Alarms | Alarm evaluations | Free tier |

**Estimated cost per test run**: < $0.01

## Troubleshooting

### Check CloudWatch Logs

View Processor Lambda logs to see why messages are failing:

```bash
aws logs tail /aws/lambda/your-prefix-project-stage-Processor --follow
```

### Check Queue Attributes

Verify queue configuration:

```bash
# Main queue
aws sqs get-queue-attributes \
  --queue-url $TEST_QUEUE_URL \
  --attribute-names All

# DLQ
aws sqs get-queue-attributes \
  --queue-url $TEST_DLQ_URL \
  --attribute-names All
```

### Check Alarm State

View alarm details:

```bash
aws cloudwatch describe-alarms \
  --alarm-names $DLQ_ALARM_NAME
```

### Manually Purge Queues

If tests leave messages behind:

```bash
# Purge main queue
aws sqs purge-queue --queue-url $TEST_QUEUE_URL

# Purge DLQ
aws sqs purge-queue --queue-url $TEST_DLQ_URL
```

## Best Practices

1. **Run Tests Sequentially**: Don't run multiple DLQ tests concurrently
2. **Clean Up**: Tests clean up after themselves, but verify queues are empty
3. **Monitor Costs**: DLQ tests are cheap, but monitor if running frequently
4. **Check Logs**: Always check CloudWatch Logs if tests fail
5. **Wait for Metrics**: Alarm tests may take time due to metric propagation

## Integration with CI/CD

Include DLQ tests in your deployment pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run DLQ Integration Tests
  env:
    RUN_INTEGRATION_TESTS: 1
    PROCESSOR_FUNCTION_NAME: ${{ secrets.PROCESSOR_FUNCTION_NAME }}
    TEST_QUEUE_URL: ${{ secrets.TEST_QUEUE_URL }}
    TEST_DLQ_URL: ${{ secrets.TEST_DLQ_URL }}
    DLQ_ALARM_NAME: ${{ secrets.DLQ_ALARM_NAME }}
  run: |
    pytest tests/integration/test_dlq.py -v
```

## Additional Resources

- [AWS SQS Dead Letter Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [CloudWatch Alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
- [pytest Documentation](https://docs.pytest.org/)

## Support

For issues or questions:
1. Check CloudWatch Logs for detailed error messages
2. Verify queue configuration (redrive policy, maxReceiveCount)
3. Check alarm configuration in CloudWatch console
4. Review test output for specific error messages
