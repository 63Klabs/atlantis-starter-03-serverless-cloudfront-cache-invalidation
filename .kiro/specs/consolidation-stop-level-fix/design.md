# Design Document

## Overview

The ConsolidationStopLevel Fix addresses incorrect behavior in the current implementation where the depth comparison logic is backwards. The current logic `depth >= stop_level` prevents consolidation at shallow depths when it should allow consolidation up to and including the specified depth level. The intended behavior is to allow consolidation at depths up to and including the stop level while preventing consolidation at deeper levels.

This fix modifies the depth comparison logic to ensure that:
- ConsolidationStopLevel=0 continues to work as before (immediate root consolidation)
- ConsolidationStopLevel=1 allows consolidation up to depth 1 (e.g., `/level1/*`, `/*`)
- ConsolidationStopLevel=N allows consolidation up to depth N and shallower

The fix is backward compatible and maintains existing behavior for the default value of 1.

## Architecture

### Current vs. Fixed Logic

**Current (Incorrect) Logic:**
```
is_consolidation_allowed_at_depth(depth, stop_level):
    if stop_level == 0:
        return True  # Special case: consolidate everything to root
    return depth >= stop_level  # WRONG: Prevents shallow consolidation
```

**Fixed Logic:**
```
is_consolidation_allowed_at_depth(depth, stop_level):
    if stop_level == 0:
        return True  # Special case: consolidate everything to root
    return depth <= stop_level  # CORRECT: Allow consolidation up to stop level
```

### Component Changes

The fix involves minimal changes to the existing architecture:

```
┌─────────────────────────────────┐
│  Processor Lambda               │
│  ┌─────────────────────────────┐│
│  │  Path Consolidator          ││
│  │  - Fixed depth logic        ││
│  │  - Corrected stop level     ││
│  │  - Enhanced logging         ││
│  └─────────────────────────────┘│
└─────────────────────────────────┘
```

## Components and Interfaces

### 1. Enhanced Path Consolidator Module

**Modified Function:**
```python
def is_consolidation_allowed_at_depth(depth: int, stop_level: int) -> bool:
    """Check if consolidation is allowed at the given depth.
    
    Args:
        depth: The depth from root directory (of the consolidation target)
        stop_level: The consolidation stop level
        
    Returns:
        True if consolidation is allowed, False otherwise
        
    Fixed Logic:
        - stop_level=0: Allow all consolidation (special case for root)
        - stop_level=N: Allow consolidation at depth N and shallower
        
    Examples:
        is_consolidation_allowed_at_depth(1, 0) -> True  (special case)
        is_consolidation_allowed_at_depth(1, 1) -> True  (depth 1 <= stop level 1)
        is_consolidation_allowed_at_depth(0, 1) -> True  (depth 0 <= stop level 1)
        is_consolidation_allowed_at_depth(2, 1) -> False (depth 2 > stop level 1)
        is_consolidation_allowed_at_depth(1, 2) -> True  (depth 1 <= stop level 2)
        is_consolidation_allowed_at_depth(2, 2) -> True  (depth 2 <= stop level 2)
        is_consolidation_allowed_at_depth(3, 2) -> False (depth 3 > stop level 2)
    """
```

**Enhanced Logging Functions:**
```python
def log_consolidation_decision(depth: int, stop_level: int, allowed: bool, path: str, operation: str):
    """Log consolidation decisions with detailed context."""

def log_stop_level_application(stop_level: int, paths_affected: int, operation_type: str):
    """Log when stop level rules are applied."""
```

### 2. Enhanced Consolidation Functions

All consolidation functions will use the corrected logic:

- `consolidate_index_and_default_files()` - Fixed stop level checking
- `consolidate_by_directory_threshold()` - Fixed stop level checking  
- `consolidate_sibling_directories()` - Fixed stop level checking

### 3. Enhanced Main Consolidation Function

**Modified Function:**
```python
def consolidate_paths(paths: List[str], directory_threshold: int = None, stop_level: int = None) -> List[List[str]]:
    """Enhanced with corrected stop level logic and improved logging."""
```

## Data Models

### Stop Level Decision Context

```python
@dataclass
class StopLevelDecision:
    depth: int                       # Calculated depth of consolidation target
    stop_level: int                  # Configured stop level
    allowed: bool                    # Whether consolidation is allowed
    reason: str                      # Explanation of decision
    path: str                        # Path being evaluated
    operation_type: str              # Type of consolidation (index, directory, sibling)
```

### Consolidation Metrics

```python
@dataclass
class ConsolidationMetrics:
    original_count: int              # Original path count
    consolidated_count: int          # Final path count
    stop_level_blocks: int           # Number of consolidations blocked by stop level
    stop_level_allows: int           # Number of consolidations allowed by stop level
    depth_distribution: Dict[int, int]  # Count of paths at each depth level
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*
### Stop Level Zero Properties

Property 1: Root consolidation for stop level zero
*For any* set of paths, when ConsolidationStopLevel is 0, the system should consolidate all paths to the root wildcard `/*`
**Validates: Requirements 1.1**

Property 2: Stop level zero override behavior
*For any* path configuration and consolidation thresholds, when ConsolidationStopLevel is 0, the system should ignore all other consolidation rules and return `/*`
**Validates: Requirements 1.2**

Property 3: Stop level zero logging
*For any* consolidation operation when ConsolidationStopLevel is 0, the system should log that root consolidation is being applied
**Validates: Requirements 1.3**

### Stop Level Depth Properties

Property 4: Consolidation allowed up to specified depth
*For any* ConsolidationStopLevel N where N > 0, the system should allow consolidation to occur at depth N and shallower
**Validates: Requirements 2.1, 3.1**

Property 5: Consolidation prevented at deep depths
*For any* ConsolidationStopLevel N where N > 0, the system should prevent consolidation at depths greater than N
**Validates: Requirements 2.4, 3.5**

### Depth Calculation Properties

Property 6: Path depth calculation accuracy
*For any* path, the system should calculate directory depth correctly by counting directory levels from the root path
**Validates: Requirements 4.1**

### Logging Properties

Property 7: Stop level prevention logging
*For any* consolidation operation prevented by ConsolidationStopLevel, the system should log the stop level value and the blocked depth
**Validates: Requirements 5.1**

Property 8: Stop level allowance logging
*For any* consolidation operation allowed by ConsolidationStopLevel, the system should log the consolidation decision with depth information
**Validates: Requirements 5.2**

Property 9: Depth calculation logging
*For any* depth calculation performed, the system should include depth values in debug logs
**Validates: Requirements 5.3**

Property 10: Invalid stop level logging
*For any* invalid ConsolidationStopLevel value encountered, the system should log warnings and fallback behavior
**Validates: Requirements 5.5**

### Consolidation Type Properties

Property 11: Index file consolidation stop level compliance
*For any* index or default file consolidation, when ConsolidationStopLevel prevents consolidation at the target depth, the system should not perform the consolidation
**Validates: Requirements 6.1**

Property 12: Directory threshold consolidation stop level compliance
*For any* directory threshold consolidation, when ConsolidationStopLevel prevents consolidation at the target depth, the system should not perform the consolidation
**Validates: Requirements 6.2**

Property 13: Sibling directory consolidation stop level compliance
*For any* sibling directory consolidation, when ConsolidationStopLevel prevents consolidation at the target depth, the system should not perform the consolidation
**Validates: Requirements 6.3**

Property 14: Consolidation type permission at allowed depths
*For any* consolidation operation at a depth where ConsolidationStopLevel allows consolidation, the system should permit all consolidation types (index, directory, sibling) at that depth
**Validates: Requirements 6.4**

Property 15: Stop level precedence over other rules
*For any* scenario where multiple consolidation rules apply, the system should ensure ConsolidationStopLevel takes precedence over other consolidation rules
**Validates: Requirements 6.5**

## Error Handling

### Invalid Stop Level Values

1. **Out of Range Values**
   - Catch: ConsolidationStopLevel values < 0 or > 20
   - Action: Log warning, use default value (1)
   - Continue: Process with default stop level

2. **Non-Numeric Values**
   - Catch: Non-integer ConsolidationStopLevel values
   - Action: Log warning, use default value (1)
   - Continue: Process with default stop level

### Depth Calculation Errors

1. **Invalid Path Formats**
   - Catch: Malformed paths that cannot be processed
   - Action: Log warning, skip path or use safe default depth
   - Continue: Process remaining paths

2. **Root Path Mismatch**
   - Catch: Paths that don't match expected root path structure
   - Action: Log warning, use absolute depth calculation
   - Continue: Process with fallback depth calculation

### Consolidation Logic Errors

1. **Stop Level Logic Failures**
   - Catch: Errors in stop level checking logic
   - Action: Log error, allow consolidation (fail safe)
   - Continue: Process with permissive behavior

2. **Depth Comparison Errors**
   - Catch: Errors comparing depths with stop level
   - Action: Log error, use conservative approach (prevent consolidation)
   - Continue: Process remaining operations

## Testing Strategy

### Unit Testing

Unit tests will verify the corrected stop level logic:

1. **Stop Level Logic Testing**
   - Test `is_consolidation_allowed_at_depth()` with various depth and stop level combinations
   - Test stop level 0 special case behavior
   - Test boundary conditions (depth equals stop level)
   - Test invalid stop level handling

2. **Depth Calculation Testing**
   - Test `calculate_path_depth()` with various path structures
   - Test edge cases (root paths, malformed paths)
   - Test consistency across different root path configurations

3. **Integration Testing**
   - Test complete consolidation flow with corrected stop level logic
   - Test interaction between stop level and different consolidation types
   - Test logging output for various stop level scenarios

4. **Backward Compatibility Testing**
   - Test that stop level 1 maintains existing behavior
   - Test that stop level 0 continues to work as before
   - Test default behavior when stop level is not specified

### Property-Based Testing

Property-based tests will verify universal properties using Hypothesis with 100 iterations minimum:

**Property Test Framework**: Hypothesis for Python

**Generator Strategies**:
- Stop level values (0-20, including invalid values)
- Path structures at various depths (1-10 levels deep)
- Directory and file combinations
- Root path configurations

**Property Test Coverage**:
- Properties 1-15 as defined in the Correctness Properties section
- Each property implemented as a separate test function
- Edge case generation for boundary values and error conditions

### Integration Testing

Integration tests will verify the fix works with the complete system:

1. **End-to-End Stop Level Testing**
   - Deploy with various ConsolidationStopLevel values
   - Send test events with paths at different depths
   - Verify consolidation behavior matches expected stop level logic

2. **Bucket Tag Integration**
   - Test with bucket tags setting different stop levels
   - Verify per-bucket stop level configuration works correctly
   - Test mixed environments with different stop levels per bucket

3. **CloudFormation Parameter Integration**
   - Test with CloudFormation parameters setting stop levels
   - Verify environment variable propagation works correctly
   - Test parameter validation and default behavior

## Implementation Notes

### Code Changes Required

1. **path_consolidator.py**:
   - Fix `is_consolidation_allowed_at_depth()` function logic
   - Enhance logging in consolidation functions
   - Add debug logging for depth calculations

2. **Testing Updates**:
   - Update existing unit tests to reflect corrected behavior
   - Add new test cases for stop level edge cases
   - Update property-based tests with corrected expectations

### Deployment Considerations

1. **Backward Compatibility**: The fix maintains existing behavior for default stop level 1
2. **Zero Downtime**: Changes are internal logic fixes that don't affect API or configuration
3. **Gradual Verification**: Can be tested with specific bucket configurations before wide deployment

### Performance Considerations

1. **No Performance Impact**: Changes are to conditional logic only
2. **Logging Overhead**: Additional debug logging may slightly increase log volume
3. **Memory Usage**: No changes to memory usage patterns

### Security Considerations

1. **No Security Impact**: Changes are to internal consolidation logic only
2. **Input Validation**: Existing stop level validation remains unchanged
3. **Error Handling**: Enhanced error handling provides better security through fail-safe behavior

## Migration Strategy

### Phase 1: Deploy Fixed Logic
- Deploy updated Lambda functions with corrected stop level logic
- Verify existing functionality continues to work (stop level 1 default)
- Monitor logs for any unexpected behavior

### Phase 2: Test Stop Level Configurations
- Test various stop level values in non-production environments
- Verify consolidation behavior matches expected logic
- Update documentation with corrected behavior examples

### Phase 3: Production Rollout
- Gradually apply different stop level configurations to production buckets
- Monitor consolidation effectiveness and CloudFront invalidation patterns
- Update operational procedures and troubleshooting guides