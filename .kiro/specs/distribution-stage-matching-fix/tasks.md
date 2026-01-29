# Distribution Stage Matching Fix - Implementation Tasks

## Overview

This task list implements the surgical fix for the distribution stage matching bug. The changes are minimal and isolated to the grouping logic in `handler.py`.

**Total Estimated Lines Changed**: 15-20 lines in 1 file
**Risk Level**: LOW
**Files Modified**: 1 (`handler.py`)

---

## Phase 1: Code Implementation

### 1. Update Grouping Function
**File**: `application-infrastructure/functions/processor/handler.py`

- [ ] 1.1 Update function signature to return 3-tuple dict
  - Change return type from `Dict[Tuple[str, str], List[Dict]]` to `Dict[Tuple[str, str, str], List[Dict]]`
  - Update type hints at function definition (line ~50)

- [ ] 1.2 Extract stage_id from each message
  - Add line: `stage_id = parsed_body.get('stageId', '')`
  - Location: After extracting `bucket_name` and `origin_path` (line ~125)
  - Use empty string as default for missing stage

- [ ] 1.3 Update grouping key to 3-tuple
  - Change: `group_key = (bucket_name, origin_path)`
  - To: `group_key = (bucket_name, origin_path, stage_id)`
  - Location: Line ~140

- [ ] 1.4 Update function docstring
  - Add `stageId` to the Args section
  - Update Returns section to mention 3-tuple keys
  - Add note about stage separation
  - Location: Lines ~52-70

- [ ] 1.5 Update grouping summary log (optional)
  - Add `'stage': stage` to the groups list in log message
  - Location: Line ~195
  - Helps with debugging and monitoring

### 2. Update Handler Main Loop
**File**: `application-infrastructure/functions/processor/handler.py`

- [ ] 2.1 Update loop to unpack 3-tuple
  - Change: `for (bucket_name, origin_path), messages in grouped_messages.items():`
  - To: `for (bucket_name, origin_path, stage_id), messages in grouped_messages.items():`
  - Location: Line ~400

- [ ] 2.2 Remove stage extraction from first event
  - Delete lines that extract stage_id from first_filtered_message
  - Location: Lines ~550-560 (approximately)
  - Delete these lines:
    ```python
    first_filtered_message = filtered_messages[0]
    first_filtered_body = first_filtered_message.get('parsed_body', {})
    stage_id = first_filtered_body.get('stageId', '')
    ```
  - Add comment: `# stage_id already available from group key`

- [ ] 2.3 Update group processing start log
  - Add `'stage_id': stage_id` to extra_fields
  - Location: Line ~410
  - Helps correlate logs with specific stage groups

- [ ] 2.4 Update origin path resolution log
  - Verify `'stage_id': stage_id` is already in log (should be)
  - Location: Line ~570
  - If missing, add it

- [ ] 2.5 Update distribution search log
  - Add `'stage_id': stage_id` to extra_fields
  - Location: Line ~650
  - Shows which stage is being searched

- [ ] 2.6 Update distribution validation failure log
  - Add `'stage_id': stage_id` to extra_fields
  - Location: Line ~680
  - Shows which stage failed validation

- [ ] 2.7 Update stage processing log
  - Add `'stage_id': stage_id` to extra_fields for correlation
  - Location: Line ~850
  - Correlates consolidated stage with group stage

---

## Phase 2: Testing

### 3. Unit Tests - Grouping Logic
**File**: `application-infrastructure/tests/unit/test_handler_grouping.py` (NEW FILE)

- [ ] 3.1 Create test file structure
  - Import necessary modules
  - Set up test fixtures
  - Create helper functions for test data

- [ ] 3.2 Test: Separate stages create separate groups
  - Test name: `test_group_by_bucket_origin_stage_separates_stages`
  - Input: 2 events, same bucket/origin, different stages (prod, beta)
  - Expected: 2 groups
  - Validates: Requirement 3.2 (different stages in different groups)

- [ ] 3.3 Test: Same stage combines into one group
  - Test name: `test_group_by_bucket_origin_stage_combines_same_stage`
  - Input: 3 events, same bucket/origin/stage
  - Expected: 1 group with 3 messages
  - Validates: Requirement 3.1 (same stage grouped together)

- [ ] 3.4 Test: Missing stage_id handled correctly
  - Test name: `test_group_by_bucket_origin_stage_handles_missing_stage`
  - Input: 2 events, one with stage, one without
  - Expected: 2 groups (empty string is separate)
  - Validates: Requirement 11.1 (handle missing stageId)

- [ ] 3.5 Test: Multiple buckets and stages
  - Test name: `test_group_by_bucket_origin_stage_multiple_buckets_stages`
  - Input: 6 events (2 buckets × 3 stages)
  - Expected: 6 groups
  - Validates: Requirement 3.3 (each group has single stage)

- [ ] 3.6 Test: Handler uses group stage not first event
  - Test name: `test_handler_uses_group_stage_not_first_event`
  - Mock: `validate_distribution_tags` to capture arguments
  - Input: Group with stage="beta"
  - Expected: validate called with stage="beta"
  - Validates: Requirement 4.2 (validation uses group's stage)

### 4. Integration Tests - Multi-Stage Scenarios
**File**: `application-infrastructure/tests/integration/test_multi_stage_invalidation.py` (NEW FILE)

- [ ] 4.1 Create test file structure
  - Set up mocks for AWS services (S3, CloudFront, SQS)
  - Create test distributions with different stages
  - Create helper functions for test scenarios

- [ ] 4.2 Test: Multi-stage bucket separate invalidations
  - Test name: `test_multi_stage_bucket_separate_invalidations`
  - Setup: Bucket with prod and beta distributions
  - Input: Events for both stages
  - Expected: Prod dist gets prod paths, beta dist gets beta paths
  - Validates: Requirements 1.1, 1.2, 2.1, 2.2

- [ ] 4.3 Test: Single-stage bucket backward compatible
  - Test name: `test_single_stage_bucket_backward_compatible`
  - Setup: Bucket with only prod distribution
  - Input: Prod events only
  - Expected: Works exactly as before
  - Validates: Requirement 8.1 (single-stage buckets work)

- [ ] 4.4 Test: Root-level bucket no stages
  - Test name: `test_root_level_bucket_no_stages`
  - Setup: Bucket with pattern `/` (no stages)
  - Input: Events with empty stage
  - Expected: Invalidations work correctly
  - Validates: Requirement 8.2 (root-level buckets work)

- [ ] 4.5 Test: Mixed events in same batch
  - Test name: `test_mixed_stages_same_batch`
  - Setup: Bucket with multiple stage distributions
  - Input: Batch with prod, beta, staging events mixed
  - Expected: Each stage invalidates correct distribution
  - Validates: Requirements 1.3, 1.4

### 5. Regression Testing
**Files**: All existing test files

- [ ] 5.1 Run existing unit tests
  - Command: `pytest tests/unit/ -v`
  - Expected: All tests pass
  - Validates: Requirement 12.1 (existing unit tests pass)

- [ ] 5.2 Run existing integration tests
  - Command: `pytest tests/integration/ -v`
  - Expected: All tests pass
  - Validates: Requirement 12.2 (existing integration tests pass)

- [ ] 5.3 Run existing property-based tests
  - Command: `pytest tests/property/ -v`
  - Expected: All tests pass
  - Validates: Requirement 12.3 (existing property tests pass)

- [ ] 5.4 Review test output for warnings
  - Check for deprecation warnings
  - Check for type hint warnings
  - Fix any issues found

---

## Phase 3: Validation and Deployment

### 6. Code Review and Validation

- [ ] 6.1 Review code changes
  - Verify only 15-20 lines changed
  - Verify no changes to consolidation algorithm
  - Verify no changes to distribution matching logic
  - Verify no changes to tag validation logic
  - Validates: Requirement 16.1 (surgical changes only)

- [ ] 6.2 Review test coverage
  - Verify new tests cover all edge cases
  - Verify regression tests all pass
  - Check code coverage metrics
  - Validates: Requirements 12.4, 13.1-13.5

- [ ] 6.3 Manual code inspection
  - Check type hints are correct
  - Check docstrings are updated
  - Check logging is consistent
  - Check error handling is preserved

### 7. Local Testing

- [ ] 7.1 Set up local test environment
  - Activate virtual environment
  - Install test dependencies
  - Set up test fixtures

- [ ] 7.2 Run full test suite locally
  - Run all unit tests
  - Run all integration tests
  - Run all property tests
  - Verify 100% pass rate

- [ ] 7.3 Manual testing with sample data
  - Create sample multi-stage events
  - Run handler locally with mocked AWS services
  - Verify grouping works correctly
  - Verify distributions are matched correctly

### 8. Deployment to Dev

- [ ] 8.1 Deploy code to dev environment
  - Use standard deployment pipeline
  - Verify deployment succeeds
  - Check CloudFormation stack status

- [ ] 8.2 Smoke test in dev
  - Trigger test events for multi-stage bucket
  - Check CloudWatch logs for correct grouping
  - Verify invalidations target correct distributions
  - Validates: Requirement 15.1 (end-to-end flow works)

- [ ] 8.3 Monitor dev environment
  - Check for errors in CloudWatch
  - Check invalidation success rate
  - Check message deletion rate
  - Validates: Requirement 15.2 (message deletion correct)

### 9. Deployment to Staging

- [ ] 9.1 Deploy code to staging environment
  - Use standard deployment pipeline
  - Verify deployment succeeds
  - Check CloudFormation stack status

- [ ] 9.2 Full testing in staging
  - Test with real multi-stage buckets
  - Test with single-stage buckets
  - Test with root-level buckets
  - Verify all scenarios work correctly

- [ ] 9.3 Performance validation
  - Check Lambda execution time
  - Check memory usage
  - Compare with baseline metrics
  - Validates: Requirement 9.1 (no performance degradation)

### 10. Deployment to Production

- [ ] 10.1 Final pre-production checklist
  - All tests passing
  - Dev and staging validated
  - Rollback plan documented
  - Monitoring alerts configured

- [ ] 10.2 Deploy to production
  - Use standard deployment pipeline
  - Monitor deployment closely
  - Be ready to rollback if needed

- [ ] 10.3 Post-deployment validation
  - Monitor CloudWatch logs for 1 hour
  - Check invalidation success rate
  - Check for any errors or warnings
  - Verify multi-stage buckets work correctly

- [ ] 10.4 Long-term monitoring
  - Monitor for 24 hours
  - Check success metrics
  - Verify no regressions
  - Document any issues found

---

## Phase 4: Documentation and Cleanup

### 11. Documentation Updates

- [ ] 11.1 Update CHANGELOG.md
  - Add entry for bug fix
  - Describe the issue and solution
  - Note backward compatibility

- [ ] 11.2 Update README if needed
  - Add note about multi-stage support
  - Update any relevant examples
  - Update architecture diagrams if needed

- [ ] 11.3 Update inline code comments
  - Ensure comments explain stage grouping
  - Add references to requirements/design docs
  - Remove any outdated comments

### 12. Final Validation

- [ ] 12.1 Verify all requirements met
  - Review requirements.md
  - Check each acceptance criterion
  - Document any deviations

- [ ] 12.2 Verify all correctness properties
  - Review design.md properties
  - Verify each property is tested
  - Verify each property holds in production

- [ ] 12.3 Close out spec
  - Mark all tasks complete
  - Archive spec documentation
  - Update project status

---

## Rollback Plan

If issues are detected at any phase:

1. **Immediate Rollback**:
   - Revert the single commit
   - Redeploy previous version
   - Verify system returns to previous behavior

2. **Investigation**:
   - Review CloudWatch logs
   - Identify root cause
   - Determine if fix is needed or design issue

3. **Re-deployment**:
   - Fix identified issues
   - Re-run all tests
   - Deploy through dev → staging → prod again

---

## Success Criteria

- ✅ All tasks completed
- ✅ All tests passing (existing + new)
- ✅ Multi-stage buckets work correctly
- ✅ Single-stage buckets still work (backward compatible)
- ✅ No performance degradation
- ✅ No errors in production logs
- ✅ Monitoring shows correct behavior

---

## Notes

- **Estimated Time**: 4-6 hours for implementation and testing
- **Risk Level**: LOW (minimal changes, well-tested)
- **Dependencies**: None (isolated change)
- **Rollback Time**: < 5 minutes (single commit revert)
