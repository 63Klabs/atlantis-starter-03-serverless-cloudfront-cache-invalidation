# S3 API Optimization - Implementation Tasks

**Feature:** s3-api-optimization  
**Created:** January 30, 2026  
**Status:** Not Started

---

## Task Overview

This task list implements the single fetch with shared state optimization to reduce S3 API calls by 67% in the processor Lambda function.

**Estimated Total Effort:** 7 hours

---

## Phase 1: Add New Functions (2 hours)

### Task 1.1: Create validate_bucket_tags_from_dict() function
- [ ] 1.1 Create validate_bucket_tags_from_dict() function
  - [ ] 1.1.1 Add function signature with type hints
  - [ ] 1.1.2 Implement validation logic (check AllowInvalidationEvents tag)
  - [ ] 1.1.3 Add error handling for None input
  - [ ] 1.1.4 Add logging for validation results
  - [ ] 1.1.5 Add docstring with requirements reference

**Location:** `application-infrastructure/functions/processor/tag_validator.py`  
**Estimated Time:** 30 minutes

---

### Task 1.2: Create get_bucket_consolidation_config_from_dict() function
- [ ] 1.2 Create get_bucket_consolidation_config_from_dict() function
  - [ ] 1.2.1 Add function signature with type hints
  - [ ] 1.2.2 Initialize config with default values
  - [ ] 1.2.3 Extract DirectoryConsolidationThreshold tag
  - [ ] 1.2.4 Extract ConsolidationStopLevel tag
  - [ ] 1.2.5 Extract SiblingDirectoryConsolidationThreshold tag
  - [ ] 1.2.6 Validate tag values using existing validation function
  - [ ] 1.2.7 Add logging for configuration sources
  - [ ] 1.2.8 Add docstring with requirements reference

**Location:** `application-infrastructure/functions/processor/tag_validator.py`  
**Estimated Time:** 45 minutes

---

### Task 1.3: Add unit tests for new functions
- [ ] 1.3 Add unit tests for new functions
  - [ ] 1.3.1 Test validate_bucket_tags_from_dict with valid tags
  - [ ] 1.3.2 Test validate_bucket_tags_from_dict with invalid tags
  - [ ] 1.3.3 Test validate_bucket_tags_from_dict with None input
  - [ ] 1.3.4 Test validate_bucket_tags_from_dict with missing tag
  - [ ] 1.3.5 Test get_bucket_consolidation_config_from_dict with all tags
  - [ ] 1.3.6 Test get_bucket_consolidation_config_from_dict with partial tags
  - [ ] 1.3.7 Test get_bucket_consolidation_config_from_dict with no tags
  - [ ] 1.3.8 Test get_bucket_consolidation_config_from_dict with invalid values
  - [ ] 1.3.9 Test get_bucket_consolidation_config_from_dict with None input
  - [ ] 1.3.10 Verify 100% code coverage for new functions

**Location:** `application-infrastructure/tests/unit/test_tag_validator.py`  
**Estimated Time:** 45 minutes

---

## Phase 2: Refactor Handler (2 hours)

### Task 2.1: Refactor handler to fetch tags once per bucket
- [ ] 2.1 Refactor handler to fetch tags once per bucket
  - [ ] 2.1.1 Move get_bucket_tags() call to start of bucket processing
  - [ ] 2.1.2 Add error handling for tag fetch failure
  - [ ] 2.1.3 Add early exit if tags is None
  - [ ] 2.1.4 Add logging for tag fetch operation
  - [ ] 2.1.5 Update messages_to_delete handling for fetch failures

**Location:** `application-infrastructure/functions/processor/handler.py` (around line 330)  
**Estimated Time:** 30 minutes

---

### Task 2.2: Update handler to use validate_bucket_tags_from_dict()
- [ ] 2.2 Update handler to use validate_bucket_tags_from_dict()
  - [ ] 2.2.1 Replace validate_bucket_tags() call with validate_bucket_tags_from_dict()
  - [ ] 2.2.2 Pass fetched tags to validation function
  - [ ] 2.2.3 Update error handling for validation failure
  - [ ] 2.2.4 Update logging messages
  - [ ] 2.2.5 Remove redundant get_bucket_tags() call

**Location:** `application-infrastructure/functions/processor/handler.py` (around line 330-360)  
**Estimated Time:** 30 minutes

---

### Task 2.3: Update handler to use get_bucket_consolidation_config_from_dict()
- [ ] 2.3 Update handler to use get_bucket_consolidation_config_from_dict()
  - [ ] 2.3.1 Replace get_bucket_consolidation_config() call
  - [ ] 2.3.2 Pass fetched tags and bucket name to config function
  - [ ] 2.3.3 Update error handling for config extraction
  - [ ] 2.3.4 Update logging messages
  - [ ] 2.3.5 Verify fallback to defaults works correctly

**Location:** `application-infrastructure/functions/processor/handler.py` (around line 395)  
**Estimated Time:** 30 minutes

---

### Task 2.4: Add integration tests for handler changes
- [ ] 2.4 Add integration tests for handler changes
  - [ ] 2.4.1 Test single API call per bucket
  - [ ] 2.4.2 Test tag fetch failure handling
  - [ ] 2.4.3 Test validation failure handling
  - [ ] 2.4.4 Test config extraction with fetched tags
  - [ ] 2.4.5 Test multiple buckets in single invocation
  - [ ] 2.4.6 Verify API call count tracking

**Location:** `application-infrastructure/tests/unit/test_processor_handler.py`  
**Estimated Time:** 30 minutes

---

## Phase 3: Testing and Validation (2 hours)

### Task 3.1: Add property-based tests
- [ ] 3.1 Add property-based tests
  - [ ] 3.1.1 Property test: validate_bucket_tags_from_dict never crashes
  - [ ] 3.1.2 Property test: config extraction never crashes
  - [ ] 3.1.3 Property test: threshold validation handles any string
  - [ ] 3.1.4 Property test: validation equivalence with original function
  - [ ] 3.1.5 Property test: config equivalence with original function

**Location:** `application-infrastructure/tests/property/test_properties_tag_validation.py`  
**Estimated Time:** 45 minutes

---

### Task 3.2: Run full test suite and verify coverage
- [ ] 3.2 Run full test suite and verify coverage
  - [ ] 3.2.1 Run all unit tests
  - [ ] 3.2.2 Run all property-based tests
  - [ ] 3.2.3 Run all integration tests
  - [ ] 3.2.4 Generate coverage report
  - [ ] 3.2.5 Verify 100% coverage for new code
  - [ ] 3.2.6 Verify all existing tests pass

**Estimated Time:** 30 minutes

---

### Task 3.3: Performance testing
- [ ] 3.3 Performance testing
  - [ ] 3.3.1 Create performance test comparing before/after
  - [ ] 3.3.2 Measure S3 API call count reduction
  - [ ] 3.3.3 Measure Lambda execution time improvement
  - [ ] 3.3.4 Verify memory usage unchanged
  - [ ] 3.3.5 Document performance results

**Location:** `application-infrastructure/tests/performance/`  
**Estimated Time:** 45 minutes

---

## Phase 4: Documentation and Deployment (1 hour)

### Task 4.1: Update code documentation
- [ ] 4.1 Update code documentation
  - [ ] 4.1.1 Add/update docstrings for all modified functions
  - [ ] 4.1.2 Add inline comments for handler changes
  - [ ] 4.1.3 Update module-level documentation
  - [ ] 4.1.4 Add type hints where missing

**Estimated Time:** 20 minutes

---

### Task 4.2: Update architecture documentation
- [ ] 4.2 Update architecture documentation
  - [ ] 4.2.1 Update ARCHITECTURE.md with optimization details
  - [ ] 4.2.2 Add sequence diagram to design doc
  - [ ] 4.2.3 Document API call reduction
  - [ ] 4.2.4 Update performance characteristics

**Location:** `ARCHITECTURE.md`, `.kiro/specs/s3-api-optimization/design.md`  
**Estimated Time:** 20 minutes

---

### Task 4.3: Prepare for deployment
- [ ] 4.3 Prepare for deployment
  - [ ] 4.3.1 Create deployment checklist
  - [ ] 4.3.2 Document rollback procedure
  - [ ] 4.3.3 Set up CloudWatch alarms
  - [ ] 4.3.4 Prepare monitoring dashboard
  - [ ] 4.3.5 Schedule deployment window

**Estimated Time:** 20 minutes

---

## Verification Checklist

Before marking this feature complete, verify:

- [ ] All tasks marked as complete
- [ ] All unit tests passing
- [ ] All property-based tests passing
- [ ] All integration tests passing
- [ ] Code coverage ≥ 100% for new code
- [ ] S3 API calls reduced by ≥ 60%
- [ ] Lambda execution time reduced by ≥ 10%
- [ ] No increase in error rate
- [ ] Documentation complete and accurate
- [ ] Code review approved
- [ ] Deployed to staging successfully
- [ ] Staging validation complete
- [ ] Ready for production deployment

---

## Notes

### Testing Environment Setup

Before starting development, ensure:
1. Virtual environment activated (`.venv` or `.ve`)
2. All requirements installed (`requirements.txt`, `requirements-test.txt`)
3. AWS credentials configured for local testing
4. Mock S3/CloudFront clients available for unit tests

### Development Workflow

1. Create feature branch: `feature/s3-api-optimization`
2. Implement tasks in order (Phase 1 → Phase 2 → Phase 3 → Phase 4)
3. Run tests after each task completion
4. Commit frequently with descriptive messages
5. Push to remote and create PR when ready

### Testing Commands

```bash
# Activate virtual environment
source .venv/bin/activate  # or source .ve/bin/activate

# Run unit tests
pytest application-infrastructure/tests/unit/ -v

# Run property-based tests
pytest application-infrastructure/tests/property/ -v

# Run integration tests
pytest application-infrastructure/tests/integration/ -v

# Run all tests with coverage
pytest application-infrastructure/tests/ --cov=application-infrastructure/functions --cov-report=html

# Run specific test file
pytest application-infrastructure/tests/unit/test_tag_validator.py -v
```

---

## Task Status Legend

- `[ ]` - Not started
- `[~]` - In progress
- `[x]` - Completed
- `[-]` - Blocked/Skipped

---

**Ready to Begin:** Yes  
**Next Task:** 1.1 Create validate_bucket_tags_from_dict() function
