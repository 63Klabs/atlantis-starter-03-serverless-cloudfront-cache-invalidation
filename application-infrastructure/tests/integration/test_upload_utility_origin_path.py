#!/usr/bin/env python3
"""
Integration tests for upload utility origin path option.

This module validates the --origin_path command-line option functionality:
- Custom origin path patterns are correctly applied
- Files are uploaded to the correct S3 paths
- Backward compatibility is maintained when option is not provided

**Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 6.1, 6.2, 6.3**

Run with: pytest tests/integration/test_upload_utility_origin_path.py -v
"""
import pytest
import os
import sys
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock, call
import argparse

# Add the build-scripts directory to the path
build_scripts_path = Path(__file__).parent.parent.parent / "build-scripts"
sys.path.insert(0, str(build_scripts_path))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("upload_test_files", build_scripts_path / "upload-test-files.py")
    upload_test_files = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upload_test_files)
    
    Configuration = upload_test_files.Configuration
    ArgumentParser = upload_test_files.ArgumentParser
    EnvironmentManager = upload_test_files.EnvironmentManager
    PathGenerator = upload_test_files.PathGenerator
    FileGenerator = upload_test_files.FileGenerator
    S3Uploader = upload_test_files.S3Uploader
    Logger = upload_test_files.Logger
    UploadTask = upload_test_files.UploadTask
    main = upload_test_files.main
    
except ImportError as e:
    print(f"Import error: {e}")
    raise


class TestUploadUtilityOriginPath:
    """Integration tests for upload utility origin path option"""
    
    def test_custom_origin_path_with_stage_placeholder(self):
        """
        Test upload utility with custom origin path containing {stageId} placeholder
        
        Validates that files are uploaded to /app/prod/ when using --origin_path /app/{stageId}
        
        **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 2.4**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test content for custom origin path</body></html>')
            test_html_path = f.name
        
        try:
            # Mock S3 operations
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with custom origin path
                test_bucket = "test-bucket"
                test_stage = "prod"
                custom_origin_path = "/app/{stageId}"
                
                config = Configuration(
                    buckets=[test_bucket],
                    stages=[test_stage],
                    aws_profile=None,
                    verbose=False,
                    base_path="",
                    source_file_path=test_html_path,
                    origin_path_pattern=custom_origin_path
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                file_generator = FileGenerator(config)
                path_generator = PathGenerator(config)
                logger_component = Logger(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Determine base path using custom origin path pattern
                base_path = env_manager.determine_base_path(test_stage, config.origin_path_pattern)
                
                # Verify base path is correct
                assert base_path == "/app/prod/", f"Expected base path '/app/prod/', got '{base_path}'"
                
                # Generate upload paths
                upload_paths, structure_info = path_generator.generate_all_upload_paths_with_info(base_path)
                
                # Create upload tasks
                upload_tasks = []
                source_content = file_generator.get_source_content()
                
                for s3_key, filename in upload_paths:
                    task = UploadTask(
                        bucket=test_bucket,
                        key=s3_key,
                        content=source_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
                
                # Execute uploads
                results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
                
                # Validate results
                assert test_bucket in results, f"Expected results for bucket {test_bucket}"
                result = results[test_bucket]
                
                # Verify all 62 files were uploaded successfully
                assert result.successful_uploads == 62, \
                    f"Expected 62 successful uploads, got {result.successful_uploads}"
                assert result.failed_uploads == 0, \
                    f"Expected 0 failed uploads, got {result.failed_uploads}"
                
                # Verify all uploaded files have the correct path prefix
                for uploaded_path in result.upload_paths:
                    # Remove leading slash for comparison (S3 standard format)
                    clean_path = uploaded_path.lstrip('/')
                    expected_prefix = "app/prod/"
                    
                    assert clean_path.startswith(expected_prefix), \
                        f"Expected path to start with '{expected_prefix}', got '{clean_path}'"
                
                # Verify S3 put_object was called with correct keys
                put_object_calls = mock_s3_client.put_object.call_args_list
                assert len(put_object_calls) == 62, \
                    f"Expected 62 put_object calls, got {len(put_object_calls)}"
                
                # Verify all S3 keys start with the correct prefix
                for call_args in put_object_calls:
                    s3_key = call_args[1]['Key']  # Get Key from kwargs
                    assert s3_key.startswith('app/prod/'), \
                        f"Expected S3 key to start with 'app/prod/', got '{s3_key}'"
                
                print(f"✅ Custom origin path test passed:")
                print(f"   - Origin path pattern: {custom_origin_path}")
                print(f"   - Resolved base path: {base_path}")
                print(f"   - All 62 files uploaded to correct prefix: app/prod/")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_custom_origin_path_without_stage_placeholder(self):
        """
        Test upload utility with custom origin path without {stageId} placeholder
        
        Validates that files are uploaded to /static/ when using --origin_path /static
        
        **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 2.4**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test content for static origin path</body></html>')
            test_html_path = f.name
        
        try:
            # Mock S3 operations
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with static origin path
                test_bucket = "test-bucket"
                test_stage = "prod"
                custom_origin_path = "/static"
                
                config = Configuration(
                    buckets=[test_bucket],
                    stages=[test_stage],
                    aws_profile=None,
                    verbose=False,
                    base_path="",
                    source_file_path=test_html_path,
                    origin_path_pattern=custom_origin_path
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                file_generator = FileGenerator(config)
                path_generator = PathGenerator(config)
                logger_component = Logger(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Determine base path using custom origin path pattern
                base_path = env_manager.determine_base_path(test_stage, config.origin_path_pattern)
                
                # Verify base path is correct (stage is ignored when no placeholder)
                assert base_path == "/static/", f"Expected base path '/static/', got '{base_path}'"
                
                # Generate upload paths
                upload_paths, structure_info = path_generator.generate_all_upload_paths_with_info(base_path)
                
                # Create upload tasks
                upload_tasks = []
                source_content = file_generator.get_source_content()
                
                for s3_key, filename in upload_paths:
                    task = UploadTask(
                        bucket=test_bucket,
                        key=s3_key,
                        content=source_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
                
                # Execute uploads
                results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
                
                # Validate results
                assert test_bucket in results, f"Expected results for bucket {test_bucket}"
                result = results[test_bucket]
                
                # Verify all 62 files were uploaded successfully
                assert result.successful_uploads == 62, \
                    f"Expected 62 successful uploads, got {result.successful_uploads}"
                assert result.failed_uploads == 0, \
                    f"Expected 0 failed uploads, got {result.failed_uploads}"
                
                # Verify all uploaded files have the correct path prefix
                for uploaded_path in result.upload_paths:
                    # Remove leading slash for comparison (S3 standard format)
                    clean_path = uploaded_path.lstrip('/')
                    expected_prefix = "static/"
                    
                    assert clean_path.startswith(expected_prefix), \
                        f"Expected path to start with '{expected_prefix}', got '{clean_path}'"
                
                # Verify S3 put_object was called with correct keys
                put_object_calls = mock_s3_client.put_object.call_args_list
                assert len(put_object_calls) == 62, \
                    f"Expected 62 put_object calls, got {len(put_object_calls)}"
                
                # Verify all S3 keys start with the correct prefix
                for call_args in put_object_calls:
                    s3_key = call_args[1]['Key']  # Get Key from kwargs
                    assert s3_key.startswith('static/'), \
                        f"Expected S3 key to start with 'static/', got '{s3_key}'"
                
                print(f"✅ Static origin path test passed:")
                print(f"   - Origin path pattern: {custom_origin_path}")
                print(f"   - Resolved base path: {base_path}")
                print(f"   - All 62 files uploaded to correct prefix: static/")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_backward_compatibility_default_origin_path(self):
        """
        Test upload utility without --origin_path option (backward compatibility)
        
        Validates that files are uploaded to /prod/public/ when no --origin_path is provided
        
        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test content for backward compatibility</body></html>')
            test_html_path = f.name
        
        try:
            # Mock S3 operations
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with DEFAULT origin path (no custom value)
                test_bucket = "test-bucket"
                test_stage = "prod"
                default_origin_path = "/{stageId}/public"  # Default value
                
                config = Configuration(
                    buckets=[test_bucket],
                    stages=[test_stage],
                    aws_profile=None,
                    verbose=False,
                    base_path="",
                    source_file_path=test_html_path,
                    origin_path_pattern=default_origin_path  # Using default
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                file_generator = FileGenerator(config)
                path_generator = PathGenerator(config)
                logger_component = Logger(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Determine base path using default origin path pattern
                base_path = env_manager.determine_base_path(test_stage, config.origin_path_pattern)
                
                # Verify base path matches current behavior
                assert base_path == "/prod/public/", \
                    f"Expected base path '/prod/public/' (current behavior), got '{base_path}'"
                
                # Generate upload paths
                upload_paths, structure_info = path_generator.generate_all_upload_paths_with_info(base_path)
                
                # Create upload tasks
                upload_tasks = []
                source_content = file_generator.get_source_content()
                
                for s3_key, filename in upload_paths:
                    task = UploadTask(
                        bucket=test_bucket,
                        key=s3_key,
                        content=source_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
                
                # Execute uploads
                results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
                
                # Validate results
                assert test_bucket in results, f"Expected results for bucket {test_bucket}"
                result = results[test_bucket]
                
                # Verify all 62 files were uploaded successfully
                assert result.successful_uploads == 62, \
                    f"Expected 62 successful uploads, got {result.successful_uploads}"
                assert result.failed_uploads == 0, \
                    f"Expected 0 failed uploads, got {result.failed_uploads}"
                
                # Verify all uploaded files have the correct path prefix (current behavior)
                for uploaded_path in result.upload_paths:
                    # Remove leading slash for comparison (S3 standard format)
                    clean_path = uploaded_path.lstrip('/')
                    expected_prefix = "prod/public/"
                    
                    assert clean_path.startswith(expected_prefix), \
                        f"Expected path to start with '{expected_prefix}', got '{clean_path}'"
                
                # Verify S3 put_object was called with correct keys
                put_object_calls = mock_s3_client.put_object.call_args_list
                assert len(put_object_calls) == 62, \
                    f"Expected 62 put_object calls, got {len(put_object_calls)}"
                
                # Verify all S3 keys start with the correct prefix (current behavior)
                for call_args in put_object_calls:
                    s3_key = call_args[1]['Key']  # Get Key from kwargs
                    assert s3_key.startswith('prod/public/'), \
                        f"Expected S3 key to start with 'prod/public/', got '{s3_key}'"
                
                print(f"✅ Backward compatibility test passed:")
                print(f"   - Origin path pattern: {default_origin_path} (default)")
                print(f"   - Resolved base path: {base_path}")
                print(f"   - All 62 files uploaded to correct prefix: prod/public/ (current behavior)")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_multiple_stages_with_custom_origin_path(self):
        """
        Test upload utility with multiple stages and custom origin path
        
        Validates that files are uploaded to correct paths for each stage
        
        **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 2.4**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test content for multiple stages</body></html>')
            test_html_path = f.name
        
        try:
            # Mock S3 operations
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with multiple stages
                test_bucket = "test-bucket"
                test_stages = ["dev", "staging", "prod"]
                custom_origin_path = "/app/{stageId}"
                
                config = Configuration(
                    buckets=[test_bucket],
                    stages=test_stages,
                    aws_profile=None,
                    verbose=False,
                    base_path="",
                    source_file_path=test_html_path,
                    origin_path_pattern=custom_origin_path
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                file_generator = FileGenerator(config)
                path_generator = PathGenerator(config)
                logger_component = Logger(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Generate upload tasks for all stages
                upload_tasks = []
                source_content = file_generator.get_source_content()
                structure_info = None
                
                expected_prefixes = {}
                
                for stage in test_stages:
                    # Determine base path for this stage
                    base_path = env_manager.determine_base_path(stage, config.origin_path_pattern)
                    
                    # Verify base path is correct for this stage
                    expected_base_path = f"/app/{stage}/"
                    assert base_path == expected_base_path, \
                        f"Expected base path '{expected_base_path}' for stage '{stage}', got '{base_path}'"
                    
                    # Store expected prefix for validation
                    expected_prefixes[stage] = f"app/{stage}/"
                    
                    # Generate upload paths
                    upload_paths, nested_info = path_generator.generate_all_upload_paths_with_info(base_path)
                    
                    if structure_info is None:
                        structure_info = nested_info
                    
                    # Create upload tasks
                    for s3_key, filename in upload_paths:
                        task = UploadTask(
                            bucket=test_bucket,
                            key=s3_key,
                            content=source_content,
                            filename=filename
                        )
                        upload_tasks.append(task)
                
                # Execute uploads
                results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
                
                # Validate results
                assert test_bucket in results, f"Expected results for bucket {test_bucket}"
                result = results[test_bucket]
                
                # Verify all files were uploaded successfully (62 files × 3 stages = 186)
                expected_total_files = 62 * len(test_stages)
                assert result.successful_uploads == expected_total_files, \
                    f"Expected {expected_total_files} successful uploads, got {result.successful_uploads}"
                assert result.failed_uploads == 0, \
                    f"Expected 0 failed uploads, got {result.failed_uploads}"
                
                # Verify S3 put_object was called correct number of times
                put_object_calls = mock_s3_client.put_object.call_args_list
                assert len(put_object_calls) == expected_total_files, \
                    f"Expected {expected_total_files} put_object calls, got {len(put_object_calls)}"
                
                # Verify S3 keys have correct prefixes for each stage
                keys_by_stage = {stage: [] for stage in test_stages}
                
                for call_args in put_object_calls:
                    s3_key = call_args[1]['Key']  # Get Key from kwargs
                    
                    # Determine which stage this key belongs to
                    for stage in test_stages:
                        if s3_key.startswith(expected_prefixes[stage]):
                            keys_by_stage[stage].append(s3_key)
                            break
                
                # Verify each stage has exactly 62 files
                for stage in test_stages:
                    assert len(keys_by_stage[stage]) == 62, \
                        f"Expected 62 files for stage '{stage}', got {len(keys_by_stage[stage])}"
                
                print(f"✅ Multiple stages test passed:")
                print(f"   - Origin path pattern: {custom_origin_path}")
                print(f"   - Stages: {', '.join(test_stages)}")
                for stage in test_stages:
                    print(f"   - Stage '{stage}': 62 files uploaded to {expected_prefixes[stage]}")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s"])
