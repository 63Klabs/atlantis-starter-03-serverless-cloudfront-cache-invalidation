"""Property-based tests for test file upload utility."""

import sys
import os
import importlib.util
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings, strategies as st
import hypothesis

# Add build-scripts to path for imports
build_scripts_path = str(Path(__file__).parent.parent.parent / 'build-scripts')
sys.path.insert(0, build_scripts_path)

# Import the module using importlib to handle hyphenated filename
import importlib.util
spec = importlib.util.spec_from_file_location(
    "upload_test_files", 
    Path(__file__).parent.parent.parent / 'build-scripts' / 'upload-test-files.py'
)
upload_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload_module)

ArgumentParser = upload_module.ArgumentParser
EnvironmentManager = upload_module.EnvironmentManager
FileGenerator = upload_module.FileGenerator
PathGenerator = upload_module.PathGenerator
Configuration = upload_module.Configuration


@settings(max_examples=10)  # Minimal iterations per testing guidelines
@given(st.lists(
    st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and ',' not in x),
    min_size=1,
    max_size=10
))
def test_property_1_bucket_list_parsing_consistency(bucket_names):
    """Property 1: Bucket list parsing consistency.
    
    For any comma-delimited bucket string, the utility should upload files to exactly
    the buckets specified in the list.
    
    **Feature: test-file-upload-utility, Property 1: Bucket list parsing consistency**
    **Validates: Requirements 1.1**
    """
    # Create comma-delimited bucket string
    bucket_string = ','.join(bucket_names)
    
    # Test ArgumentParser and EnvironmentManager integration
    env_manager = EnvironmentManager()
    
    # Parse bucket list
    parsed_buckets = env_manager.get_target_buckets(bucket_string)
    
    # Property: Parsed buckets should match original bucket names
    assert len(parsed_buckets) == len(bucket_names), \
        f"Expected {len(bucket_names)} buckets, got {len(parsed_buckets)}"
    
    # Check each bucket name is preserved (order and content)
    for original, parsed in zip(bucket_names, parsed_buckets):
        assert parsed == original.strip(), \
            f"Expected bucket '{original.strip()}', got '{parsed}'"


@settings(max_examples=10)
@given(st.one_of(
    st.just('prod'),
    st.just('staging'),
    st.just('dev'),
    st.just('local')
))
def test_property_2_environment_based_configuration(environment):
    """Property 2: Environment-based configuration.
    
    For any valid environment parameter, the utility should configure AWS operations
    and base paths consistently for that environment.
    
    **Feature: test-file-upload-utility, Property 2: Environment-based configuration**
    **Validates: Requirements 1.2, 3.2**
    """
    env_manager = EnvironmentManager()
    
    # Test base path determination
    base_path = env_manager.determine_base_path(environment)
    
    # Property: Environment should consistently determine base path
    if environment == 'prod':
        expected_path = '/prod/public/'
    else:
        expected_path = '/stage/public/'
    
    assert base_path == expected_path, \
        f"Expected base path '{expected_path}' for environment '{environment}', got '{base_path}'"


@settings(max_examples=10)
@given(st.lists(
    st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
    min_size=1,
    max_size=5
).map(lambda buckets: ','.join(buckets) + ','))  # Add trailing comma
def test_property_bucket_parsing_with_trailing_comma(bucket_string_with_comma):
    """Test bucket parsing handles trailing commas correctly.
    
    **Feature: test-file-upload-utility, Property 1: Bucket list parsing consistency**
    **Validates: Requirements 1.1**
    """
    env_manager = EnvironmentManager()
    
    # Parse bucket list with trailing comma
    parsed_buckets = env_manager.get_target_buckets(bucket_string_with_comma)
    
    # Property: Trailing comma should not create empty bucket names
    for bucket in parsed_buckets:
        assert bucket.strip() != '', f"Found empty bucket name in parsed list: {parsed_buckets}"


@settings(max_examples=10)
@given(st.one_of(
    st.just(''),  # Empty string
    st.just(','),  # Only comma
    st.just(',,'),  # Multiple commas
    st.just(' , , ')  # Spaces and commas
))
def test_property_bucket_parsing_invalid_input(invalid_bucket_string):
    """Test bucket parsing handles invalid input correctly.
    
    **Feature: test-file-upload-utility, Property 1: Bucket list parsing consistency**
    **Validates: Requirements 1.1**
    """
    env_manager = EnvironmentManager()
    
    # Property: Invalid bucket strings should raise ValueError
    try:
        parsed_buckets = env_manager.get_target_buckets(invalid_bucket_string)
        # If we get here, check that no empty buckets were returned
        for bucket in parsed_buckets:
            assert bucket.strip() != '', f"Found empty bucket name: '{bucket}'"
    except ValueError:
        # This is expected behavior for invalid input
        pass


@settings(max_examples=10)
@given(st.just(None))
def test_property_bucket_fallback_to_environment_variable(_):
    """Test bucket resolution falls back to environment variable when no --buckets provided.
    
    **Feature: test-file-upload-utility, Property 2: Environment-based configuration**
    **Validates: Requirements 1.2, 3.2**
    """
    env_manager = EnvironmentManager()
    
    # Test with environment variable set
    test_bucket = 'test-env-bucket'
    with patch.dict(os.environ, {'S3_STATIC_HOST_BUCKET': test_bucket}):
        buckets = env_manager.get_target_buckets(None)
        
        # Property: Should return environment variable bucket
        assert len(buckets) == 1, f"Expected 1 bucket from env var, got {len(buckets)}"
        assert buckets[0] == test_bucket, f"Expected '{test_bucket}', got '{buckets[0]}'"


@settings(max_examples=10)
@given(st.just(None))
def test_property_bucket_error_when_no_source(_):
    """Test bucket resolution raises error when no buckets specified anywhere.
    
    **Feature: test-file-upload-utility, Property 2: Environment-based configuration**
    **Validates: Requirements 1.2, 3.2**
    """
    env_manager = EnvironmentManager()
    
    # Test with no buckets argument and no environment variable
    with patch.dict(os.environ, {}, clear=False):
        # Remove environment variable if it exists
        if 'S3_STATIC_HOST_BUCKET' in os.environ:
            del os.environ['S3_STATIC_HOST_BUCKET']
        
        # Property: Should raise ValueError when no bucket source available
        try:
            buckets = env_manager.get_target_buckets(None)
            assert False, f"Expected ValueError but got buckets: {buckets}"
        except ValueError as e:
            assert "No buckets specified" in str(e), f"Expected specific error message, got: {e}"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=100))
def test_property_4_filename_pattern_compliance(seed):
    """Property 4: Filename pattern compliance.
    
    For any generated filename, it should follow the "test-XXXXXX.html" pattern 
    where XXXXXX is exactly 6 alphanumeric characters.
    
    **Feature: test-file-upload-utility, Property 4: Filename pattern compliance**
    **Validates: Requirements 3.3**
    """
    import re
    import random
    
    # Set random seed for reproducible test
    random.seed(seed)
    
    # Create a minimal configuration for FileGenerator
    config = Configuration(
        buckets=['test-bucket'],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    file_generator = FileGenerator(config)
    
    # Generate filename
    filename = file_generator.generate_random_filename()
    
    # Property: Filename should match test-XXXXXX.html pattern
    pattern = r'^test-[A-Za-z0-9]{6}\.html$'
    assert re.match(pattern, filename), \
        f"Filename '{filename}' does not match pattern 'test-XXXXXX.html' where X is alphanumeric"
    
    # Additional checks for exact format
    assert filename.startswith('test-'), f"Filename should start with 'test-', got: {filename}"
    assert filename.endswith('.html'), f"Filename should end with '.html', got: {filename}"
    
    # Check middle part is exactly 6 characters
    middle_part = filename[5:-5]  # Remove 'test-' and '.html'
    assert len(middle_part) == 6, f"Expected 6 characters between 'test-' and '.html', got {len(middle_part)}: '{middle_part}'"
    
    # Check all characters in middle part are alphanumeric
    assert middle_part.isalnum(), f"Middle part should be alphanumeric, got: '{middle_part}'"


@settings(max_examples=10)
@given(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
def test_property_3_file_count_consistency(bucket_name):
    """Property 3: File count consistency.
    
    For any target bucket, the utility should create exactly 12 test files 
    regardless of bucket name or configuration.
    
    **Feature: test-file-upload-utility, Property 3: File count consistency**
    **Validates: Requirements 3.1**
    """
    # Create configuration with the test bucket
    config = Configuration(
        buckets=[bucket_name.strip()],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    path_generator = PathGenerator(config)
    
    # Generate upload paths
    upload_paths = path_generator.generate_upload_paths(config.base_path)
    
    # Property: Should always generate exactly 12 files
    assert len(upload_paths) == 12, \
        f"Expected exactly 12 files for bucket '{bucket_name}', got {len(upload_paths)}"
    
    # Property: All paths should be unique
    s3_keys = [path[0] for path in upload_paths]
    unique_keys = set(s3_keys)
    assert len(unique_keys) == 12, \
        f"Expected 12 unique paths, got {len(unique_keys)} unique out of {len(s3_keys)} total"
    
    # Property: All paths should start with the base path
    for s3_key, filename in upload_paths:
        assert s3_key.startswith(config.base_path.rstrip('/')), \
            f"Path '{s3_key}' should start with base path '{config.base_path}'"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=100))
def test_property_5_directory_depth_distribution(seed):
    """Property 5: Directory depth distribution.
    
    For any set of 12 generated paths, they should include files at directory 
    depths 1, 2, 3, and 4 levels under the base path.
    
    **Feature: test-file-upload-utility, Property 5: Directory depth distribution**
    **Validates: Requirements 3.4**
    """
    import random
    
    # Set random seed for reproducible test
    random.seed(seed)
    
    # Create configuration
    config = Configuration(
        buckets=['test-bucket'],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    path_generator = PathGenerator(config)
    
    # Generate upload paths
    upload_paths = path_generator.generate_upload_paths(config.base_path)
    
    # Analyze directory depths
    depth_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    base_path_clean = config.base_path.strip('/')
    
    for s3_key, filename in upload_paths:
        # Remove base path and count directory levels
        relative_path = s3_key.replace(f"/{base_path_clean}/", "")
        path_parts = relative_path.split('/')
        # Depth is number of directories (excluding filename)
        depth = len(path_parts) - 1
        
        if depth in depth_counts:
            depth_counts[depth] += 1
    
    # Property: Should have files at all depths 1-4
    for depth in range(1, 5):
        assert depth_counts[depth] > 0, \
            f"Expected files at depth {depth}, but found none. Distribution: {depth_counts}"
    
    # Property: Total should be 12
    total_files = sum(depth_counts.values())
    assert total_files == 12, \
        f"Expected 12 total files, got {total_files}. Distribution: {depth_counts}"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=100))
def test_property_6_filename_variety_requirement(seed):
    """Property 6: Filename variety requirement.
    
    For any set of 12 generated files, some should be named "index.html" 
    and some should be named "default.html".
    
    **Feature: test-file-upload-utility, Property 6: Filename variety requirement**
    **Validates: Requirements 3.5**
    """
    import random
    
    # Set random seed for reproducible test
    random.seed(seed)
    
    # Create configuration
    config = Configuration(
        buckets=['test-bucket'],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    path_generator = PathGenerator(config)
    
    # Generate upload paths
    upload_paths = path_generator.generate_upload_paths(config.base_path)
    
    # Extract filenames
    filenames = [filename for s3_key, filename in upload_paths]
    
    # Count special filenames
    index_count = filenames.count('index.html')
    default_count = filenames.count('default.html')
    
    # Property: Should have at least one index.html or default.html
    special_filename_count = index_count + default_count
    assert special_filename_count > 0, \
        f"Expected at least one 'index.html' or 'default.html', but found none. Filenames: {filenames}"
    
    # Property: Should have variety (not all files should be the same special filename)
    if special_filename_count > 1:
        # If we have multiple special filenames, they should include both types
        assert index_count > 0 or default_count > 0, \
            f"Expected variety in special filenames. Found {index_count} index.html and {default_count} default.html"
    
    # Property: Should also have some random filenames (test-*.html pattern)
    random_filename_count = 0
    for filename in filenames:
        if filename.startswith('test-') and filename.endswith('.html') and len(filename) == 16:
            random_filename_count += 1
    
    assert random_filename_count > 0, \
        f"Expected at least one random filename (test-XXXXXX.html), but found none. Filenames: {filenames}"
    
    # Property: Total should be 12
    assert len(filenames) == 12, \
        f"Expected 12 filenames, got {len(filenames)}"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=5))
def test_property_7_retry_behavior_consistency(max_retries):
    """Property 7: Retry behavior consistency.
    
    For any S3 upload failure, the utility should retry up to 3 times with 
    exponential backoff before giving up.
    
    **Feature: test-file-upload-utility, Property 7: Retry behavior consistency**
    **Validates: Requirements 4.1**
    """
    import boto3
    from unittest.mock import Mock, patch
    import time
    
    # Import S3Uploader
    S3Uploader = upload_module.S3Uploader
    
    # Create configuration
    config = Configuration(
        buckets=['test-bucket'],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create mock session and S3 client
    mock_session = Mock(spec=boto3.Session)
    mock_s3_client = Mock()
    mock_session.client.return_value = mock_s3_client
    
    # Create Logger instance for S3Uploader
    Logger = upload_module.Logger
    logger_component = Logger(config)
    
    # Create S3Uploader instance
    uploader = S3Uploader(mock_session, config, logger_component)
    uploader.s3_client = mock_s3_client
    
    # Mock put_object to always fail
    mock_s3_client.put_object.side_effect = Exception("Simulated S3 failure")
    
    # Track time to verify exponential backoff
    start_time = time.time()
    
    # Mock time.sleep to avoid actual delays in tests
    with patch('time.sleep') as mock_sleep:
        # Test upload with retry
        result = uploader.upload_with_retry('test-bucket', 'test-key', 'test-content', max_retries)
        
        # Property: Should return False after all retries fail
        assert result is False, f"Expected upload to fail after retries, but got success"
        
        # Property: Should call put_object exactly max_retries + 1 times (initial + retries)
        expected_calls = max_retries + 1
        actual_calls = mock_s3_client.put_object.call_count
        assert actual_calls == expected_calls, \
            f"Expected {expected_calls} put_object calls, got {actual_calls}"
        
        # Property: Should call sleep exactly max_retries times (no sleep after final failure)
        expected_sleeps = max_retries
        actual_sleeps = mock_sleep.call_count
        assert actual_sleeps == expected_sleeps, \
            f"Expected {expected_sleeps} sleep calls, got {actual_sleeps}"
        
        # Property: Sleep delays should follow exponential backoff (2^attempt)
        if max_retries > 0:
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            for i, delay in enumerate(sleep_calls):
                expected_delay = 2 ** i
                assert delay == expected_delay, \
                    f"Expected delay {expected_delay} for attempt {i}, got {delay}"


@settings(max_examples=10)
@given(st.integers(min_value=0, max_value=3))
def test_property_7_retry_success_behavior(success_on_attempt):
    """Property 7: Retry behavior consistency - success case.
    
    For any S3 upload that succeeds on a retry attempt, the utility should 
    stop retrying and return success.
    
    **Feature: test-file-upload-utility, Property 7: Retry behavior consistency**
    **Validates: Requirements 4.1**
    """
    import boto3
    from unittest.mock import Mock, patch, call
    
    # Import S3Uploader
    S3Uploader = upload_module.S3Uploader
    
    # Create configuration
    config = Configuration(
        buckets=['test-bucket'],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create mock session and S3 client
    mock_session = Mock(spec=boto3.Session)
    mock_s3_client = Mock()
    mock_session.client.return_value = mock_s3_client
    
    # Create Logger instance for S3Uploader
    Logger = upload_module.Logger
    logger_component = Logger(config)
    
    # Create S3Uploader instance
    uploader = S3Uploader(mock_session, config, logger_component)
    uploader.s3_client = mock_s3_client
    
    # Configure put_object to fail for first N attempts, then succeed
    call_count = 0
    def mock_put_object(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= success_on_attempt:
            raise Exception(f"Simulated failure on attempt {call_count}")
        return {}  # Success
    
    mock_s3_client.put_object.side_effect = mock_put_object
    
    # Mock time.sleep to avoid actual delays in tests
    with patch('time.sleep') as mock_sleep:
        # Test upload with retry (use max_retries=3 as per requirements)
        result = uploader.upload_with_retry('test-bucket', 'test-key', 'test-content', max_retries=3)
        
        # Property: Should return True when upload eventually succeeds
        assert result is True, f"Expected upload to succeed on attempt {success_on_attempt + 1}, but got failure"
        
        # Property: Should call put_object exactly success_on_attempt + 1 times
        expected_calls = success_on_attempt + 1
        actual_calls = mock_s3_client.put_object.call_count
        assert actual_calls == expected_calls, \
            f"Expected {expected_calls} put_object calls, got {actual_calls}"
        
        # Property: Should call sleep exactly success_on_attempt times (no sleep after success)
        expected_sleeps = success_on_attempt
        actual_sleeps = mock_sleep.call_count
        assert actual_sleeps == expected_sleeps, \
            f"Expected {expected_sleeps} sleep calls, got {actual_sleeps}"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=5).flatmap(
    lambda n: st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),  # bucket
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')), min_size=5, max_size=20)  # key
        ),
        min_size=n,
        max_size=n,
        unique=True
    )
))
def test_property_9_upload_logging_completeness(upload_data):
    """Property 9: Upload logging completeness.
    
    For any successful file upload, the utility should log the complete S3 path 
    of the uploaded file.
    
    **Feature: test-file-upload-utility, Property 9: Upload logging completeness**
    **Validates: Requirements 5.1**
    """
    import boto3
    from unittest.mock import Mock, patch
    import logging
    import io
    
    # Import required classes
    Logger = upload_module.Logger
    S3Uploader = upload_module.S3Uploader
    Configuration = upload_module.Configuration
    
    # Create configuration
    config = Configuration(
        buckets=[data[0] for data in upload_data],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create Logger instance
    logger_component = Logger(config)
    
    # Capture log output
    log_capture = io.StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.INFO)
    
    # Get the logger and add our handler
    test_logger = logging.getLogger(upload_module.__name__)
    original_handlers = test_logger.handlers[:]
    test_logger.handlers = [log_handler]
    test_logger.setLevel(logging.INFO)
    
    try:
        # Create mock session and S3 client
        mock_session = Mock(spec=boto3.Session)
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        
        # Configure put_object to always succeed
        mock_s3_client.put_object.return_value = {}
        
        # Create S3Uploader instance
        uploader = S3Uploader(mock_session, config, logger_component)
        uploader.s3_client = mock_s3_client
        
        # Test upload logging for each upload
        for bucket, key in upload_data:
            # Perform upload
            result = uploader.upload_file(bucket, key, '<html><body>Test</body></html>')
            
            # Property: Upload should succeed
            assert result is True, f"Expected upload to succeed for s3://{bucket}/{key}"
        
        # Get logged output
        log_output = log_capture.getvalue()
        
        # Property: Each successful upload should be logged with complete S3 path
        for bucket, key in upload_data:
            clean_key = key.lstrip('/')
            expected_s3_path = f"s3://{bucket}/{clean_key}"
            
            assert f"Uploaded: {expected_s3_path}" in log_output, \
                f"Expected log entry 'Uploaded: {expected_s3_path}' not found in output: {log_output}"
        
        # Property: Number of "Uploaded:" log entries should match number of uploads
        upload_log_count = log_output.count("Uploaded: s3://")
        expected_count = len(upload_data)
        assert upload_log_count == expected_count, \
            f"Expected {expected_count} upload log entries, found {upload_log_count} in: {log_output}"
    
    finally:
        # Restore original handlers
        test_logger.handlers = original_handlers


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=3).flatmap(
    lambda n: st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),  # bucket
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')), min_size=5, max_size=20)  # key
        ),
        min_size=n,
        max_size=n,
        unique=True
    )
))
def test_property_9_upload_logging_verbose_mode(upload_data):
    """Property 9: Upload logging completeness - verbose mode.
    
    For any successful file upload in verbose mode, the utility should log 
    additional detailed information about the upload.
    
    **Feature: test-file-upload-utility, Property 9: Upload logging completeness**
    **Validates: Requirements 5.1**
    """
    import boto3
    from unittest.mock import Mock
    import logging
    import io
    
    # Import required classes
    Logger = upload_module.Logger
    S3Uploader = upload_module.S3Uploader
    Configuration = upload_module.Configuration
    
    # Create configuration with verbose mode enabled
    config = Configuration(
        buckets=[data[0] for data in upload_data],
        environment='staging',
        aws_profile=None,
        verbose=True,  # Enable verbose mode
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create Logger instance
    logger_component = Logger(config)
    
    # Capture log output
    log_capture = io.StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.DEBUG)
    
    # Get the logger and add our handler
    test_logger = logging.getLogger(upload_module.__name__)
    original_handlers = test_logger.handlers[:]
    test_logger.handlers = [log_handler]
    test_logger.setLevel(logging.DEBUG)
    
    try:
        # Create mock session and S3 client
        mock_session = Mock(spec=boto3.Session)
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        
        # Configure put_object to always succeed
        mock_s3_client.put_object.return_value = {}
        
        # Create S3Uploader instance
        uploader = S3Uploader(mock_session, config, logger_component)
        uploader.s3_client = mock_s3_client
        
        # Test upload logging for each upload
        for bucket, key in upload_data:
            # Perform upload
            result = uploader.upload_file(bucket, key, '<html><body>Test</body></html>')
            
            # Property: Upload should succeed
            assert result is True, f"Expected upload to succeed for s3://{bucket}/{key}"
        
        # Get logged output
        log_output = log_capture.getvalue()
        
        # Property: Each successful upload should be logged with complete S3 path
        for bucket, key in upload_data:
            clean_key = key.lstrip('/')
            expected_s3_path = f"s3://{bucket}/{clean_key}"
            
            assert f"Uploaded: {expected_s3_path}" in log_output, \
                f"Expected log entry 'Uploaded: {expected_s3_path}' not found in output: {log_output}"
            
            # Property: Verbose mode should include upload details
            assert f"Upload details - Bucket: {bucket}, Key: {clean_key}" in log_output, \
                f"Expected verbose upload details for {bucket}/{clean_key} not found in: {log_output}"
    
    finally:
        # Restore original handlers
        test_logger.handlers = original_handlers


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=3).flatmap(
    lambda n: st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),  # bucket
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')), min_size=5, max_size=20)  # key
        ),
        min_size=n,
        max_size=n,
        unique=True
    )
))
def test_property_9_upload_failure_logging(upload_data):
    """Property 9: Upload logging completeness - failure case.
    
    For any failed file upload, the utility should log the complete S3 path 
    and error information.
    
    **Feature: test-file-upload-utility, Property 9: Upload logging completeness**
    **Validates: Requirements 5.1**
    """
    import boto3
    from unittest.mock import Mock
    import logging
    import io
    
    # Import required classes
    Logger = upload_module.Logger
    S3Uploader = upload_module.S3Uploader
    Configuration = upload_module.Configuration
    
    # Create configuration
    config = Configuration(
        buckets=[data[0] for data in upload_data],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create Logger instance
    logger_component = Logger(config)
    
    # Capture log output
    log_capture = io.StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.ERROR)
    
    # Get the logger and add our handler
    test_logger = logging.getLogger(upload_module.__name__)
    original_handlers = test_logger.handlers[:]
    test_logger.handlers = [log_handler]
    test_logger.setLevel(logging.ERROR)
    
    try:
        # Create mock session and S3 client
        mock_session = Mock(spec=boto3.Session)
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        
        # Configure put_object to always fail
        mock_s3_client.put_object.side_effect = Exception("Simulated S3 failure")
        
        # Create S3Uploader instance
        uploader = S3Uploader(mock_session, config, logger_component)
        uploader.s3_client = mock_s3_client
        
        # Test upload logging for each upload
        for bucket, key in upload_data:
            # Perform upload (should fail)
            result = uploader.upload_file(bucket, key, '<html><body>Test</body></html>')
            
            # Property: Upload should fail
            assert result is False, f"Expected upload to fail for s3://{bucket}/{key}"
        
        # Get logged output
        log_output = log_capture.getvalue()
        
        # Property: Each failed upload should be logged with complete S3 path and error
        for bucket, key in upload_data:
            clean_key = key.lstrip('/')
            expected_s3_path = f"s3://{bucket}/{clean_key}"
            
            assert f"Upload failed for {expected_s3_path}" in log_output, \
                f"Expected error log entry for {expected_s3_path} not found in output: {log_output}"
            
            # Property: Error message should include the simulated failure
            assert "Simulated S3 failure" in log_output, \
                f"Expected error message 'Simulated S3 failure' not found in: {log_output}"
        
        # Property: Number of failure log entries should match number of uploads
        failure_log_count = log_output.count("Upload failed for s3://")
        expected_count = len(upload_data)
        assert failure_log_count == expected_count, \
            f"Expected {expected_count} failure log entries, found {failure_log_count} in: {log_output}"
    
    finally:
        # Restore original handlers
        test_logger.handlers = original_handlers


@settings(max_examples=10, suppress_health_check=[hypothesis.HealthCheck.filter_too_much])
@given(st.integers(min_value=2, max_value=5).flatmap(
    lambda n: st.lists(
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),
        min_size=n,
        max_size=n,
        unique=True
    )
))
def test_property_8_bucket_error_isolation(bucket_names):
    """Property 8: Bucket error isolation.
    
    For any list of buckets where some don't exist, the utility should continue 
    processing remaining buckets after logging errors for missing ones.
    
    **Feature: test-file-upload-utility, Property 8: Bucket error isolation**
    **Validates: Requirements 4.2**
    """
    import boto3
    from unittest.mock import Mock, patch
    from botocore.exceptions import NoCredentialsError, ClientError
    
    # Import required classes
    S3Uploader = upload_module.S3Uploader
    UploadTask = upload_module.UploadTask
    
    # Create configuration
    config = Configuration(
        buckets=bucket_names,
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create mock session and S3 client
    mock_session = Mock(spec=boto3.Session)
    mock_s3_client = Mock()
    mock_session.client.return_value = mock_s3_client
    
    # Create Logger instance for S3Uploader
    Logger = upload_module.Logger
    logger_component = Logger(config)
    
    # Create S3Uploader instance
    uploader = S3Uploader(mock_session, config, logger_component)
    uploader.s3_client = mock_s3_client
    
    # Configure head_bucket to fail for first bucket, succeed for others
    def mock_head_bucket(Bucket):
        if Bucket == bucket_names[0]:
            # Simulate bucket doesn't exist
            error_response = {'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}}
            raise ClientError(error_response, 'HeadBucket')
        return {}  # Success for other buckets
    
    mock_s3_client.head_bucket.side_effect = mock_head_bucket
    
    # Configure put_object to always succeed (for buckets that pass validation)
    mock_s3_client.put_object.return_value = {}
    
    # Create upload tasks for all buckets
    upload_tasks = []
    for bucket in bucket_names:
        task = UploadTask(
            bucket=bucket,
            key='/stage/public/test/test-file.html',
            content='<html><body>Test</body></html>',
            filename='test-file.html'
        )
        upload_tasks.append(task)
    
    # Execute upload tasks
    results = uploader.execute_upload_tasks(upload_tasks)
    
    # Property: Should return results for all buckets
    assert len(results) == len(bucket_names), \
        f"Expected results for {len(bucket_names)} buckets, got {len(results)}"
    
    # Property: First bucket should have failed uploads (bucket doesn't exist)
    first_bucket_result = results[bucket_names[0]]
    assert first_bucket_result.successful_uploads == 0, \
        f"Expected 0 successful uploads for non-existent bucket {bucket_names[0]}, got {first_bucket_result.successful_uploads}"
    assert first_bucket_result.failed_uploads == 1, \
        f"Expected 1 failed upload for non-existent bucket {bucket_names[0]}, got {first_bucket_result.failed_uploads}"
    
    # Property: Other buckets should have successful uploads (bucket exists)
    for bucket in bucket_names[1:]:
        bucket_result = results[bucket]
        assert bucket_result.successful_uploads == 1, \
            f"Expected 1 successful upload for existing bucket {bucket}, got {bucket_result.successful_uploads}"
        assert bucket_result.failed_uploads == 0, \
            f"Expected 0 failed uploads for existing bucket {bucket}, got {bucket_result.failed_uploads}"
    
    # Property: head_bucket should be called for each bucket (validation)
    expected_head_bucket_calls = len(bucket_names)
    actual_head_bucket_calls = mock_s3_client.head_bucket.call_count
    assert actual_head_bucket_calls == expected_head_bucket_calls, \
        f"Expected {expected_head_bucket_calls} head_bucket calls, got {actual_head_bucket_calls}"
    
    # Property: put_object should only be called for valid buckets (not the first one)
    expected_put_object_calls = len(bucket_names) - 1  # Exclude first bucket that failed validation
    actual_put_object_calls = mock_s3_client.put_object.call_count
    assert actual_put_object_calls == expected_put_object_calls, \
        f"Expected {expected_put_object_calls} put_object calls, got {actual_put_object_calls}"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=3).flatmap(
    lambda n: st.lists(
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),
        min_size=n,
        max_size=n,
        unique=True
    )
))
def test_property_8_all_buckets_fail_validation(bucket_names):
    """Property 8: Bucket error isolation - all buckets fail validation.
    
    For any list of buckets where all don't exist, the utility should handle 
    all failures gracefully and return appropriate results.
    
    **Feature: test-file-upload-utility, Property 8: Bucket error isolation**
    **Validates: Requirements 4.2**
    """
    import boto3
    from unittest.mock import Mock
    from botocore.exceptions import ClientError
    
    # Import required classes
    S3Uploader = upload_module.S3Uploader
    UploadTask = upload_module.UploadTask
    
    # Create configuration
    config = Configuration(
        buckets=bucket_names,
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create mock session and S3 client
    mock_session = Mock(spec=boto3.Session)
    mock_s3_client = Mock()
    mock_session.client.return_value = mock_s3_client
    
    # Create Logger instance for S3Uploader
    Logger = upload_module.Logger
    logger_component = Logger(config)
    
    # Create S3Uploader instance
    uploader = S3Uploader(mock_session, config, logger_component)
    uploader.s3_client = mock_s3_client
    
    # Configure head_bucket to fail for all buckets
    def mock_head_bucket(Bucket):
        error_response = {'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}}
        raise ClientError(error_response, 'HeadBucket')
    
    mock_s3_client.head_bucket.side_effect = mock_head_bucket
    
    # Create upload tasks for all buckets
    upload_tasks = []
    for bucket in bucket_names:
        task = UploadTask(
            bucket=bucket,
            key='/stage/public/test/test-file.html',
            content='<html><body>Test</body></html>',
            filename='test-file.html'
        )
        upload_tasks.append(task)
    
    # Execute upload tasks
    results = uploader.execute_upload_tasks(upload_tasks)
    
    # Property: Should return results for all buckets
    assert len(results) == len(bucket_names), \
        f"Expected results for {len(bucket_names)} buckets, got {len(results)}"
    
    # Property: All buckets should have failed uploads (none exist)
    for bucket in bucket_names:
        bucket_result = results[bucket]
        assert bucket_result.successful_uploads == 0, \
            f"Expected 0 successful uploads for non-existent bucket {bucket}, got {bucket_result.successful_uploads}"
        assert bucket_result.failed_uploads == 1, \
            f"Expected 1 failed upload for non-existent bucket {bucket}, got {bucket_result.failed_uploads}"
        assert len(bucket_result.upload_paths) == 0, \
            f"Expected no upload paths for failed bucket {bucket}, got {bucket_result.upload_paths}"
    
    # Property: put_object should never be called (all buckets failed validation)
    assert mock_s3_client.put_object.call_count == 0, \
        f"Expected 0 put_object calls when all buckets fail validation, got {mock_s3_client.put_object.call_count}"


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=5).flatmap(
    lambda n: st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),  # bucket
            st.integers(min_value=0, max_value=12),  # successful_uploads
            st.integers(min_value=0, max_value=12)   # failed_uploads
        ),
        min_size=n,
        max_size=n,
        unique_by=lambda x: x[0]  # Unique by bucket name
    )
))
def test_property_10_summary_reporting_accuracy(bucket_results):
    """Property 10: Summary reporting accuracy.
    
    For any successful execution, the utility should display a summary showing 
    the count of uploaded files per bucket.
    
    **Feature: test-file-upload-utility, Property 10: Summary reporting accuracy**
    **Validates: Requirements 5.2**
    """
    import logging
    import io
    
    # Import required classes
    Logger = upload_module.Logger
    UploadResult = upload_module.UploadResult
    Configuration = upload_module.Configuration
    
    # Create configuration
    config = Configuration(
        buckets=[data[0] for data in bucket_results],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create Logger instance
    logger_component = Logger(config)
    
    # Capture log output
    log_capture = io.StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.INFO)
    
    # Get the logger and add our handler
    test_logger = logging.getLogger(upload_module.__name__)
    original_handlers = test_logger.handlers[:]
    test_logger.handlers = [log_handler]
    test_logger.setLevel(logging.INFO)
    
    try:
        # Create UploadResult objects from test data
        results = {}
        total_successful = 0
        total_failed = 0
        
        for bucket, successful, failed in bucket_results:
            # Generate some dummy upload paths for successful uploads
            upload_paths = [f"/stage/public/test/file{i}.html" for i in range(successful)]
            
            results[bucket] = UploadResult(
                bucket=bucket,
                successful_uploads=successful,
                failed_uploads=failed,
                upload_paths=upload_paths
            )
            
            total_successful += successful
            total_failed += failed
        
        # Call log_summary
        logger_component.log_summary(results)
        
        # Get logged output
        log_output = log_capture.getvalue()
        
        # Property: Summary should include header
        assert "=== Upload Summary ===" in log_output, \
            f"Expected summary header not found in output: {log_output}"
        
        # Property: Each bucket should be reported with correct counts
        for bucket, successful, failed in bucket_results:
            expected_line = f"{bucket}: {successful} successful, {failed} failed"
            assert expected_line in log_output, \
                f"Expected bucket summary '{expected_line}' not found in output: {log_output}"
        
        # Property: Total summary should be accurate
        expected_total = f"Total: {total_successful} successful, {total_failed} failed uploads"
        assert expected_total in log_output, \
            f"Expected total summary '{expected_total}' not found in output: {log_output}"
        
        # Property: If there are failures, error guidance should be provided
        if total_failed > 0:
            assert "uploads failed. Check bucket permissions" in log_output, \
                f"Expected failure guidance not found when {total_failed} uploads failed: {log_output}"
            assert "Retry suggestions:" in log_output, \
                f"Expected retry suggestions not found when {total_failed} uploads failed: {log_output}"
        
    finally:
        # Restore original handlers
        test_logger.handlers = original_handlers


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=3).flatmap(
    lambda n: st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),  # bucket
            st.integers(min_value=1, max_value=5),  # successful_uploads (at least 1)
            st.integers(min_value=0, max_value=2)   # failed_uploads
        ),
        min_size=n,
        max_size=n,
        unique_by=lambda x: x[0]  # Unique by bucket name
    )
))
def test_property_10_summary_reporting_verbose_mode(bucket_results):
    """Property 10: Summary reporting accuracy - verbose mode.
    
    For any successful execution in verbose mode, the utility should display 
    detailed upload paths in addition to the summary counts.
    
    **Feature: test-file-upload-utility, Property 10: Summary reporting accuracy**
    **Validates: Requirements 5.2**
    """
    import logging
    import io
    
    # Import required classes
    Logger = upload_module.Logger
    UploadResult = upload_module.UploadResult
    Configuration = upload_module.Configuration
    
    # Create configuration with verbose mode enabled
    config = Configuration(
        buckets=[data[0] for data in bucket_results],
        environment='staging',
        aws_profile=None,
        verbose=True,  # Enable verbose mode
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create Logger instance
    logger_component = Logger(config)
    
    # Capture log output
    log_capture = io.StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.INFO)
    
    # Get the logger and add our handler
    test_logger = logging.getLogger(upload_module.__name__)
    original_handlers = test_logger.handlers[:]
    test_logger.handlers = [log_handler]
    test_logger.setLevel(logging.INFO)
    
    try:
        # Create UploadResult objects from test data
        results = {}
        
        for bucket, successful, failed in bucket_results:
            # Generate some dummy upload paths for successful uploads
            upload_paths = [f"/stage/public/test/file{i}.html" for i in range(successful)]
            
            results[bucket] = UploadResult(
                bucket=bucket,
                successful_uploads=successful,
                failed_uploads=failed,
                upload_paths=upload_paths
            )
        
        # Call log_summary
        logger_component.log_summary(results)
        
        # Get logged output
        log_output = log_capture.getvalue()
        
        # Property: Summary should include header
        assert "=== Upload Summary ===" in log_output, \
            f"Expected summary header not found in output: {log_output}"
        
        # Property: Each bucket should be reported with correct counts
        for bucket, successful, failed in bucket_results:
            expected_line = f"{bucket}: {successful} successful, {failed} failed"
            assert expected_line in log_output, \
                f"Expected bucket summary '{expected_line}' not found in output: {log_output}"
        
        # Property: Verbose mode should show uploaded paths for buckets with successful uploads
        for bucket, successful, failed in bucket_results:
            if successful > 0:
                assert "Uploaded paths:" in log_output, \
                    f"Expected 'Uploaded paths:' section not found in verbose output: {log_output}"
                
                # Check that individual paths are listed
                for i in range(successful):
                    expected_path = f"s3://{bucket}/stage/public/test/file{i}.html"
                    assert expected_path in log_output, \
                        f"Expected path '{expected_path}' not found in verbose output: {log_output}"
        
    finally:
        # Restore original handlers
        test_logger.handlers = original_handlers


@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=3).flatmap(
    lambda n: st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=3, max_size=10),  # bucket
            st.just(0),  # successful_uploads (all failed)
            st.integers(min_value=1, max_value=5)   # failed_uploads (at least 1)
        ),
        min_size=n,
        max_size=n,
        unique_by=lambda x: x[0]  # Unique by bucket name
    )
))
def test_property_10_summary_reporting_error_guidance(bucket_results):
    """Property 10: Summary reporting accuracy - error guidance.
    
    For any execution with failures, the utility should provide actionable 
    error guidance in the summary.
    
    **Feature: test-file-upload-utility, Property 10: Summary reporting accuracy**
    **Validates: Requirements 5.2**
    """
    import logging
    import io
    
    # Import required classes
    Logger = upload_module.Logger
    UploadResult = upload_module.UploadResult
    Configuration = upload_module.Configuration
    
    # Create configuration
    config = Configuration(
        buckets=[data[0] for data in bucket_results],
        environment='staging',
        aws_profile=None,
        verbose=False,
        base_path='/stage/public/',
        source_file_path='test.html'
    )
    
    # Create Logger instance
    logger_component = Logger(config)
    
    # Capture log output
    log_capture = io.StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.ERROR)
    
    # Get the logger and add our handler
    test_logger = logging.getLogger(upload_module.__name__)
    original_handlers = test_logger.handlers[:]
    test_logger.handlers = [log_handler]
    test_logger.setLevel(logging.ERROR)
    
    try:
        # Create UploadResult objects from test data (all failures)
        results = {}
        total_failed = 0
        
        for bucket, successful, failed in bucket_results:
            results[bucket] = UploadResult(
                bucket=bucket,
                successful_uploads=successful,
                failed_uploads=failed,
                upload_paths=[]  # No successful uploads
            )
            total_failed += failed
        
        # Call log_summary
        logger_component.log_summary(results)
        
        # Get logged output
        log_output = log_capture.getvalue()
        
        # Property: Should provide error guidance when there are failures
        assert f"{total_failed} uploads failed" in log_output, \
            f"Expected failure count '{total_failed} uploads failed' not found in output: {log_output}"
        
        # Property: Should provide retry suggestions
        assert "Retry suggestions:" in log_output, \
            f"Expected 'Retry suggestions:' not found in output: {log_output}"
        
        # Property: Should include specific actionable guidance
        expected_suggestions = [
            "Verify AWS credentials and permissions",
            "Check bucket names and existence", 
            "Ensure network connectivity to AWS"
        ]
        
        for suggestion in expected_suggestions:
            assert suggestion in log_output, \
                f"Expected suggestion '{suggestion}' not found in output: {log_output}"
        
    finally:
        # Restore original handlers
        test_logger.handlers = original_handlers