# Implementation Plan

- [x] 1. Create new directory structure for functions and layers
  - Create `application-infrastructure/functions/` directory
  - Create `application-infrastructure/functions/ingestor/` directory
  - Create `application-infrastructure/functions/processor/` directory
  - Create `application-infrastructure/layers/` directory
  - Create `application-infrastructure/layers/common/` directory
  - Create `application-infrastructure/layers/common/python/` directory
  - Create `application-infrastructure/layers/common/python/common/` directory
  - _Requirements: 1.1, 2.1_

- [x] 2. Move common code to Lambda layer
- [x] 2.1 Copy common modules to layer structure
  - Copy all files from `src/common/` to `layers/common/python/common/`
  - Preserve file contents and structure
  - Create `layers/common/requirements.txt` for layer dependencies
  - _Requirements: 2.1, 2.2_

- [x] 2.2 Write property test for layer structure
  - **Property 2: Layer dependency resolution**
  - **Validates: Requirements 2.3, 3.3, 3.4**

- [x] 3. Move ingestor function code
- [x] 3.1 Copy ingestor modules to function directory
  - Copy all files from `src/ingestor/` to `functions/ingestor/`
  - Create `functions/ingestor/requirements.txt` for function-specific dependencies
  - Update import statements to use layer imports instead of local common imports
  - _Requirements: 1.1, 1.4_

- [x] 3.2 Write property test for function deployment isolation
  - **Property 1: Function deployment isolation**
  - **Validates: Requirements 1.2, 4.1**

- [x] 4. Move processor function code
- [x] 4.1 Copy processor modules to function directory
  - Copy all files from `src/processor/` to `functions/processor/`
  - Create `functions/processor/requirements.txt` for function-specific dependencies
  - Update import statements to use layer imports instead of local common imports
  - _Requirements: 1.1, 1.4_

- [x] 4.2 Write property test for architectural boundary enforcement
  - **Property 4: Architectural boundary enforcement**
  - **Validates: Requirements 1.4**

- [x] 5. Update CloudFormation template
- [x] 5.1 Add Lambda layer resource definition
  - Add `CommonLayer` resource to template.yml
  - Configure layer properties including name, content location, and compatible runtimes
  - _Requirements: 2.4, 4.4_

- [x] 5.2 Update Lambda function resources
  - Update `IngestorFunction` CodeUri to point to `functions/ingestor/`
  - Update `ProcessorFunction` CodeUri to point to `functions/processor/`
  - Add layer references to both function resources
  - _Requirements: 4.3, 4.4_

- [-] 6. Update build system
- [x] 6.1 Update buildspec.yml for new structure
  - Update dependency installation paths for functions and layer
  - Update test execution paths to work with new structure
  - Add layer packaging commands to build process
  - _Requirements: 3.2, 4.5, 5.3_

- [-] 6.2 Write property test for build and test execution consistency
  - **Property 5: Build and test execution consistency**
  - **Validates: Requirements 3.1, 3.2, 4.5, 5.3**

- [ ] 7. Update test imports and paths
- [ ] 7.1 Update test import statements
  - Update all test files to import from new function locations
  - Update test imports to use layer structure for common code
  - Ensure test discovery works with new directory structure
  - _Requirements: 3.3, 3.4_

- [ ] 7.2 Write property test for functional behavior preservation
  - **Property 3: Functional behavior preservation**
  - **Validates: Requirements 1.3, 3.5**

- [ ] 8. Create dependency management files
- [ ] 8.1 Create function-specific requirements files
  - Analyze current dependencies and split between functions and layer
  - Create `functions/ingestor/requirements.txt` with ingestor-specific dependencies
  - Create `functions/processor/requirements.txt` with processor-specific dependencies
  - Create `layers/common/requirements.txt` with shared dependencies
  - _Requirements: 5.1, 5.2_

- [ ] 9. Validate new structure
- [ ] 9.1 Run tests with new structure
  - Execute unit tests to ensure they pass with new imports
  - Execute property-based tests to validate correctness properties
  - Execute integration tests to ensure end-to-end functionality works
  - _Requirements: 3.1, 3.4_

- [ ] 9.2 Test build process
  - Run buildspec commands locally to ensure build works
  - Verify function packages contain only function-specific code
  - Verify layer package contains common code with correct Python path structure
  - _Requirements: 4.1, 4.2, 4.5_

- [ ] 10. Remove old source structure
- [ ] 10.1 Clean up old directories
  - Remove `src/ingestor/` directory and contents
  - Remove `src/processor/` directory and contents  
  - Remove `src/common/` directory and contents
  - Remove empty `src/` directory
  - _Requirements: 1.5_

- [ ] 11. Final validation and cleanup
- [ ] 11.1 End-to-end validation
  - Run complete test suite to ensure all tests pass
  - Validate CloudFormation template syntax
  - Test deployment process with new structure
  - Verify layer and function associations work correctly
  - _Requirements: 2.4, 3.1, 4.3_

- [ ] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.