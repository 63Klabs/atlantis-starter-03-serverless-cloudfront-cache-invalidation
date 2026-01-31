# Distribution Tag Validation Fix for Missing StageId - Design Document

## 1. Overview

### 1.1 Purpose
This design document specifies the changes needed to fix the distribution tag validation logic in `tag_validator.py` to correctly handle cases where there is no `stageId` in the bucket pattern. The current implementation incorrectly constructs an expected `ApplicationDeploymentId` with a trailing hyphen when `stage_id` is empty, leading to validation failures.

### 1.2 Problem Summary
When a bucket pattern does not include `{stageId}`, the `stage_id` variable is set to an empty string. The current validation logic constructs an expected `ApplicationDeploymentId` as `{bucket_app_tag}-{stage_id}`, which results in a trailing hyphen (e.g., `xcme-cdninval-a-`) when `stage_id` is empty. This causes exact match validation to fail even when the distribution's `ApplicationDeploymentId` correctly starts with the expected prefix.

**Current Error:**
```
Distribution tag validation failed for E2G4RY69EPFNR7: ApplicationDeploymentId mismatch: 
expected=xcme-cdninval-a-, actual=xcme-cdninval-a-prod
```

**Expected Behavior:**
- When `stage_id` is empty: construct expected value as `xcme-cdninval-a` (no trailing hyphen)
- Use prefix matching instead of exact match: accept any distribution where `ApplicationDeploymentId` starts with `xcme-cdninval-a`
- When `stage_id` is non-empty: maintain existing exact match behavior

### 1.3 Scope
- **In Scope:**
  - Modify `validate_distribution_tags()` function in `tag_validator.py`
  - Add logic to detect empty/None `stage_id`
  - Implement prefix matching for empty `stage_id` scenarios
  - Update logging to indicate match type (prefix vs exact)
  - Add comprehensive unit tests for both scenarios
  - Maintain backward compatibility with existing stage-based validation

- **Out of Scope:**
  - Changes to bucket tag validation logic
  - Modifications to `AllowInvalidationEvents` validation
  - Changes to distribution discovery or other tag validation functions
  - Infrastructure or CloudFormation template changes

## 2. Current Implementation Analysis

### 2.1 Current Code Structure
The `validate_distribution_tags()` function in `tag_validator.py` (lines 520-650) currently:

1. Accepts three parameters: `distribution_id`, `bucket_app_tag`, `stage_id`
2. Retrieves distribution tags via `get_distribution_tags()`
3. Validates `AllowInvalidationEvents` tag equals "true"
4. Constructs expected `ApplicationDeploymentId` as `f"{bucket_app_tag}-{stage_id}"`
5. Performs exact match comparison: `app_deployment_id == expected_app_deployment_id`
6. Returns `True` only if both validations pass

### 2.2 Current Validation Logic
```python
# Current implementation (simplified)
expected_app_deployment_id = f"{bucket_app_tag}-{stage_id}"
app_deployment_id_valid = app_deployment_id == expected_app_deployment_id
```

**Problem:** When `stage_id = ""`, this produces:
- Expected: `"xcme-cdninval-a-"` (with trailing hyphen)
- Actual: `"xcme-cdninval-a-prod"`
- Match: `False` (incorrect)

### 2.3 Affected Code Locations
- **Primary:** `application-infrastructure/functions/processor/tag_validator.py`
  - Function: `validate_distribution_tags()` (lines ~520-650)
- **Tests:** `application-infrastructure/tests/unit/test_tag_validator.py`
  - Existing tests for `validate_distribution_tags()`
  - New tests needed for empty `stage_id` scenarios

## 3. Design Solution

### 3.1 High-Level Approach
Implement conditional validation logic based on whether `stage_id` is empty:

1. **Empty StageId Path:**
   - Construct expected value without trailing hyphen
   - Use prefix matching (`startswith()`)
   - Accept any distribution where `ApplicationDeploymentId` starts with expected prefix

2. **Non-Empty StageId Path:**
   - Maintain existing exact match behavior
   - Ensure backward compatibility

### 3.2 Detailed Design

#### 3.2.1 Modified Validation Logic
```python
def validate_distribution_tags(
    distribution_id: str,
    bucket_app_tag: str,
    stage_id: str
) -> bool:
    """Validate distribution tags with support for empty stage_id.
    
    When stage_id is empty or None:
    - Expected ApplicationDeploymentId: {bucket_app_tag} (no trailing hyphen)
    - Validation: Prefix match (distribution tag must start with expected value)
    
    When stage_id is non-empty:
    - Expected ApplicationDeploymentId: {bucket_app_tag}-{stage_id}
    - Validation: Exact match (existing behavior)
    """
    
    # Retrieve distribution tags
    tags = get_distribution_tags(distribution_id)
    if tags is None:
        return False
    
    # Validate AllowInvalidationEvents (unchanged)
    allow_invalidation = tags.get('AllowInvalidationEvents', '')
    allow_invalidation_valid = allow_invalidation == 'true'
    
    # Get actual ApplicationDeploymentId
    app_deployment_id = tags.get('atlantis:ApplicationDeploymentId', '')
    
    # Determine validation strategy based on stage_id
    if not stage_id:  # Empty or None
        # Construct expected value without trailing hyphen
        expected_app_deployment_id = bucket_app_tag
        
        # Use prefix matching
        app_deployment_id_valid = app_deployment_id.startswith(expected_app_deployment_id)
        match_type = "prefix"
    else:
        # Construct expected value with stage_id
        expected_app_deployment_id = f"{bucket_app_tag}-{stage_id}"
        
        # Use exact matching (existing behavior)
        app_deployment_id_valid = app_deployment_id == expected_app_deployment_id
        match_type = "exact"
    
    # Log validation details with match type
    logger.info(
        f"Distribution tag validation for {distribution_id}",
        extra={'extra_fields': {
            'distribution_id': distribution_id,
            'match_type': match_type,
            'expected_app_deployment_id': expected_app_deployment_id,
            'actual_app_deployment_id': app_deployment_id,
            'app_deployment_id_valid': app_deployment_id_valid,
            'allow_invalidation_valid': allow_invalidation_valid
        }}
    )
    
    return allow_invalidation_valid and app_deployment_id_valid
```

#### 3.2.2 Decision Logic Flow
```
Input: distribution_id, bucket_app_tag, stage_id
  |
  v
Retrieve distribution tags
  |
  v
Validate AllowInvalidationEvents == "true"
  |
  v
Check if stage_id is empty/None
  |
  +-- YES (empty) --> expected = bucket_app_tag
  |                   validation = startswith(expected)
  |                   match_type = "prefix"
  |
  +-- NO (non-empty) -> expected = bucket_app_tag + "-" + stage_id
                        validation = equals(expected)
                        match_type = "exact"
  |
  v
Return: allow_invalidation_valid AND app_deployment_id_valid
```

### 3.3 Edge Cases and Handling

#### 3.3.1 Empty StageId Scenarios
| Scenario | Expected | Actual | Match Type | Result |
|----------|----------|--------|------------|--------|
| Empty string | `xcme-cdninval-a` | `xcme-cdninval-a-prod` | prefix | ✅ Valid |
| Empty string | `xcme-cdninval-a` | `xcme-cdninval-a-dev` | prefix | ✅ Valid |
| Empty string | `xcme-cdninval-a` | `xcme-cdninval-a` | prefix | ✅ Valid |
| Empty string | `xcme-cdninval-a` | `xcme-cdninval-b-prod` | prefix | ❌ Invalid |
| None | `xcme-cdninval-a` | `xcme-cdninval-a-prod` | prefix | ✅ Valid |

#### 3.3.2 Non-Empty StageId Scenarios (Existing Behavior)
| Scenario | Expected | Actual | Match Type | Result |
|----------|----------|--------|------------|--------|
| "prod" | `xcme-cdninval-a-prod` | `xcme-cdninval-a-prod` | exact | ✅ Valid |
| "prod" | `xcme-cdninval-a-prod` | `xcme-cdninval-a-dev` | exact | ❌ Invalid |
| "dev" | `xcme-cdninval-a-dev` | `xcme-cdninval-a-dev` | exact | ✅ Valid |

#### 3.3.3 Special Cases
- **Whitespace-only stage_id:** Treat as empty (use `not stage_id` or `not stage_id.strip()`)
- **Case sensitivity:** Maintain case-sensitive comparison (existing behavior)
- **Missing ApplicationDeploymentId tag:** Returns empty string, fails validation (existing behavior)

### 3.4 Logging Enhancements

#### 3.4.1 Enhanced Log Messages
```python
# Success log (prefix match)
logger.info(
    f"Distribution tag validation passed for {distribution_id} (prefix match)",
    extra={'extra_fields': {
        'distribution_id': distribution_id,
        'validation_result': True,
        'match_type': 'prefix',
        'expected_prefix': expected_app_deployment_id,
        'actual_app_deployment_id': app_deployment_id,
        'allow_invalidation_events': allow_invalidation
    }}
)

# Success log (exact match)
logger.info(
    f"Distribution tag validation passed for {distribution_id} (exact match)",
    extra={'extra_fields': {
        'distribution_id': distribution_id,
        'validation_result': True,
        'match_type': 'exact',
        'expected_app_deployment_id': expected_app_deployment_id,
        'actual_app_deployment_id': app_deployment_id,
        'allow_invalidation_events': allow_invalidation
    }}
)

# Failure log (with match type)
logger.warning(
    f"Distribution tag validation failed for {distribution_id}: "
    f"ApplicationDeploymentId mismatch ({match_type} match)",
    extra={'extra_fields': {
        'distribution_id': distribution_id,
        'validation_result': False,
        'match_type': match_type,
        'expected': expected_app_deployment_id,
        'actual': app_deployment_id,
        'reason': 'app_deployment_id_mismatch'
    }}
)
```

## 4. Testing Strategy

### 4.1 Unit Tests

#### 4.1.1 Test Cases for Empty StageId
```python
def test_validate_distribution_tags_empty_stage_id_prefix_match():
    """Test distribution validation with empty stage_id uses prefix matching."""
    # Distribution: xcme-cdninval-a-prod
    # Expected: xcme-cdninval-a (prefix match)
    # Result: Valid

def test_validate_distribution_tags_empty_stage_id_exact_match():
    """Test distribution validation with empty stage_id accepts exact match."""
    # Distribution: xcme-cdninval-a
    # Expected: xcme-cdninval-a (prefix match, also exact)
    # Result: Valid

def test_validate_distribution_tags_empty_stage_id_no_match():
    """Test distribution validation with empty stage_id rejects non-matching prefix."""
    # Distribution: xcme-cdninval-b-prod
    # Expected: xcme-cdninval-a (prefix match)
    # Result: Invalid

def test_validate_distribution_tags_none_stage_id():
    """Test distribution validation with None stage_id uses prefix matching."""
    # stage_id: None
    # Distribution: xcme-cdninval-a-prod
    # Expected: xcme-cdninval-a (prefix match)
    # Result: Valid
```

#### 4.1.2 Test Cases for Non-Empty StageId (Regression)
```python
def test_validate_distribution_tags_with_stage_id_exact_match():
    """Test distribution validation with stage_id uses exact matching."""
    # stage_id: "prod"
    # Distribution: xcme-cdninval-a-prod
    # Expected: xcme-cdninval-a-prod (exact match)
    # Result: Valid

def test_validate_distribution_tags_with_stage_id_no_match():
    """Test distribution validation with stage_id rejects different stage."""
    # stage_id: "prod"
    # Distribution: xcme-cdninval-a-dev
    # Expected: xcme-cdninval-a-prod (exact match)
    # Result: Invalid
```

#### 4.1.3 Test Cases for AllowInvalidationEvents (Unchanged)
```python
def test_validate_distribution_tags_missing_allow_invalidation():
    """Test validation fails when AllowInvalidationEvents is missing."""
    # AllowInvalidationEvents: missing
    # Result: Invalid

def test_validate_distribution_tags_false_allow_invalidation():
    """Test validation fails when AllowInvalidationEvents is false."""
    # AllowInvalidationEvents: "false"
    # Result: Invalid
```

### 4.2 Integration Tests
- Test end-to-end flow with real S3 events from buckets without `{stageId}`
- Verify distributions are correctly matched using prefix logic
- Confirm existing stage-based flows continue to work

### 4.3 Property-Based Tests (Optional)
Per testing guidelines, property-based tests are optional for this fix. If implemented:
- Property: For any `bucket_app_tag` and empty `stage_id`, validation should accept any distribution where `ApplicationDeploymentId` starts with `bucket_app_tag`
- Property: For any `bucket_app_tag` and non-empty `stage_id`, validation should only accept exact match of `{bucket_app_tag}-{stage_id}`

## 5. Implementation Plan

### 5.1 Code Changes
1. **Modify `validate_distribution_tags()` function:**
   - Add conditional logic to detect empty `stage_id`
   - Implement prefix matching for empty `stage_id`
   - Maintain exact matching for non-empty `stage_id`
   - Update logging to include match type

2. **Update function docstring:**
   - Document the two validation modes
   - Clarify when each mode is used
   - Update examples

### 5.2 Test Changes
1. **Add new unit tests:**
   - Empty `stage_id` with prefix match (valid)
   - Empty `stage_id` with exact match (valid)
   - Empty `stage_id` with no match (invalid)
   - None `stage_id` (valid)

2. **Update existing tests:**
   - Ensure regression tests cover non-empty `stage_id` scenarios
   - Verify `AllowInvalidationEvents` validation unchanged

### 5.3 Documentation Updates
- Update function docstring in `tag_validator.py`
- Add inline comments explaining the conditional logic
- Update any relevant architecture documentation

## 6. Backward Compatibility

### 6.1 Compatibility Analysis
This change is **fully backward compatible**:

1. **Existing stage-based validation:** Unchanged behavior when `stage_id` is non-empty
2. **Exact match logic:** Preserved for non-empty `stage_id`
3. **AllowInvalidationEvents validation:** Unchanged
4. **API signatures:** No changes to function parameters or return types
5. **Logging structure:** Enhanced but maintains existing fields

### 6.2 Migration Path
No migration required. The fix automatically handles both scenarios:
- Buckets with `{stageId}` in pattern: Continue using exact match
- Buckets without `{stageId}` in pattern: Automatically use prefix match

## 7. Security Considerations

### 7.1 Security Impact
- **AllowInvalidationEvents validation:** Unchanged - still required to be "true"
- **Prefix matching security:** More permissive than exact match, but still validates the application prefix
- **Authorization model:** Maintains tag-based authorization approach

### 7.2 Risk Assessment
**Low Risk:** The prefix matching approach is more permissive but still validates:
1. The distribution has `AllowInvalidationEvents=true`
2. The distribution's `ApplicationDeploymentId` starts with the correct application identifier

This ensures only distributions belonging to the same application can receive invalidations, which aligns with the intended security model.

### 7.3 Mitigation
If stricter validation is needed in the future, consider:
- Adding a bucket tag to explicitly enable prefix matching mode
- Implementing a whitelist of allowed stage suffixes
- Adding CloudWatch alarms for prefix-matched validations

## 8. Performance Considerations

### 8.1 Performance Impact
**Negligible:** The change adds a simple string comparison (`startswith()` vs `==`), which has minimal performance impact.

### 8.2 Optimization Opportunities
None required. The validation logic remains O(1) for both match types.

## 9. Monitoring and Observability

### 9.1 Logging Enhancements
- Add `match_type` field to all validation logs ("prefix" or "exact")
- Include expected value and actual value in all log messages
- Maintain existing structured logging format

### 9.2 Metrics
Consider adding CloudWatch metrics:
- Count of prefix match validations
- Count of exact match validations
- Ratio of prefix to exact matches

### 9.3 Alarms
No new alarms required. Existing validation failure alarms will continue to work.

## 10. Rollout Plan

### 10.1 Deployment Strategy
1. **Phase 1:** Deploy code changes to development environment
2. **Phase 2:** Run integration tests with both empty and non-empty `stage_id` scenarios
3. **Phase 3:** Deploy to staging environment
4. **Phase 4:** Monitor logs for 24 hours
5. **Phase 5:** Deploy to production

### 10.2 Rollback Plan
If issues arise:
1. Revert to previous version of `tag_validator.py`
2. Investigate validation failures in logs
3. Fix and redeploy

### 10.3 Success Criteria
- All unit tests pass
- Integration tests pass for both scenarios
- No increase in validation failure rate
- Logs show correct match type for each scenario

## 11. Correctness Properties

### 11.1 Formal Properties

#### Property 1: Empty StageId Prefix Matching
**Statement:** For any distribution with `AllowInvalidationEvents=true` and `ApplicationDeploymentId` starting with `bucket_app_tag`, validation should pass when `stage_id` is empty.

**Validates:** Requirements 1.1, 1.2, 1.3, 1.4, 1.5

**Test Strategy:** Unit tests with various prefix combinations

#### Property 2: Non-Empty StageId Exact Matching
**Statement:** For any distribution with `AllowInvalidationEvents=true` and `ApplicationDeploymentId` equal to `{bucket_app_tag}-{stage_id}`, validation should pass when `stage_id` is non-empty.

**Validates:** Requirements 2.1, 2.2, 2.3, 2.4

**Test Strategy:** Unit tests with exact match scenarios

#### Property 3: AllowInvalidationEvents Required
**Statement:** For any distribution, validation should fail if `AllowInvalidationEvents` is not "true", regardless of `ApplicationDeploymentId` match.

**Validates:** Requirements 3.1, 3.2

**Test Strategy:** Unit tests with missing or incorrect `AllowInvalidationEvents`

#### Property 4: Match Type Consistency
**Statement:** The match type logged should always be "prefix" when `stage_id` is empty and "exact" when `stage_id` is non-empty.

**Validates:** FR-5 (logging requirement)

**Test Strategy:** Unit tests verifying log output

## 12. Open Questions and Decisions

### 12.1 Resolved Decisions

**Decision 1: Use `startswith()` for prefix matching**
- **Rationale:** Simple, performant, and clear intent
- **Alternative considered:** Regular expressions (rejected as overkill)

**Decision 2: Treat None and empty string identically**
- **Rationale:** Both indicate absence of stage_id
- **Alternative considered:** Different handling (rejected for simplicity)

**Decision 3: No configuration flag for match type**
- **Rationale:** Automatic detection based on `stage_id` is simpler
- **Alternative considered:** Bucket tag to control match type (rejected as unnecessary)

### 12.2 Open Questions
None at this time.

## 13. References

### 13.1 Related Documents
- Requirements: `.kiro/specs/distribution-tag-validation-no-stage-fix/requirements.md`
- Current Implementation: `application-infrastructure/functions/processor/tag_validator.py`
- Test Suite: `application-infrastructure/tests/unit/test_tag_validator.py`

### 13.2 Related Features
- Multi-bucket CloudFront invalidation
- Dynamic bucket consolidation configuration
- S3 API optimization

## 14. Appendix

### 14.1 Example Scenarios

#### Scenario A: Bucket Without StageId
```
Bucket Pattern: xcme-cdninval-a-{bucketId}
Object Key: /assets/style.css
Extracted stage_id: "" (empty)
Bucket App Tag: xcme-cdninval-a

Distribution Tags:
  AllowInvalidationEvents: "true"
  ApplicationDeploymentId: "xcme-cdninval-a-prod"

Validation:
  Expected: "xcme-cdninval-a"
  Match Type: prefix
  Result: ✅ Valid (starts with expected prefix)
```

#### Scenario B: Bucket With StageId
```
Bucket Pattern: xcme-cdninval-a-{stageId}-{bucketId}
Object Key: /prod/assets/style.css
Extracted stage_id: "prod"
Bucket App Tag: xcme-cdninval-a

Distribution Tags:
  AllowInvalidationEvents: "true"
  ApplicationDeploymentId: "xcme-cdninval-a-prod"

Validation:
  Expected: "xcme-cdninval-a-prod"
  Match Type: exact
  Result: ✅ Valid (exact match)
```

### 14.2 Code Diff Preview
```python
# Before
expected_app_deployment_id = f"{bucket_app_tag}-{stage_id}"
app_deployment_id_valid = app_deployment_id == expected_app_deployment_id

# After
if not stage_id:
    expected_app_deployment_id = bucket_app_tag
    app_deployment_id_valid = app_deployment_id.startswith(expected_app_deployment_id)
    match_type = "prefix"
else:
    expected_app_deployment_id = f"{bucket_app_tag}-{stage_id}"
    app_deployment_id_valid = app_deployment_id == expected_app_deployment_id
    match_type = "exact"
```
