# Script Organization and CI/CD Guidelines

This document provides standards for organizing scripts, modules, and CI/CD processes to ensure maintainability, testability, and reusability.

## Directory Structure

### CI/CD Scripts
```
.
├── build-scripts/          # CI/CD automation scripts
│   ├── deploy.py          # Deployment automation
│   ├── test-runner.sh     # Test execution logic
│   ├── package.py         # Build and packaging
│   └── utils/             # Shared CI/CD utilities
├── tests/                 # Tests for build scripts and application
│   ├── test_deploy.py     # Tests for deployment scripts
│   ├── test_package.py    # Tests for packaging scripts
│   └── fixtures/          # Test data and fixtures
├── scripts/               # Local development and utility scripts
│   ├── setup-dev.sh       # Development environment setup
│   ├── run-local.py       # Local execution helpers
│   └── cli/               # Command-line tools
├── template.yml           # CloudFormation/SAM template
├── buildspec.yml          # CodeBuild specification
├── env.py                 # Environment configuration loader
└── .env.example           # Example environment variables
```

## When to Extract Scripts

### Move from Inline to Script File When:
- **Complexity**: More than 5-10 lines of commands
- **Logic**: Contains conditional statements, loops, or error handling
- **Reusability**: Used in multiple places or contexts
- **Testing**: Logic needs to be unit tested
- **Maintainability**: Commands are hard to read or modify inline
- **Environment-specific**: Different behavior needed across environments

### Examples of Extraction Triggers:
```yaml
# BAD: Complex inline logic in buildspec.yml
build:
  commands:
    - |
      if [ "$ENVIRONMENT" = "prod" ]; then
        aws s3 cp dist/ s3://prod-bucket --recursive
        aws cloudfront create-invalidation --distribution-id $PROD_DIST_ID --paths "/*"
      elif [ "$ENVIRONMENT" = "staging" ]; then
        aws s3 cp dist/ s3://staging-bucket --recursive
        aws cloudfront create-invalidation --distribution-id $STAGING_DIST_ID --paths "/*"
      fi
      
# GOOD: Extract to script
build:
  commands:
    - python build-scripts/deploy.py --environment $ENVIRONMENT
```

## Script Categories and Organization

### CI/CD Scripts (`build-scripts/`)
**Purpose**: Automation for build, test, and deployment processes
**Characteristics**:
- Used by CodeBuild, GitHub Actions, or other CI/CD systems
- Should work in both CI and local environments
- Must handle environment-specific configuration
- Should use SSM Parameter Store for secrets

**Examples**:
- `deploy.py` - Deployment orchestration
- `test-runner.sh` - Test execution with reporting
- `package.py` - Build and packaging logic
- `validate.py` - Configuration and resource validation

### Local Development Scripts (`scripts/`)
**Purpose**: Developer productivity and local environment management
**Characteristics**:
- Primarily for local development use
- May interact with CI/CD scripts for consistency
- Can include convenience wrappers and shortcuts
- Should support local testing of CI/CD processes

**Examples**:
- `setup-dev.sh` - Development environment initialization
- `run-local.py` - Local execution with proper environment
- `cli/` - Command-line tools and utilities

### Test Scripts (`tests/`)
**Purpose**: Validation of both application code and build scripts
**Characteristics**:
- Test build scripts as well as application logic
- Include integration tests for CI/CD processes
- Provide fixtures and test data
- Should be runnable locally and in CI

## Environment Configuration Standards

### Environment Variable Management
```python
# env.py - Environment configuration loader
import os
from pathlib import Path
import boto3

def load_env():
    """Load environment variables from .env file if present"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ.setdefault(key, value)

def get_ssm_parameter(parameter_name, decrypt=True):
    """Retrieve parameter from SSM Parameter Store"""
    ssm = boto3.client('ssm')
    response = ssm.get_parameter(Name=parameter_name, WithDecryption=decrypt)
    return response['Parameter']['Value']

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager"""
    secrets = boto3.client('secretsmanager')
    response = secrets.get_secret_value(SecretId=secret_name)
    return response['SecretString']
```

### .env File Standards
```bash
# .env.example - Template for local development
# Copy to .env and update values for local development
# DO NOT store secrets here - use SSM Parameter Store

# Environment Configuration
ENVIRONMENT=local
AWS_REGION=us-east-1
LOG_LEVEL=INFO

# Application Configuration
APP_NAME=my-application
VERSION=1.0.0

# Local Development Overrides
LOCAL_ENDPOINT=http://localhost:3000
DEBUG_MODE=true

# SSM Parameter Names (not values!)
DB_PASSWORD_PARAM=/myapp/database/password
API_KEY_PARAM=/myapp/external/api-key
```

## Secret Management Standards

### Use SSM Parameter Store for Secrets
```python
# Example: Accessing secrets in scripts
import boto3
from env import get_ssm_parameter, get_secret

# Preferred: SSM Parameter Store
db_password = get_ssm_parameter('/myapp/database/password')
api_key = get_ssm_parameter('/myapp/external/api-key')

# For complex secrets: Secrets Manager
db_config = json.loads(get_secret('myapp/database/config'))
```

### Environment Variable Categories
- **Configuration**: Non-sensitive settings (environment name, regions, etc.)
- **Parameters**: References to SSM parameters (parameter names, not values)
- **Secrets**: NEVER in environment variables - always from SSM/Secrets Manager

## Script Development Best Practices

### Error Handling and Logging
```python
# build-scripts/deploy.py
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Script logic here
        logger.info("Deployment started")
        # ... deployment steps ...
        logger.info("Deployment completed successfully")
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Local Testing Support
```bash
#!/bin/bash
# build-scripts/test-runner.sh

set -e  # Exit on any error

# Support both local and CI execution
if [ -f ".env" ]; then
    echo "Loading local environment from .env"
    python env.py
fi

# Determine test scope
TEST_SCOPE=${1:-all}

case $TEST_SCOPE in
    "unit")
        echo "Running unit tests..."
        python -m pytest tests/unit/
        ;;
    "integration")
        echo "Running integration tests..."
        python -m pytest tests/integration/
        ;;
    "all")
        echo "Running all tests..."
        python -m pytest tests/
        ;;
    *)
        echo "Usage: $0 [unit|integration|all]"
        exit 1
        ;;
esac
```

### Parameterization and Flexibility
```python
# build-scripts/package.py
import argparse
import os
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description='Package application')
    parser.add_argument('--environment', required=True, 
                       choices=['local', 'dev', 'staging', 'prod'])
    parser.add_argument('--output-dir', default='dist')
    parser.add_argument('--skip-tests', action='store_true')
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Environment-specific logic
    if args.environment == 'prod':
        # Production-specific packaging
        pass
    elif args.environment in ['dev', 'staging']:
        # Non-production packaging
        pass
```

## Testing Standards for Scripts

### Test Organization
```python
# tests/test_deploy.py
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from build_scripts.deploy import deploy_application

class TestDeployment:
    def test_deploy_to_staging(self):
        """Test deployment to staging environment"""
        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            
            result = deploy_application('staging', 'test-bucket')
            
            assert result.success
            mock_s3.upload_file.assert_called()

    def test_deploy_with_invalid_environment(self):
        """Test deployment fails with invalid environment"""
        with pytest.raises(ValueError):
            deploy_application('invalid-env', 'test-bucket')
```

### Integration Testing
```python
# tests/integration/test_ci_pipeline.py
import subprocess
import tempfile
from pathlib import Path

def test_full_build_pipeline():
    """Test complete build pipeline locally"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up test environment
        test_env = {
            'ENVIRONMENT': 'test',
            'OUTPUT_DIR': temp_dir
        }
        
        # Run build script
        result = subprocess.run(
            ['python', 'build-scripts/package.py', '--environment', 'test'],
            env=test_env,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert Path(temp_dir).exists()
```

## AI Assistant Guidelines

### Decision Framework for Script Extraction
When generating code, consider these factors:

1. **Complexity Assessment**:
   - Count lines of shell commands or logic
   - Identify conditional statements, loops, error handling
   - Evaluate readability and maintainability

2. **Reusability Analysis**:
   - Will this logic be used elsewhere?
   - Could it benefit from parameterization?
   - Is it environment-specific?

3. **Testing Requirements**:
   - Does the logic need unit testing?
   - Are there edge cases to validate?
   - Would mocking be beneficial?

4. **Maintenance Considerations**:
   - Will this logic change frequently?
   - Is it complex enough to benefit from version control?
   - Would documentation be helpful?

### Script Generation Templates

#### Python CI/CD Script Template
```python
#!/usr/bin/env python3
"""
Script description and purpose
Supports cross-platform execution (Linux, Mac, Windows)
"""
import argparse
import logging
import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from env import load_env, get_ssm_parameter

def setup_console_logging(level=logging.INFO):
    """Configure informative console logging"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments with required help"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--profile', 
                       help='AWS profile to use (required for local development)')
    parser.add_argument('--environment', required=True,
                       choices=['local', 'dev', 'staging', 'prod'],
                       help='Target environment')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    return parser.parse_args()

def setup_aws_profile(profile):
    """Setup AWS profile for cross-platform compatibility"""
    if profile:
        os.environ['AWS_PROFILE'] = profile
        print(f"Using AWS profile: {profile}")
    elif not os.environ.get('AWS_PROFILE'):
        print("Using default AWS profile (CI/CD mode)")

def main():
    """Main script logic"""
    args = parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_console_logging(log_level)
    
    # Load environment
    load_env()  # Load .env if present
    setup_aws_profile(args.profile)
    
    try:
        logger.info("Starting script execution...")
        logger.info(f"Target environment: {args.environment}")
        
        # Script logic here
        
        logger.info("Script completed successfully!")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        if args.verbose:
            logger.exception("Full error details:")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

#### Bash CI/CD Script Template
```bash
#!/bin/bash
"""
Script description and purpose
Optimized for AWS CLI operations and Linux commands
"""

set -e  # Exit on any error

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Description of what this script does

OPTIONS:
    -e, --environment ENV    Target environment (local|dev|staging|prod)
    -p, --profile PROFILE    AWS profile to use (required for local development)
    -v, --verbose           Enable verbose output
    -h, --help              Show this help message

Examples:
    $0 --environment dev --profile myprofile
    $0 --environment prod  # Uses default profile (CI/CD)
EOF
}

# Default values
ENVIRONMENT=""
AWS_PROFILE=""
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$ENVIRONMENT" ]; then
    echo "Error: --environment is required"
    show_help
    exit 1
fi

# Setup AWS profile
PROFILE_FLAG=""
if [ -n "$AWS_PROFILE" ]; then
    PROFILE_FLAG="--profile $AWS_PROFILE"
    echo "Using AWS profile: $AWS_PROFILE"
else
    echo "Using default AWS profile (CI/CD mode)"
fi

# Verbose logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

verbose_log() {
    if [ "$VERBOSE" = true ]; then
        log "$1"
    fi
}

# Main script logic
main() {
    log "Starting script execution..."
    log "Target environment: $ENVIRONMENT"
    
    # Script logic here
    # Example AWS CLI usage:
    # aws s3 sync ./dist/ s3://$BUCKET_NAME $PROFILE_FLAG
    
    log "Script completed successfully!"
}

# Execute main function
main "$@"
```

#### Interactive Developer Script Template
```python
#!/usr/bin/env python3
"""
Interactive developer utility script
Cross-platform compatible (Linux, Mac, Windows)
"""
import argparse
import logging
import sys
import os
from pathlib import Path

def setup_interactive_logging():
    """Setup user-friendly logging for interactive use"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',  # Simplified for interactive use
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)

def confirm_action(message):
    """Interactive confirmation prompt"""
    while True:
        response = input(f"{message} (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' or 'n'")

def select_from_list(items, prompt="Select an option"):
    """Interactive list selection"""
    print(f"\n{prompt}:")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item}")
    
    while True:
        try:
            choice = int(input(f"Enter choice (1-{len(items)}): "))
            if 1 <= choice <= len(items):
                return items[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(items)}")
        except ValueError:
            print("Please enter a valid number")

def main():
    """Main interactive script logic"""
    logger = setup_interactive_logging()
    
    logger.info("=== Interactive Developer Tool ===")
    
    # Interactive logic here
    
    logger.info("Operation completed!")

if __name__ == "__main__":
    main()
```

## Platform and Technology Standards

### CI/CD Platforms
- **Primary**: AWS CodeBuild for deployment and CI/CD
- **Secondary**: GitHub Actions for basic operations (zip, copy to S3)
- **Focus**: CodeBuild-optimized scripts with GitHub Actions compatibility

### Language Selection Guidelines

#### Bash Scripts
**Use for**:
- Linux/CLI command sequences
- AWS CLI operations
- File system operations
- Simple automation workflows

```bash
#!/bin/bash
# Example: AWS CLI deployment script
set -e

PROFILE_FLAG=""
if [ "$AWS_PROFILE" != "" ]; then
    PROFILE_FLAG="--profile $AWS_PROFILE"
fi

aws s3 sync ./dist/ s3://$BUCKET_NAME $PROFILE_FLAG
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*" $PROFILE_FLAG
```

#### Python Scripts
**Use for**:
- AWS SDK operations (boto3)
- Complex logic and variable manipulation
- Interactive developer tools
- Cross-platform compatibility (Linux, Mac, Windows)
- Heavy data processing

```python
#!/usr/bin/env python3
"""
Cross-platform deployment script using AWS SDK
"""
import argparse
import boto3
from pathlib import Path

def setup_aws_session(profile=None):
    """Setup AWS session with optional profile"""
    if profile:
        return boto3.Session(profile_name=profile)
    return boto3.Session()  # Use default profile in CI/CD
```

#### Node.js Scripts
**Use for**:
- Testing Node.js Lambda functions
- Node.js-specific tooling and utilities
- Limited to Node.js ecosystem needs

### Testing Framework Standards
- **Python**: pytest (Kiro's preferred framework)
- **Node.js**: Jest or Mocha (based on existing project setup)
- **Bash**: bats-core for shell script testing
- **Principle**: Use existing framework if present, otherwise default to Kiro preferences

### Infrastructure as Code (IaC) Standards

#### Primary: CloudFormation with SAM
- **Use for**: Main application deployment
- **Templates**: SAM-based CloudFormation templates
- **Deployment**: CodeBuild with SAM CLI

#### Secondary: CDK for Event-Driven Services
- **Use for**: Event-driven infrastructure (S3 bucket creation, pipeline triggers)
- **Deployment**: CDK scripts deployed as part of CloudFormation-deployed services
- **Pattern**: CDK services should be triggered by events, not direct deployment

```python
# Example: CDK script for event-driven infrastructure
from aws_cdk import core, s3, events

class EventDrivenStack(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Event-driven S3 bucket creation
        bucket = s3.Bucket(self, "EventBucket")
```

### Security and Maintenance Standards
- **Package Updates**: Keep all dependencies current
- **Secrets**: SSM Parameter Store and Secrets Manager only
- **Profiles**: Require `--profile` flag for local AWS CLI operations
- **Default Behavior**: Use default profile in CI/CD environments

### Cross-Platform Development Requirements

#### Script Compatibility
All developer scripts must work on:
- Linux (native and WSL)
- macOS
- Windows (with WSL or native Python)

#### AWS Profile Management
```python
def setup_aws_profile(args):
    """Handle AWS profile for cross-platform compatibility"""
    if hasattr(args, 'profile') and args.profile:
        os.environ['AWS_PROFILE'] = args.profile
        print(f"Using AWS profile: {args.profile}")
    elif not os.environ.get('AWS_PROFILE'):
        print("Using default AWS profile (recommended for CI/CD)")
```

#### Help and Documentation Standards
```python
def parse_args():
    """Standard argument parsing with required help"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--profile', 
                       help='AWS profile to use (required for local development)')
    parser.add_argument('--environment', required=True,
                       choices=['local', 'dev', 'staging', 'prod'],
                       help='Target environment for deployment')
    return parser.parse_args()
```

### Console Output Standards
All scripts should provide informative console output:

```python
import logging
import sys

def setup_console_logging():
    """Setup informative console logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

# Usage in scripts
logger = setup_console_logging()
logger.info("Starting deployment process...")
logger.info(f"Target environment: {environment}")
logger.info("Deployment completed successfully!")
```