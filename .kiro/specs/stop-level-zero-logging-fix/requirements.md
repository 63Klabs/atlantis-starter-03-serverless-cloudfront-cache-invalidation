# Requirements Document

## Introduction

This feature fixes the commented-out logging functionality for ConsolidationStopLevel=0 in the path consolidation system. The logging code exists but is commented out, causing the property test `test_property_3_stop_level_zero_logging` to fail. This fix ensures that when ConsolidationStopLevel=0 is used, the system properly logs the root consolidation behavior as expected by the existing property-based test.

## Glossary

- **ConsolidationStopLevel**: Directory depth level where consolidation is prevented for shallower depths
- **Stop_Level_Zero**: Special case where ConsolidationStopLevel=0 triggers immediate root consolidation
- **Root_Consolidation**: Consolidating all paths to the single wildcard `/*`
- **Property_Test**: Automated test that verifies universal properties across many generated inputs
- **Path_Consolidator**: Module responsible for consolidating invalidation paths

## Requirements

### Requirement 1

**User Story:** As a system operator, I want ConsolidationStopLevel=0 operations to be properly logged, so that I can monitor and troubleshoot root consolidation behavior.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel is set to 0, THE system SHALL log that root consolidation is being applied
2. WHEN logging stop level 0 behavior, THE system SHALL include the stop level value in the log entry
3. WHEN logging stop level 0 behavior, THE system SHALL include the original path count in the log entry
4. WHEN logging stop level 0 behavior, THE system SHALL include the consolidation type as 'stop_level_zero_override'
5. WHEN logging stop level 0 behavior, THE system SHALL include that all other consolidation logic was bypassed

### Requirement 2

**User Story:** As a developer, I want the existing property test to pass, so that the test suite validates the stop level zero logging functionality correctly.

#### Acceptance Criteria

1. WHEN the property test `test_property_3_stop_level_zero_logging` runs, THE system SHALL pass the test
2. WHEN the property test generates random paths with stop level 0, THE system SHALL produce the expected log output
3. WHEN the property test checks for log content, THE system SHALL have logged the required fields in the correct format
4. WHEN the property test validates log structure, THE system SHALL use the JSON formatter as expected
5. WHEN the property test completes, THE system SHALL have demonstrated that stop level 0 logging works correctly

### Requirement 3

**User Story:** As a platform administrator, I want the logging to be consistent with the existing logging patterns, so that log analysis tools and procedures continue to work correctly.

#### Acceptance Criteria

1. WHEN stop level 0 logging occurs, THE system SHALL use the same JSON formatter as other log entries
2. WHEN stop level 0 logging occurs, THE system SHALL use the INFO log level
3. WHEN stop level 0 logging occurs, THE system SHALL include fields at the top level of the JSON structure
4. WHEN stop level 0 logging occurs, THE system SHALL maintain consistency with existing log field naming conventions
5. WHEN stop level 0 logging occurs, THE system SHALL ensure the log entry is parseable as valid JSON