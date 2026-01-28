#!/usr/bin/env python3
"""
Backward compatibility validation tests for the enhanced test file upload utility.

This module validates that existing command-line usage patterns continue to work:
- Existing command-line usage patterns continue to work
- CI/CD integration remains functional with enhanced file count
- buildspec-postdeploy.yml integration works correctly

**Validates: Requirements 3.1, 3.2, 3.3**

Run with: pytest tests/integration/test_backward_compatibility_enhanced.py -v
"""
import pytest
import os
import sys
import tempfile
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple
import boto3
from unittest.mock import patch, MagicMock, call

# Add the build-scripts directory to the path
build_scripts_path = Path(__file__).parent.parent.parent / "build-scripts"
sys.path.insert(0, str(build_scripts_path))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("upload_test_files", build_scripts_path / "upload-test-files.py")
    upload_test_files = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upload_test_files)
    
    main = upload_test_files.main
    ArgumentParser = upload_test_files.ArgumentParser
    EnvironmentManager = upload_test_files.EnvironmentManager
    
except ImportError as e:
    print(f"Import error: {e}")
    raise


class TestBackwardCompatibilityEnhanced:
    """Backward compatibility validation tests for the enhanced upload utility"""
    
    def test_existing_command_line_patterns(self):
        """
        Test that existing command-line usage patterns continue to work
        
        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Backward compatibility test</body></html>')
            test_html_path = f.name
        
        try:
            # Test various command-line patterns that should continue to work
            test_cases = [
                # Basic usage with single bucket
                ["--buckets", "test-bucket-1"],
                
                # Multiple buckets
                ["--buckets", "test-bucket-1,test-bucket-2"],
                
                # With stages
                ["--buckets", "test-bucket-1", "--stages", "dev,staging,prod"],
                
                # With profile
                ["--buckets", "test-bucket-1", "--profile", "test-profile"],
                
                # With verbose
                ["--buckets", "test-bucket-1", "--verbose"],
                
                # Combined options
                ["--buckets", "test-bucket-1,test-bucket-2", "--stages", "dev,prod", "--verbose"],
            ]
            
            for test_args in test_cases:
                with patch('boto3.Session') as mock_session:
                    mock_s3_client = MagicMock()
                    mock_session.return_value.client.return_value = mock_s3_client
                    
                    # Mock successful S3 operations
                    mock_s3_client.head_bucket.return_value = {}
                    mock_s3_client.put_object.return_value = {}
                    
                    # Mock the source file path to use our temporary file
                    with patch.object(Path, 'exists', return_value=True):
                        with patch('builtins.open', mock_open_with_content('<html><body>Test</body></html>')):
                            with patch('sys.argv', ['upload-test-files.py'] + test_args):
                                with patch('sys.exit') as mock_exit:
                                    try:
                                        main()
                                        # If main() completes without exception, it should exit with 0
                                        mock_exit.assert_called_with(0)
                                    except SystemExit as e:
                                        # Check that it's a successful exit
                                        assert e.code == 0, f"Command failed with args {test_args}: exit code {e.code}"
                    
                    # Verify S3 operations were called (indicating the enhanced utility ran)
                    assert mock_s3_client.head_bucket.called, f"head_bucket should be called for args {test_args}"
                    assert mock_s3_client.put_object.called, f"put_object should be called for args {test_args}"
                    
                    # Verify enhanced file count (62 files per bucket per stage)
                    buckets = test_args[test_args.index("--buckets") + 1].split(',')
                    stages = ["prod"]  # default
                    if "--stages" in test_args:
                        stages = test_args[test_args.index("--stages") + 1].split(',')
                    
                    expected_uploads = len(buckets) * len(stages) * 62
                    actual_uploads = mock_s3_client.put_object.call_count
                    
                    assert actual_uploads == expected_uploads, \
                        f"Args {test_args}: expected {expected_uploads} uploads, got {actual_uploads}"
                
                print(f"✅ Command-line pattern validated: {' '.join(test_args)}")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_environment_variable_compatibility(self):
        """
        Test that environment variable usage continues to work
        
        **Validates: Requirements 3.1**
        """
        # Test with S3_STATIC_HOST_BUCKET environment variable
        with patch.dict(os.environ, {'S3_STATIC_HOST_BUCKET': 'env-test-bucket'}):
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Mock the source file path
                with patch.object(Path, 'exists', return_value=True):
                    with patch('builtins.open', mock_open_with_content('<html><body>Test</body></html>')):
                        with patch('sys.argv', ['upload-test-files.py']):  # No --buckets argument
                            with patch('sys.exit') as mock_exit:
                                try:
                                    main()
                                    mock_exit.assert_called_with(0)
                                except SystemExit as e:
                                    assert e.code == 0, f"Environment variable usage failed: exit code {e.code}"
                
                # Verify the environment bucket was used
                mock_s3_client.head_bucket.assert_called_with(Bucket='env-test-bucket')
                
                # Verify enhanced file count (62 files for 1 bucket, 1 stage)
                assert mock_s3_client.put_object.call_count == 62, \
                    f"Expected 62 uploads with env variable, got {mock_s3_client.put_object.call_count}"
        
        print("✅ Environment variable compatibility validated")
    
    def test_argument_parser_compatibility(self):
        """
        Test that argument parser maintains backward compatibility
        
        **Validates: Requirements 3.1**
        """
        parser = ArgumentParser()
        
        # Test that all existing arguments are still supported
        test_cases = [
            # Basic arguments
            ['--buckets', 'test-bucket'],
            ['--stages', 'dev,staging,prod'],
            ['--profile', 'test-profile'],
            ['--verbose'],
            
            # Combined arguments
            ['--buckets', 'bucket1,bucket2', '--stages', 'dev', '--profile', 'test', '--verbose'],
        ]
        
        for test_args in test_cases:
            try:
                args = parser.parse_args(test_args)
                
                # Verify expected attributes exist
                assert hasattr(args, 'buckets'), f"Missing 'buckets' attribute for args {test_args}"
                assert hasattr(args, 'stages'), f"Missing 'stages' attribute for args {test_args}"
                assert hasattr(args, 'profile'), f"Missing 'profile' attribute for args {test_args}"
                assert hasattr(args, 'verbose'), f"Missing 'verbose' attribute for args {test_args}"
                
                # Verify default values work
                if '--stages' not in test_args:
                    assert args.stages == 'prod', f"Default stages should be 'prod', got {args.stages}"
                
                if '--verbose' not in test_args:
                    assert args.verbose is False, f"Default verbose should be False, got {args.verbose}"
                
                print(f"✅ Argument parsing validated: {' '.join(test_args)}")
                
            except Exception as e:
                pytest.fail(f"Argument parsing failed for {test_args}: {e}")
    
    def test_legacy_file_generation_preserved(self):
        """
        Test that legacy file generation (12 files) is preserved
        
        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        # Import components directly to test legacy functionality
        Configuration = upload_test_files.Configuration
        PathGenerator = upload_test_files.PathGenerator
        
        config = Configuration(
            buckets=["test-bucket"],
            stages=["prod"],
            aws_profile=None,
            verbose=False,
            base_path="/prod/public/",
            source_file_path="test.html"
        )
        
        path_generator = PathGenerator(config)
        
        # Test legacy path generation method still works
        legacy_paths = path_generator.generate_upload_paths("/prod/public/", 12)
        
        # Verify legacy behavior
        assert len(legacy_paths) == 12, f"Legacy method should generate 12 files, got {len(legacy_paths)}"
        
        # Verify legacy file patterns
        legacy_count = 0
        special_files = {'index.html', 'default.html'}
        
        for s3_key, filename in legacy_paths:
            # Should be either test-XXXXXX.html or special files
            is_test_pattern = filename.startswith('test-') and filename.endswith('.html')
            is_special_file = filename in special_files
            
            assert is_test_pattern or is_special_file, \
                f"Legacy file should follow expected patterns: {filename}"
            
            # Should have proper directory structure (1-4 levels deep)
            path_parts = s3_key.replace("/prod/public/", "").strip('/').split('/')
            depth = len(path_parts) - 1  # Subtract 1 for filename
            assert 1 <= depth <= 4, f"Legacy file should be 1-4 levels deep, got {depth} for {s3_key}"
            
            legacy_count += 1
        
        assert legacy_count == 12, f"Should have exactly 12 legacy files, got {legacy_count}"
        
        # Test enhanced path generation includes legacy files
        enhanced_paths = path_generator.generate_all_upload_paths("/prod/public/")
        
        assert len(enhanced_paths) == 62, f"Enhanced method should generate 62 files, got {len(enhanced_paths)}"
        
        # Verify enhanced includes legacy files
        enhanced_legacy_count = 0
        enhanced_nested_count = 0
        
        for s3_key, filename in enhanced_paths:
            if filename.startswith('nested-'):
                enhanced_nested_count += 1
            else:
                enhanced_legacy_count += 1
        
        assert enhanced_legacy_count == 12, f"Enhanced method should include 12 legacy files, got {enhanced_legacy_count}"
        assert enhanced_nested_count == 50, f"Enhanced method should include 50 nested files, got {enhanced_nested_count}"
        
        print("✅ Legacy file generation preserved in enhanced utility")
    
    def test_buildspec_integration_compatibility(self):
        """
        Test that buildspec-postdeploy.yml integration works correctly
        
        **Validates: Requirements 3.3**
        """
        # Check if buildspec-postdeploy.yml exists and references the upload utility
        buildspec_path = Path(__file__).parent.parent.parent / "buildspec-postdeploy.yml"
        
        if buildspec_path.exists():
            with open(buildspec_path, 'r') as f:
                buildspec_content = f.read()
            
            # Verify the upload utility is referenced (either directly or through post-deploy.sh)
            references_upload_utility = (
                "upload-test-files.py" in buildspec_content or
                "post-deploy.sh" in buildspec_content
            )
            assert references_upload_utility, \
                "buildspec-postdeploy.yml should reference upload-test-files.py or post-deploy.sh"
            
            # Check for common buildspec patterns that should still work
            expected_patterns = [
                "python",  # Should use python to run the script
                "build-scripts",  # Should reference the build-scripts directory
            ]
            
            for pattern in expected_patterns:
                assert pattern in buildspec_content, \
                    f"buildspec-postdeploy.yml should contain '{pattern}' for compatibility"
            
            print("✅ buildspec-postdeploy.yml integration compatibility verified")
        else:
            print("⚠️  buildspec-postdeploy.yml not found - skipping integration test")
    
    def test_error_handling_backward_compatibility(self):
        """
        Test that error handling maintains backward compatibility
        
        **Validates: Requirements 3.1**
        """
        # Test error cases that should behave the same way
        test_cases = [
            # No buckets specified (should fail gracefully)
            {
                'args': [],
                'env': {},
                'should_fail': True,
                'error_message': 'no buckets specified'
            },
            
            # Invalid bucket access (should fail gracefully)
            {
                'args': ['--buckets', 'invalid-bucket'],
                'env': {},
                'should_fail': True,
                'error_message': 'validation failed'
            }
        ]
        
        for test_case in test_cases:
            with patch.dict(os.environ, test_case['env'], clear=True):
                with patch('boto3.Session') as mock_session:
                    if test_case['should_fail']:
                        # Mock S3 client to simulate failures
                        mock_s3_client = MagicMock()
                        mock_session.return_value.client.return_value = mock_s3_client
                        
                        if 'invalid-bucket' in str(test_case['args']):
                            # Simulate bucket validation failure
                            mock_s3_client.head_bucket.side_effect = Exception("Bucket not found")
                    
                    with patch('sys.argv', ['upload-test-files.py'] + test_case['args']):
                        with patch('sys.exit') as mock_exit:
                            try:
                                main()
                                if test_case['should_fail']:
                                    # Should have exited with error code
                                    mock_exit.assert_called_with(1)
                            except SystemExit as e:
                                if test_case['should_fail']:
                                    assert e.code == 1, f"Should fail with exit code 1, got {e.code}"
                                else:
                                    assert e.code == 0, f"Should succeed with exit code 0, got {e.code}"
                            except Exception as e:
                                if test_case['should_fail']:
                                    # Expected to fail
                                    assert test_case['error_message'].lower() in str(e).lower(), \
                                        f"Error message should contain '{test_case['error_message']}', got: {e}"
                                else:
                                    pytest.fail(f"Unexpected error: {e}")
        
        print("✅ Error handling backward compatibility verified")
    
    def test_origin_path_backward_compatibility(self):
        """
        Test that default behavior is maintained when --origin_path is not specified
        
        **Validates: upload-utility-origin-path-option Requirements 6.1, 6.2, 6.3**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test backward compatibility</body></html>')
            test_html_path = f.name
        
        try:
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Mock the source file path
                with patch.object(Path, 'exists', return_value=True):
                    with patch('builtins.open', mock_open_with_content('<html><body>Test</body></html>')):
                        # Test WITHOUT --origin_path option (should use default)
                        with patch('sys.argv', ['upload-test-files.py', '--buckets', 'test-bucket', '--stages', 'prod']):
                            with patch('sys.exit') as mock_exit:
                                try:
                                    main()
                                    mock_exit.assert_called_with(0)
                                except SystemExit as e:
                                    assert e.code == 0, f"Should succeed with exit code 0, got {e.code}"
                
                # Verify files were uploaded to default path /{stage}/public/
                put_object_calls = mock_s3_client.put_object.call_args_list
                assert len(put_object_calls) == 62, f"Expected 62 uploads, got {len(put_object_calls)}"
                
                # Check that all paths use default pattern
                for call in put_object_calls:
                    s3_key = call[1]['Key']
                    assert s3_key.startswith('/prod/public/'), \
                        f"Default behavior should upload to /prod/public/, got {s3_key}"
                
                print("✅ Origin path backward compatibility verified:")
                print("   - Default pattern /{stageId}/public maintained ✓")
                print("   - All 62 files uploaded to /prod/public/ ✓")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_origin_path_validation(self):
        """
        Test that --origin_path validation works correctly
        
        **Validates: upload-utility-origin-path-option Requirements 3.1, 3.2**
        """
        # Test invalid origin path (missing leading slash)
        with patch('sys.argv', ['upload-test-files.py', '--buckets', 'test-bucket', '--origin_path', 'app/{stageId}']):
            with patch('sys.exit') as mock_exit:
                try:
                    parser = ArgumentParser()
                    args = parser.parse_args(['--buckets', 'test-bucket', '--origin_path', 'app/{stageId}'])
                    # This should raise ValueError during validation
                    pytest.fail("Should have raised ValueError for invalid origin path")
                except ValueError as e:
                    # Expected error
                    assert "must start with '/'" in str(e).lower(), \
                        f"Error message should mention leading slash requirement, got: {e}"
                    print("✅ Origin path validation correctly rejects invalid patterns")
                except SystemExit:
                    # Also acceptable if it exits with error code
                    pass


def mock_open_with_content(content):
    """Helper function to create a mock open that returns specific content"""
    from unittest.mock import mock_open
    return mock_open(read_data=content)


if __name__ == "__main__":
    # Run backward compatibility tests
    pytest.main([__file__, "-v", "-s"])