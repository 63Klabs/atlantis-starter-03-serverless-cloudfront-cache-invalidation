# Requirements Document

## Introduction

This feature involves restructuring the AWS Lambda application architecture to separate individual Lambda functions into their own directories and extract common Python code into a Lambda layer. This will enable more efficient deployments where each function is packaged only with the code it needs, while shared functionality is provided through a reusable Lambda layer.

## Glossary

- **Lambda Function**: An individual AWS Lambda function (ingestor or processor)
- **Lambda Layer**: A ZIP archive containing libraries, custom runtime, or other function dependencies that can be shared across multiple Lambda functions
- **Function Directory**: A dedicated directory containing only the code and dependencies specific to one Lambda function
- **Common Code**: Shared Python modules and utilities used by multiple Lambda functions
- **Deployment Package**: The ZIP file containing function code and dependencies that gets deployed to AWS Lambda
- **Build System**: The CI/CD pipeline and build scripts that package and deploy Lambda functions
- **Test Suite**: The collection of unit, integration, and property-based tests that validate function behavior

## Requirements

### Requirement 1

**User Story:** As a developer, I want each Lambda function in its own directory, so that deployments only include the code each function needs.

#### Acceptance Criteria

1. WHEN the restructuring is complete, THE system SHALL have separate directories for each Lambda function at `application-infrastructure/functions/ingestor/` and `application-infrastructure/functions/processor/`
2. WHEN a function is deployed, THE system SHALL package only the code specific to that function
3. WHEN the directory structure is changed, THE system SHALL preserve all existing function logic and behavior
4. WHEN functions are separated, THE system SHALL maintain clear boundaries between ingestor and processor functionality
5. WHEN the restructuring is complete, THE system SHALL no longer have Lambda function code mixed in the shared src directory

### Requirement 2

**User Story:** As a developer, I want common Python code in a Lambda layer, so that shared functionality can be reused across functions without duplication.

#### Acceptance Criteria

1. WHEN common code is identified, THE system SHALL move it to a dedicated layer directory at `application-infrastructure/layers/common/`
2. WHEN the layer is created, THE system SHALL include all shared modules from the common package
3. WHEN functions use common code, THE system SHALL import it from the Lambda layer
4. WHEN the layer is deployed, THE system SHALL make it available to all Lambda functions that need it
5. WHEN common code is updated, THE system SHALL allow layer updates without redeploying individual functions

### Requirement 3

**User Story:** As a developer, I want tests to continue working locally and in CI/CD, so that code quality and reliability are maintained throughout the restructuring.

#### Acceptance Criteria

1. WHEN tests are run locally, THE system SHALL execute all unit, integration, and property tests successfully
2. WHEN the CI/CD pipeline runs, THE system SHALL find and execute all tests from their new locations
3. WHEN function code is moved, THE system SHALL update all test import paths to work with the new structure
4. WHEN tests import common code, THE system SHALL resolve imports correctly whether running locally or in CI/CD
5. WHEN the buildspec file is updated, THE system SHALL maintain all existing test execution capabilities

### Requirement 4

**User Story:** As a developer, I want the build system to package functions and layers correctly, so that deployments work seamlessly with the new structure.

#### Acceptance Criteria

1. WHEN building function packages, THE system SHALL create deployment packages containing only function-specific code
2. WHEN building the layer package, THE system SHALL create a layer ZIP containing all common code with proper Python path structure
3. WHEN deploying functions, THE system SHALL reference the common layer for shared dependencies
4. WHEN the CloudFormation template is updated, THE system SHALL define the layer resource and function layer associations
5. WHEN build scripts run, THE system SHALL handle both function and layer packaging in the correct sequence

### Requirement 5

**User Story:** As a developer, I want proper dependency management for functions and layers, so that each component has access to the libraries it needs.

#### Acceptance Criteria

1. WHEN functions have specific dependencies, THE system SHALL manage them in function-specific requirements files
2. WHEN the layer has dependencies, THE system SHALL manage them in a layer-specific requirements file
3. WHEN dependencies are installed, THE system SHALL place them in the correct location for functions or layers
4. WHEN functions are deployed, THE system SHALL have access to both function dependencies and layer dependencies
5. WHEN dependency conflicts arise, THE system SHALL resolve them by proper separation between function and layer dependencies