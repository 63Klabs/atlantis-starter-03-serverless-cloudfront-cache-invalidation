# CloudWatch Metrics and Logging Guide for Path Normalization

## Overview

The S3 path normalization feature uses structured logging to capture all normalization events in CloudWatch Logs. These logs can be queried and analyzed using CloudWatch Logs Insights to monitor path normalization behavior and troubleshoot issues.

## Structured Logging Fields

All path normalization related logs include an `operation` field in the `extra_fields` that identifies the type of operation:

- `path_normalization` - Path normalization events
- `pattern_matching` - Pattern matching events
- `event_filtering` - Event filtering events
- `bucket_pattern_resolution` - Bucket pattern resolution events
- `stage_filtering` - Stage filtering events

## CloudWatch Logs Insights Queries

### Query 1: Path Normalization Events

View all path normalization events showing original and normalized paths:

```
fields @timestamp, extra_fields.raw_key, extra_fields.normalized_key, extra_fields.normalization_applied
| filter extra_fields.operation = "path_normalization"
| sort @timestamp desc
| limit 100
```

### Query 2: Path Normalization Statistics

Count how many paths required normalization vs. were already normalized:

```
fields extra_fields.normalization_applied
| filter extra_fields.operation = "path_normalization"
| stats count() by extra_fields.normalization_applied
```

### Query 3: Pattern Matching Results

View pattern matching results with normalized paths:

```
fields @timestamp, extra_fields.normalized_path, extra_fields.bucket_pattern, extra_fields.filter_result
| filter extra_fields.operation = "pattern_matching"
| sort @timestamp desc
| limit 100
```

### Query 4: Event Filtering Summary

Count events by filter result (accepted vs. rejected):

```
fields extra_fields.filter_result, extra_fields.filter_reason
| filter extra_fields.operation = "event_filtering"
| stats count() by extra_fields.filter_result, extra_fields.filter_reason
```

### Query 5: Stage Filtering Analysis

Analyze which stages are being filtered:

```
fields @timestamp, extra_fields.event_path, extra_fields.stage, extra_fields.filter_result
| filter extra_fields.operation = "stage_filtering"
| stats count() by extra_fields.stage, extra_fields.filter_result
```

### Query 6: Bucket Pattern Resolution

View how bucket patterns are being resolved:

```
fields @timestamp, extra_fields.bucket_name, extra_fields.bucket_pattern, extra_fields.sample_event_path
| filter extra_fields.operation = "bucket_pattern_resolution"
| sort @timestamp desc
| limit 50
```

### Query 7: All Path Normalization Operations

View all operations related to path normalization in chronological order:

```
fields @timestamp, extra_fields.operation, @message
| filter extra_fields.operation in ["path_normalization", "pattern_matching", "event_filtering", "stage_filtering", "bucket_pattern_resolution"]
| sort @timestamp desc
| limit 200
```

## CloudWatch Dashboard Integration

The existing CloudWatch dashboard (template-dashboard.yml) already includes:

1. **Lambda Metrics**: Invocations, errors, duration, concurrent executions
2. **SQS Metrics**: Message counts, age of oldest message, DLQ messages
3. **Log Queries**: Error and warning logs, memory usage, duration distribution

### Adding Path Normalization Metrics to Dashboard

To add path normalization specific metrics to the dashboard, you can add a new log widget:

```yaml
{
  "type": "log",
  "x": 0,
  "y": <next_y_position>,
  "width": 24,
  "height": 6,
  "properties": {
    "query": "SOURCE '/aws/lambda/${IngestorFunction}' | fields @timestamp, extra_fields.raw_key, extra_fields.normalized_key, extra_fields.normalization_applied\n| filter extra_fields.operation = \"path_normalization\"\n| stats count() by extra_fields.normalization_applied",
    "region": "${AWS::Region}",
    "title": "Path Normalization Statistics",
    "view": "table"
  }
}
```

## Monitoring Best Practices

### 1. Regular Monitoring

- Check path normalization statistics daily to ensure paths are being normalized correctly
- Monitor filter reasons to identify any unexpected filtering behavior
- Review pattern matching results to verify bucket patterns are working as expected

### 2. Alerting

Consider creating CloudWatch alarms for:

- High rate of event filtering (may indicate misconfigured patterns)
- Errors in path normalization (should be rare)
- Unexpected stage filtering results

### 3. Troubleshooting

When investigating issues:

1. Start with Query 7 to see all path normalization operations
2. Use Query 1 to verify paths are being normalized correctly
3. Use Query 3 to check pattern matching behavior
4. Use Query 4 to understand why events are being filtered

## Standard AWS Lambda Metrics

The following standard AWS Lambda metrics are automatically captured and available in CloudWatch:

- **Invocations**: Number of times the function is invoked
- **Errors**: Number of invocations that result in errors
- **Duration**: Time the function takes to execute
- **Throttles**: Number of throttled invocations
- **ConcurrentExecutions**: Number of concurrent executions
- **DeadLetterErrors**: Number of times Lambda fails to send to DLQ

These metrics are already displayed in the CloudWatch dashboard and do not require any additional configuration.

## Requirement Validation

This logging and metrics approach satisfies:

- **Requirement 7.1**: Original and normalized paths are logged at debug level with structured fields
- **Requirement 7.2**: Pattern matching results with normalized paths are logged with structured fields
- **Requirement 7.3**: Filter reasons are included in structured logs with the `filter_reason` field
- **Requirement 7.4**: Path normalization statistics are captured in CloudWatch Logs and can be queried using Logs Insights

All logs use structured logging with the `extra_fields` dictionary, making them easily queryable and analyzable in CloudWatch Logs Insights.
