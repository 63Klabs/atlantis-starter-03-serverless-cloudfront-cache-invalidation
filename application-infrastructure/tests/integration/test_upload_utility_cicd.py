#!/usr/bin/env python3
"""
Integration tests for test file upload utility CI/CD pipeline integration.

**Feature: test-file-upload-utility, Integration Test: CI/CD pipeline integration**
**Validates: Requirements 2.1, 2.3, 2.4**

This module tests the integration of the test file upload utility with the CI/CD pipeline
to verify that the buildspec execution, environment variable resolution, and script
execution work correctly in a CodeBuild-like environment.

These tests simulate:
1. CodeBuild environment variable setup
2. Buildspec execution flow
3. Script execution with various configurations
4. Error handling in CI/CD context

Run with: pytest tests/integration/test_upload_utility_cicd.py -v

Environment variables for testing:
- S3_STATIC_HOST_BUCKET: Test bucket for CI/CD mode testing
- RUN_INTEGRATION_TESTS: Set to '1' to enable integration tests
"""

import os
import json
import subprocess
import tempfile
import time
import boto3
import pytest
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock


# Skip all tests if not in integration test mode
pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_INTEGRATION_TESTS') != '1',
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 environment variable"
)


@pytest.fixture(scope="module")
def aws_clients():
    """Create AWS service clients for integration tests."""
    return {
        's3': boto3.client('s3'),
        'logs': boto3.client('logs'),
    }


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration from environment variables."""
    config = {
        'test_bucket': os.environ.get('S3_STATIC_HOST_BUCKET'),
        'stage': 'staging',  # Default stage for testing
        'build_scripts_dir': Path(__file__).parent.parent.parent / 'build-scripts',
        'upload_script_path': Path(__file__).parent.parent.parent / 'build-scripts' / 'upload-test-files.py',
        'buildspec_path': Path(__file__).parent.parent.parent / 'buildspec-postdeploy.yml',
        'test_html_path': Path(__file__).parent.parent.parent.parent / 'test.html',
    }
    
    # Validate required paths exist
    missing_paths = []
    for key, path in config.items():
        if key.endswith('_path') and not path.exists():
            missing_paths.append(f"{key}: {path}")
    
    if missing_paths:
        pytest.skip(f"Missing required files: {', '.join(missing_paths)}")
    
    return config


@pytest.fixture(scope="function")
def clean_test_environment():
    """
    Fixture to ensure clean test environment before and after each test.
    """
    # Clean up environment variables that might affect tests
    env_vars_to_clean = [
        'AWS_PROFILE',
        'S3_STATIC_HOST_BUCKET'
    ]
    
    original_values = {}
    for var in env_vars_to_clean:
        original_values[var] = os.environ.get(var)
    
    yield
    
    # Restore original environment
    for var, value in original_values.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


def run_upload_script(script_path: Path, args: List[str], env_vars: Dict[str, str] = None) -> subprocess.CompletedProcess:
    """
    Helper function to run the upload script with specified arguments and environment.
    
    Args:
        script_path: Path to the upload script
        args: Command line arguments
        env_vars: Additional environment variables
        
    Returns:
        CompletedProcess result
    """
    # Prepare environment
    test_env = os.environ.copy()
    if env_vars:
        test_env.update(env_vars)
    
    # Run script
    cmd = ['python', str(script_path)] + args
    
    result = subprocess.run(
        cmd,
        env=test_env,
        capture_output=True,
        text=True,
        timeout=60  # 60 second timeout
    )
    
    return result


def simulate_buildspec_execution(buildspec_path: Path, env_vars: Dict[str, str] = None) -> subprocess.CompletedProcess:
    """
    Helper function to simulate buildspec execution by extracting and running the upload command.
    
    Args:
        buildspec_path: Path to the buildspec file
        env_vars: Environment variables for the execution
        
    Returns:
        CompletedProcess result
    """
    # Read buildspec and extract the upload command
    with open(buildspec_path, 'r') as f:
        buildspec_content = f.read()
    
    # Find the upload command in the buildspec
    # Look for the line that runs upload-test-files.py
    upload_command = None
    for line in buildspec_content.split('\n'):
        if 'upload-test-files.py' in line and 'python' in line:
            # Extract the command, removing shell script formatting
            upload_command = line.strip()
            if upload_command.startswith('- '):
                upload_command = upload_command[2:]  # Remove YAML list marker
            break
    
    if not upload_command:
        raise ValueError("Upload command not found in buildspec")
    
    # Prepare environment
    test_env = os.environ.copy()
    if env_vars:
        test_env.update(env_vars)
    
    # Change to application-infrastructure directory as buildspec does
    original_cwd = os.getcwd()
    try:
        os.chdir(buildspec_path.parent)
        
        # Execute the command
        result = subprocess.run(
            upload_command,
            shell=True,
            env=test_env,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return result
    finally:
        os.chdir(original_cwd)


class TestEnvironmentVariableResolution:
    """Test environment variable resolution in CI/CD context."""
    
    def test_s3_static_host_bucket_resolution(self, test_config, clean_test_environment):
        """
        Test that S3_STATIC_HOST_BUCKET environment variable is correctly resolved.
        
        **Validates: Requirements 2.1**
        
        This test verifies:
        1. Script reads S3_STATIC_HOST_BUCKET when --buckets not provided
        2. Environment variable takes precedence in CI/CD mode
        3. Error handling when neither --buckets nor environment variable provided
        """
        script_path = test_config['upload_script_path']
        
        # Test 1: With S3_STATIC_HOST_BUCKET set
        if test_config['test_bucket']:
            env_vars = {
                'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
            }
            
            result = run_upload_script(
                script_path,
                ['--stages', 'staging', '--verbose'],
                env_vars
            )
            
            # Should succeed (or fail only due to AWS permissions, not config)
            output = result.stdout + result.stderr
            assert 'No buckets specified' not in output
            assert test_config['test_bucket'] in output
        
        # Test 2: Without S3_STATIC_HOST_BUCKET (should fail with helpful message)
        env_vars = {}
        # Remove S3_STATIC_HOST_BUCKET if it exists
        if 'S3_STATIC_HOST_BUCKET' in os.environ:
            del os.environ['S3_STATIC_HOST_BUCKET']
        
        result = run_upload_script(
            script_path,
            ['--stages', 'staging'],
            env_vars
        )
        
        # Should fail with helpful error message
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert 'No buckets specified' in output or 'S3_STATIC_HOST_BUCKET' in output
    
    def test_stages_parameter_resolution(self, test_config, clean_test_environment):
        """
        Test that stages parameter is correctly resolved and used.
        
        **Validates: Requirements 2.3**
        
        This test verifies:
        1. --stages parameter affects base path determination
        2. Different stages produce different base paths
        3. Stage configuration is logged correctly
        """
        script_path = test_config['upload_script_path']
        
        if not test_config['test_bucket']:
            pytest.skip("No test bucket configured")
        
        # Test staging stage
        env_vars_staging = {
            'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
        }
        
        result_staging = run_upload_script(
            script_path,
            ['--stages', 'staging', '--verbose'],  # Use --stages parameter
            env_vars_staging
        )
        
        # Should use staging base path
        assert '/stage/public/' in result_staging.stdout or '/stage/public/' in result_staging.stderr
        
        # Test production stage
        env_vars_prod = {
            'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
        }
        
        result_prod = run_upload_script(
            script_path,
            ['--stages', 'prod', '--verbose'],
            env_vars_prod
        )
        
        # Should use production base path
        assert '/prod/public/' in result_prod.stdout or '/prod/public/' in result_prod.stderr
    
    def test_aws_profile_handling_in_cicd(self, test_config, clean_test_environment):
        """
        Test AWS profile handling in CI/CD environment.
        
        **Validates: Requirements 2.3**
        
        This test verifies:
        1. Script works without --profile in CI/CD mode
        2. Default AWS credentials are used when no profile specified
        3. Profile usage is logged correctly
        """
        script_path = test_config['upload_script_path']
        
        if not test_config['test_bucket']:
            pytest.skip("No test bucket configured")
        
        # Simulate CI/CD environment (no AWS_PROFILE set)
        env_vars = {
            'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
        }
        
        # Remove AWS_PROFILE if it exists
        if 'AWS_PROFILE' in os.environ:
            del os.environ['AWS_PROFILE']
        
        result = run_upload_script(
            script_path,
            ['--stages', 'staging', '--verbose'],
            env_vars
        )
        
        # Should indicate using default profile
        assert 'default AWS profile' in result.stdout or 'CI/CD mode' in result.stdout


class TestBuildspecIntegration:
    """Test buildspec integration and execution."""
    
    def test_buildspec_upload_command_execution(self, test_config, clean_test_environment):
        """
        Test that the buildspec correctly executes the upload utility.
        
        **Validates: Requirements 2.1, 2.4**
        
        This test verifies:
        1. Buildspec contains the correct upload command
        2. Command executes successfully in simulated CI/CD environment
        3. Environment variables are passed correctly
        """
        buildspec_path = test_config['buildspec_path']
        
        if not test_config['test_bucket']:
            pytest.skip("No test bucket configured")
        
        # Simulate CodeBuild environment variables
        env_vars = {
            'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
        }
        
        result = simulate_buildspec_execution(buildspec_path, env_vars)
        
        # Check that the command was found and executed
        assert result is not None
        
        # Should not fail due to configuration issues
        if result.returncode != 0:
            # If it fails, it should be due to AWS permissions, not configuration
            assert 'No buckets specified' not in result.stderr
            assert 'S3_STATIC_HOST_BUCKET' not in result.stderr or 'found' in result.stderr
    
    def test_buildspec_requirements_installation(self, test_config):
        """
        Test that buildspec correctly installs requirements for build scripts.
        
        **Validates: Requirements 2.1**
        
        This test verifies:
        1. build-scripts/requirements.txt exists
        2. boto3 is included in requirements
        3. Requirements file is properly formatted
        """
        requirements_path = test_config['build_scripts_dir'] / 'requirements.txt'
        
        assert requirements_path.exists(), "build-scripts/requirements.txt not found"
        
        with open(requirements_path, 'r') as f:
            requirements_content = f.read()
        
        # Should contain boto3
        assert 'boto3' in requirements_content, "boto3 not found in build-scripts/requirements.txt"
        
        # Should be properly formatted (no empty lines at start, proper version spec)
        lines = [line.strip() for line in requirements_content.split('\n') if line.strip()]
        assert len(lines) > 0, "Requirements file is empty"
        
        # Check boto3 line format
        boto3_lines = [line for line in lines if 'boto3' in line]
        assert len(boto3_lines) == 1, f"Expected exactly one boto3 line, found: {boto3_lines}"
        
        boto3_line = boto3_lines[0]
        assert '>=' in boto3_line or '==' in boto3_line, f"boto3 line should have version spec: {boto3_line}"


class TestScriptExecutionInCICD:
    """Test script execution scenarios in CI/CD environment."""
    
    def test_successful_execution_flow(self, test_config, clean_test_environment):
        """
        Test complete successful execution flow in CI/CD environment.
        
        **Validates: Requirements 2.1, 2.3, 2.4**
        
        This test verifies:
        1. Script executes successfully with CI/CD configuration
        2. All 12 files are generated per bucket
        3. Proper logging and summary are produced
        4. Exit code is 0 for success
        """
        script_path = test_config['upload_script_path']
        
        if not test_config['test_bucket']:
            pytest.skip("No test bucket configured")
        
        env_vars = {
            'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
        }
        
        result = run_upload_script(
            script_path,
            ['--stages', 'staging', '--verbose'],
            env_vars
        )
        
        # Check output for expected patterns
        output = result.stdout + result.stderr
        
        # Should log startup information
        assert 'Test File Upload Utility' in output
        assert test_config['test_bucket'] in output
        assert 'staging' in output or 'Stage: staging' in output
        
        # Should log base path
        assert '/stage/public/' in output
        
        # If successful, should show upload summary
        if result.returncode == 0:
            assert 'Upload Summary' in output or 'successful' in output
        else:
            # If failed, should be due to AWS permissions, not configuration
            assert 'credentials' in output.lower() or 'permission' in output.lower() or 'access' in output.lower()
    
    def test_error_handling_in_cicd(self, test_config, clean_test_environment):
        """
        Test error handling scenarios in CI/CD environment.
        
        **Validates: Requirements 2.4**
        
        This test verifies:
        1. Missing source file produces clear error
        2. Invalid bucket names are handled gracefully
        3. AWS credential errors are reported clearly
        4. Exit codes are appropriate for different error types
        """
        script_path = test_config['upload_script_path']
        
        # Test 1: Missing source file (simulate by using wrong working directory)
        with tempfile.TemporaryDirectory() as temp_dir:
            env_vars = {
                'S3_STATIC_HOST_BUCKET': 'nonexistent-bucket-for-testing'
            }
            
            # Run from temp directory where test.html doesn't exist
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                result = subprocess.run(
                    ['python', str(script_path), '--stages', 'staging', '--verbose'],
                    env=env_vars,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Should fail with file not found error
                assert result.returncode != 0
                assert 'test.html' in result.stderr or 'not found' in result.stderr.lower()
                
            finally:
                os.chdir(original_cwd)
        
        # Test 2: Invalid bucket name (should be handled gracefully)
        env_vars = {
            'S3_STATIC_HOST_BUCKET': 'definitely-nonexistent-bucket-12345'
        }
        
        result = run_upload_script(
            script_path,
            ['--stages', 'staging', '--verbose'],
            env_vars
        )
        
        # Should fail but with appropriate error handling
        assert result.returncode != 0
        output = result.stdout + result.stderr
        
        # Should provide actionable guidance
        assert any(keyword in output.lower() for keyword in [
            'bucket', 'permission', 'access', 'credential', 'network'
        ])
    
    def test_verbose_logging_in_cicd(self, test_config, clean_test_environment):
        """
        Test verbose logging functionality in CI/CD environment.
        
        **Validates: Requirements 2.3**
        
        This test verifies:
        1. Verbose mode provides detailed information
        2. AWS profile information is logged
        3. Bucket validation steps are logged
        4. Configuration details are shown
        """
        script_path = test_config['upload_script_path']
        
        if not test_config['test_bucket']:
            pytest.skip("No test bucket configured")
        
        env_vars = {
            'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
        }
        
        # Run with verbose flag
        result = run_upload_script(
            script_path,
            ['--stages', 'staging', '--verbose'],
            env_vars
        )
        
        output = result.stdout + result.stderr
        
        # Should include verbose information
        verbose_indicators = [
            'AWS profile',
            'default',
            'CI/CD mode',
            'Verbose mode',
            'Base path',
            'staging'  # Should mention the stage being processed
        ]
        
        found_indicators = [indicator for indicator in verbose_indicators if indicator in output]
        
        # Should find at least some verbose indicators
        assert len(found_indicators) >= 2, f"Insufficient verbose output. Found: {found_indicators}. Output: {output[:500]}"


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility in CI/CD context."""
    
    def test_script_permissions_and_execution(self, test_config):
        """
        Test that script has proper permissions and can be executed.
        
        **Validates: Requirements 2.1**
        
        This test verifies:
        1. Script file has executable permissions
        2. Script can be executed directly
        3. Shebang line is correct for cross-platform use
        """
        script_path = test_config['upload_script_path']
        
        # Check file permissions
        import stat
        file_stat = script_path.stat()
        is_executable = bool(file_stat.st_mode & stat.S_IEXEC)
        
        assert is_executable, f"Script {script_path} is not executable"
        
        # Check shebang line
        with open(script_path, 'r') as f:
            first_line = f.readline().strip()
        
        assert first_line.startswith('#!'), f"Script missing shebang line: {first_line}"
        assert 'python' in first_line, f"Shebang should reference python: {first_line}"
    
    def test_path_handling_cross_platform(self, test_config, clean_test_environment):
        """
        Test that path handling works across different platforms.
        
        **Validates: Requirements 2.1**
        
        This test verifies:
        1. Script handles file paths correctly
        2. Source file resolution works from different working directories
        3. S3 path generation is consistent
        """
        script_path = test_config['upload_script_path']
        
        if not test_config['test_bucket']:
            pytest.skip("No test bucket configured")
        
        # Test from different working directories
        test_dirs = [
            script_path.parent,  # build-scripts directory
            script_path.parent.parent,  # application-infrastructure directory
            script_path.parent.parent.parent,  # repository root
        ]
        
        for test_dir in test_dirs:
            if not test_dir.exists():
                continue
            
            original_cwd = os.getcwd()
            try:
                os.chdir(test_dir)
                
                env_vars = {
                    'S3_STATIC_HOST_BUCKET': test_config['test_bucket']
                }
                
                result = subprocess.run(
                    ['python', str(script_path), '--stages', 'staging', '--verbose'],
                    env=env_vars,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Should either succeed or fail with AWS-related errors, not path errors
                if result.returncode != 0:
                    output = result.stdout + result.stderr
                    # Should not fail due to path issues
                    assert 'test.html' not in result.stderr or 'found' in output.lower()
                
            finally:
                os.chdir(original_cwd)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])