# Implementation Plan

- [ ] 1. Analyze current dashboard structure and create layout plan
  - Parse existing dashboard JSON to understand current widget positioning
  - Calculate new widget coordinates to accommodate alarms at top and new sections
  - Create coordinate mapping for all new and existing widgets
  - _Requirements: 3.1, 3.3, 5.1, 5.4_

- [x] 1.1 Write property test for widget non-overlap validation
  - **Property 3: Widget non-overlap constraint**
  - **Validates: Requirements 3.1**

- [x] 2. Implement alarms widget repositioning
  - Move alarms widget to top position (after title)
  - Update alarms widget coordinates and ensure full width
  - Adjust all other widget y-coordinates to accommodate alarms position
  - _Requirements: 3.3, 5.1, 5.3, 5.4, 5.5_

- [x] 2.1 Write property test for alarms widget positioning
  - **Property 5: Alarms widget top positioning**
  - **Validates: Requirements 3.3, 5.1, 5.3, 5.5**

- [x] 3. Add Ingestor function section with header
  - Create "Lambda Functions - Ingestor" text header widget
  - Position header widget above Ingestor metrics section
  - Ensure consistent formatting with other section headers
  - _Requirements: 4.1, 4.4, 4.5_

- [x] 4. Implement Ingestor function metrics widgets
- [x] 4.1 Create Ingestor invocations and errors widget
  - Add time series widget for Ingestor invocations and errors metrics
  - Configure proper metric references using ${IngestorFunction} parameter
  - Set appropriate colors and display properties
  - _Requirements: 1.1, 1.4_

- [x] 4.2 Create Ingestor duration metrics widget
  - Add time series widget showing average, minimum, and maximum duration
  - Configure multiple statistics for comprehensive duration monitoring
  - Position widget in Ingestor section with proper coordinates
  - _Requirements: 1.2_

- [x] 4.3 Create Ingestor concurrent executions widget
  - Add time series widget for concurrent executions metric
  - Configure appropriate time period and statistics
  - Position widget in Ingestor section layout
  - _Requirements: 1.3_

- [x] 4.4 Create Ingestor invocation summary widget
  - Add single-value widget for Ingestor invocation summaries
  - Configure singleValue view type with appropriate time range
  - Position widget to complement time series metrics
  - _Requirements: 1.5_

- [x] 4.5 Write property test for Ingestor metrics presence
  - **Property 1: Ingestor metrics presence**
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

- [x] 5. Add SQS queues section with header
  - Create "SQS Queues" text header widget
  - Position header widget above SQS metrics section
  - Ensure consistent formatting and positioning
  - _Requirements: 4.2, 4.4, 4.5_

- [x] 6. Implement SQS metrics widgets
- [x] 6.1 Create Event Queue message count widgets
  - Add widgets for ApproximateNumberOfMessages and ApproximateNumberOfMessagesVisible
  - Configure proper queue name references using ${EventQueue} parameter
  - Set appropriate time series display properties
  - _Requirements: 2.1_

- [x] 6.2 Create Event Queue age metrics widget
  - Add widget for ApproximateAgeOfOldestMessage metric
  - Configure appropriate time period and alert thresholds
  - Position widget in SQS section layout
  - _Requirements: 2.2_

- [x] 6.3 Create Dead Letter Queue monitoring widget
  - Add widget for DLQ message count metrics
  - Configure proper queue name references using ${EventQueueDLQ} parameter
  - Set appropriate alerting colors and thresholds
  - _Requirements: 2.3_

- [x] 6.4 Create SQS send and receive rate widgets
  - Add widgets for NumberOfMessagesSent and NumberOfMessagesReceived metrics
  - Configure rate-based statistics and time periods
  - Position widgets to show message flow patterns
  - _Requirements: 2.4_

- [x] 6.5 Write property test for SQS metrics completeness
  - **Property 2: SQS metrics completeness**
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 7. Add Processor function section header
  - Create "Lambda Functions - Processor" text header widget
  - Position header widget above existing Processor metrics
  - Ensure all existing Processor widgets are preserved
  - _Requirements: 3.5, 4.3, 4.4, 4.5_

- [x] 7.1 Write property test for existing widget preservation
  - **Property 7: Existing widget preservation**
  - **Validates: Requirements 3.5**

- [x] 8. Validate and adjust widget positioning
- [x] 8.1 Ensure consistent widget widths
  - Verify all widgets follow standard width patterns (6, 12, 24 columns)
  - Adjust any widgets that don't conform to design standards
  - Maintain visual consistency across all sections
  - _Requirements: 3.4_

- [x] 8.2 Validate section header formatting
  - Ensure all text headers have consistent height (2 units) and width (24 columns)
  - Verify markdown formatting is consistent across all headers
  - Check positioning relative to their metric sections
  - _Requirements: 4.4_

- [x] 8.3 Write property test for widget width consistency
  - **Property 6: Widget width consistency**
  - **Validates: Requirements 3.4**

- [x] 8.4 Write property test for text header formatting consistency
  - **Property 8: Text header formatting consistency**
  - **Validates: Requirements 4.4**

- [x] 9. Update alarms widget configuration
  - Verify alarms widget includes all existing alarm references
  - Ensure both Ingestor and Processor function alarms are included
  - Validate alarm ARN format and CloudFormation parameter references
  - _Requirements: 5.2_

- [x] 9.1 Write property test for alarm references completeness
  - **Property 9: Alarm references completeness**
  - **Validates: Requirements 5.2**

- [x] 10. Final layout validation and testing
- [x] 10.1 Validate complete dashboard structure
  - Parse final dashboard JSON to verify all widgets are properly positioned
  - Check that all sections have appropriate headers and metrics
  - Ensure no widgets overlap or extend beyond grid boundaries
  - _Requirements: 3.1, 4.5_

- [x] 10.2 Write property test for section header positioning
  - **Property 4: Section header presence and positioning**
  - **Validates: Requirements 3.2, 4.1, 4.2, 4.3, 4.5**

- [x] 10.3 Write property test for coordinate adjustment validation
  - **Property 10: Coordinate adjustment for alarms positioning**
  - **Validates: Requirements 5.4**

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.