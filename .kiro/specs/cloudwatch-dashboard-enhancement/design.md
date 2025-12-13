# Design Document

## Overview

This design enhances the existing CloudWatch Dashboard by adding comprehensive monitoring for the Ingestor Lambda function and SQS queue metrics. The enhancement reorganizes the dashboard layout to provide a logical flow from event ingestion through processing, with clear section headers and optimal widget positioning.

## Architecture

The enhanced dashboard follows a top-down monitoring approach:

1. **Alarms Section** - Critical alerts at the top for immediate visibility
2. **Ingestor Function Section** - Event ingestion monitoring 
3. **SQS Queues Section** - Message queue health and performance
4. **Processor Function Section** - Event processing monitoring
5. **Logs and Analysis Section** - Detailed logs and performance analysis

The dashboard maintains the existing 24-column grid layout with consistent widget sizing patterns.

## Components and Interfaces

### Widget Layout Grid System
- **Grid Width**: 24 columns
- **Standard Widget Widths**: 6 columns (quarter-width), 12 columns (half-width), 24 columns (full-width)
- **Widget Heights**: Variable based on content type (2-7 units typical for metrics)

### Section Headers
- **Type**: Text widgets with markdown formatting
- **Width**: 24 columns (full-width)
- **Height**: 2 units
- **Styling**: Consistent H2 markdown headers

### Metric Widgets
- **Lambda Metrics**: Invocations, Duration, Errors, Concurrent Executions
- **SQS Metrics**: Message counts, Age of oldest message, Send/Receive rates
- **Display Types**: Time series charts and single-value summaries

## Data Models

### Lambda Function Metrics
```yaml
MetricNamespace: AWS/Lambda
Dimensions:
  - FunctionName: ${IngestorFunction} | ${ProcessorFunction}
MetricNames:
  - Invocations
  - Duration  
  - Errors
  - ConcurrentExecutions
```

### SQS Queue Metrics  
```yaml
MetricNamespace: AWS/SQS
Dimensions:
  - QueueName: ${EventQueue} | ${EventQueueDLQ}
MetricNames:
  - ApproximateNumberOfMessages
  - ApproximateNumberOfMessagesVisible
  - ApproximateAgeOfOldestMessage
  - NumberOfMessagesSent
  - NumberOfMessagesReceived
```

### Widget Positioning Schema
```yaml
Widget:
  x: 0-23 (column position)
  y: 0-n (row position) 
  width: 1-24 (column span)
  height: 1-n (row span)
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: Ingestor metrics presence
*For any* dashboard configuration, all required Ingestor Lambda metrics (Invocations, Duration, Errors, ConcurrentExecutions) should be present as widgets with correct function name references
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

Property 2: SQS metrics completeness  
*For any* dashboard configuration, all required SQS metrics (message counts, age metrics, send/receive rates) should be present for both Event_Queue and Event_Queue_DLQ
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 3: Widget non-overlap constraint
*For any* two widgets in the dashboard, their coordinate rectangles (x, y, width, height) should not intersect or overlap
**Validates: Requirements 3.1**

Property 4: Section header presence and positioning
*For any* dashboard configuration, text header widgets should exist for each section (Ingestor, SQS, Processor) and be positioned above their corresponding metric widgets
**Validates: Requirements 3.2, 4.1, 4.2, 4.3, 4.5**

Property 5: Alarms widget top positioning
*For any* dashboard configuration, the alarms widget should have the smallest y-coordinate among all actionable widgets and span full width (24 columns)
**Validates: Requirements 3.3, 5.1, 5.3, 5.5**

Property 6: Widget width consistency
*For any* dashboard widget, the width should follow standard patterns (6, 12, or 24 columns) consistent with the existing design
**Validates: Requirements 3.4**

Property 7: Existing widget preservation
*For any* dashboard modification, all original Processor function widgets and log queries should remain unchanged in their properties and functionality
**Validates: Requirements 3.5**

Property 8: Text header formatting consistency
*For any* text header widgets in the dashboard, they should have consistent height (2 units), width (24 columns), and markdown formatting structure
**Validates: Requirements 4.4**

Property 9: Alarm references completeness
*For any* alarms widget, it should contain all existing alarm ARN references for both Ingestor and Processor functions
**Validates: Requirements 5.2**

Property 10: Coordinate adjustment for alarms positioning
*For any* non-title widgets, their y-coordinates should be adjusted to accommodate the top-positioned alarms widget without creating overlaps
**Validates: Requirements 5.4**

## Error Handling

### Invalid Widget Positioning
- Validate widget coordinates to prevent overlaps
- Ensure widgets fit within the 24-column grid system
- Handle edge cases where widgets exceed dashboard boundaries

### Missing Resource References
- Validate that all Lambda function and SQS queue references exist
- Handle cases where CloudFormation parameters are not properly substituted
- Provide fallback behavior for missing alarm references

### Malformed Dashboard JSON
- Validate JSON structure before deployment
- Ensure all required widget properties are present
- Handle CloudFormation template syntax errors gracefully

## Testing Strategy

### Unit Testing Approach
The testing strategy will focus on validating the dashboard configuration structure and widget properties:

- **Dashboard JSON Validation**: Parse and validate the generated dashboard JSON structure
- **Widget Property Testing**: Verify individual widget configurations match requirements
- **Coordinate System Testing**: Validate widget positioning and overlap detection
- **Resource Reference Testing**: Ensure all CloudFormation parameter references are correct

### Property-Based Testing Approach
Property-based testing will use **Hypothesis** (Python) to generate random dashboard configurations and validate correctness properties:

- **Widget Generation**: Generate random widget configurations within valid bounds
- **Layout Validation**: Test overlap detection across many widget combinations  
- **Metric Validation**: Verify metric configurations across different AWS resource names
- **Coordinate Testing**: Test positioning logic with various grid layouts

Each property-based test will run a minimum of 100 iterations to ensure comprehensive coverage. Property-based tests will be tagged with comments referencing the specific correctness property from this design document using the format: '**Feature: cloudwatch-dashboard-enhancement, Property {number}: {property_text}**'

The dual testing approach ensures both specific examples work correctly (unit tests) and general correctness holds across all valid inputs (property tests), providing comprehensive validation of the dashboard enhancement.