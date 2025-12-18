"""Property-based tests for consolidation configuration in tag validator."""

import sys
import os
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st
from botocore.exceptions import ClientError
from functions.processor.tag_validator import (
    get_bucket_consolidation_config,
    validate_consolidation_tag_value,
    get_bucket_tags
)


# Custom strategies for generating test data

@st.composite
def bucket_name_strategy(draw):
    """Generate valid S3 bucket names."""
    # S3 bucket names: 3-63 chars, lowercase letters, numbers, hyphens, dots
    # Must start and end with letter or number
    length = draw(st.integers(min_value=3, max_value=63))
    
    # Start with letter or number
    first_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
    
    # Middle characters can include hyphens and dots
    if length > 2:
        middle_chars = draw(st.text(
            min_size=length - 2,
            max_size=length - 2,
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-.'
        ))
    else:
        middle_chars = ''
    
    # End with letter or number
    if length > 1:
        last_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
    else:
        last_char = ''
    
    bucket_name = first_char + middle_chars + last_char
    
    # Ensure no consecutive dots or dot-dash combinations (S3 rules)
    while '..' in bucket_name or '.-' in bucket_name or '-.' in bucket_name:
        bucket_name = bucket_name.replace('..', '.').replace('.-', '-').replace('-.', '-')
    
    return bucket_name


@st.composite
def valid_threshold_tag_strategy(draw):
    """Generate valid DirectoryConsolidationThreshold tag values (1-1000)."""
    return str(draw(st.integers(min_value=1, max_value=1000)))


@st.composite
def valid_stop_level_tag_strategy(draw):
    """Generate valid ConsolidationStopLevel tag values (0-1000)."""
    return str(draw(st.integers(min_value=0, max_value=1000)))


@st.composite
def invalid_tag_value_strategy(draw):
    """Generate invalid tag values (non-numeric or out of range)."""
    invalid_type = draw(st.sampled_from(['non_numeric', 'negative', 'too_large', 'empty', 'float']))
    
    if invalid_type == 'non_numeric':
        return draw(st.text(
            min_size=1, 
            max_size=20,
            alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+-=[]{}|;:,.<>?'
        ).filter(
            lambda x: not x.isdigit() and not (x.startswith('-') and x[1:].isdigit())
        ))
    elif invalid_type == 'negative':
        return str(draw(st.integers(max_value=-1)))
    elif invalid_type == 'too_large':
        return str(draw(st.integers(min_value=1001)))
    elif invalid_type == 'empty':
        return ''
    elif invalid_type == 'float':
        return str(draw(st.floats(min_value=1.1, max_value=999.9)))


@st.composite
def tags_with_threshold_strategy(draw, threshold_value):
    """Generate tag dictionary with DirectoryConsolidationThreshold."""
    tags = {'invalidator:DirectoryConsolidationThreshold': threshold_value}
    
    # Add some random additional tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=3))
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )).filter(lambda x: not x.startswith('invalidator:')))
        value = draw(st.text(min_size=0, max_size=50))
        tags[key] = value
    
    return tags


@st.composite
def tags_with_stop_level_strategy(draw, stop_level_value):
    """Generate tag dictionary with ConsolidationStopLevel."""
    tags = {'invalidator:ConsolidationStopLevel': stop_level_value}
    
    # Add some random additional tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=3))
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )).filter(lambda x: not x.startswith('invalidator:')))
        value = draw(st.text(min_size=0, max_size=50))
        tags[key] = value
    
    return tags


@st.composite
def tags_with_both_config_strategy(draw, threshold_value, stop_level_value):
    """Generate tag dictionary with both configuration tags."""
    tags = {
        'invalidator:DirectoryConsolidationThreshold': threshold_value,
        'invalidator:ConsolidationStopLevel': stop_level_value
    }
    
    # Add some random additional tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=3))
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )).filter(lambda x: not x.startswith('invalidator:')))
        value = draw(st.text(min_size=0, max_size=50))
        tags[key] = value
    
    return tags


# Property Tests

@settings(max_examples=20)  # Reduced from 100 per testing guidelines
@given(bucket_name_strategy(), valid_threshold_tag_strategy())
def test_property_1_directory_threshold_tag_reading(bucket_name, threshold_value):
    """Property 1: Directory consolidation threshold tag reading.
    
    For any bucket name, when the system reads bucket tags, it should check for
    the invalidator:DirectoryConsolidationThreshold tag and return the tag value if present.
    
    **Feature: dynamic-bucket-consolidation-config, Property 1: Directory consolidation threshold tag reading**
    **Validates: Requirements 1.1**
    """
    tags = {
        'invalidator:DirectoryConsolidationThreshold': threshold_value,
        'AllowInvalidationEvents': 'true'  # Add required tag
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags:
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should read and use the threshold tag value
        expected_threshold = int(threshold_value)
        assert config['directory_threshold'] == expected_threshold, \
            f"Expected threshold {expected_threshold}, got {config['directory_threshold']}"
        assert config['directory_threshold_source'] == 'tag', \
            f"Expected source 'tag', got {config['directory_threshold_source']}"


@settings(max_examples=20)
@given(bucket_name_strategy(), valid_threshold_tag_strategy())
def test_property_2_valid_directory_threshold_usage(bucket_name, threshold_value):
    """Property 2: Valid directory threshold tag usage.
    
    For any bucket with invalidator:DirectoryConsolidationThreshold tag containing
    a value between 1 and 1000, the system should use that value instead of the
    global DIRECTORY_CONSOLIDATION_THRESHOLD.
    
    **Feature: dynamic-bucket-consolidation-config, Property 2: Valid directory threshold tag usage**
    **Validates: Requirements 1.2**
    """
    tags = {
        'invalidator:DirectoryConsolidationThreshold': threshold_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.DIRECTORY_CONSOLIDATION_THRESHOLD', 999):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use tag value instead of global constant
        expected_threshold = int(threshold_value)
        assert config['directory_threshold'] == expected_threshold, \
            f"Expected threshold {expected_threshold}, got {config['directory_threshold']}"
        assert config['directory_threshold_source'] == 'tag', \
            "Should use tag source when valid tag is present"


@settings(max_examples=20)
@given(bucket_name_strategy())
def test_property_3_directory_threshold_fallback(bucket_name):
    """Property 3: Directory threshold fallback behavior.
    
    For any bucket without the invalidator:DirectoryConsolidationThreshold tag,
    the system should use the default DIRECTORY_CONSOLIDATION_THRESHOLD from constants.
    
    **Feature: dynamic-bucket-consolidation-config, Property 3: Directory threshold fallback behavior**
    **Validates: Requirements 1.3**
    """
    tags = {}  # No configuration tags
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.DIRECTORY_CONSOLIDATION_THRESHOLD', 42):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use default value when tag is missing
        assert config['directory_threshold'] == 42, \
            f"Expected default threshold 42, got {config['directory_threshold']}"
        assert config['directory_threshold_source'] == 'default', \
            f"Expected source 'default', got {config['directory_threshold_source']}"


@settings(max_examples=20)
@given(bucket_name_strategy(), invalid_tag_value_strategy())
def test_property_4_invalid_directory_threshold_handling(bucket_name, invalid_value):
    """Property 4: Invalid directory threshold handling.
    
    For any bucket with invalidator:DirectoryConsolidationThreshold tag containing
    an invalid value (outside 1-1000 range or non-numeric), the system should log
    a warning and use the default DIRECTORY_CONSOLIDATION_THRESHOLD.
    
    **Feature: dynamic-bucket-consolidation-config, Property 4: Invalid directory threshold handling**
    **Validates: Requirements 1.4**
    """
    tags = {
        'invalidator:DirectoryConsolidationThreshold': invalid_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.DIRECTORY_CONSOLIDATION_THRESHOLD', 55):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use default value when tag is invalid
        assert config['directory_threshold'] == 55, \
            f"Expected default threshold 55, got {config['directory_threshold']}"
        assert config['directory_threshold_source'] == 'default', \
            f"Expected source 'default', got {config['directory_threshold_source']}"


@settings(max_examples=20)
@given(bucket_name_strategy(), valid_stop_level_tag_strategy())
def test_property_6_stop_level_tag_reading(bucket_name, stop_level_value):
    """Property 6: Consolidation stop level tag reading.
    
    For any bucket name, when the system reads bucket tags, it should check for
    the invalidator:ConsolidationStopLevel tag and return the tag value if present.
    
    **Feature: dynamic-bucket-consolidation-config, Property 6: Consolidation stop level tag reading**
    **Validates: Requirements 2.1**
    """
    tags = {
        'invalidator:ConsolidationStopLevel': stop_level_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags:
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should read and use the stop level tag value
        expected_stop_level = int(stop_level_value)
        assert config['stop_level'] == expected_stop_level, \
            f"Expected stop level {expected_stop_level}, got {config['stop_level']}"
        assert config['stop_level_source'] == 'tag', \
            f"Expected source 'tag', got {config['stop_level_source']}"


@settings(max_examples=20)
@given(bucket_name_strategy(), valid_stop_level_tag_strategy())
def test_property_7_valid_stop_level_usage(bucket_name, stop_level_value):
    """Property 7: Valid stop level tag usage.
    
    For any bucket with invalidator:ConsolidationStopLevel tag containing a value
    between 0 and 1000, the system should use that value as the consolidation stop level.
    
    **Feature: dynamic-bucket-consolidation-config, Property 7: Valid stop level tag usage**
    **Validates: Requirements 2.2**
    """
    tags = {
        'invalidator:ConsolidationStopLevel': stop_level_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.CONSOLIDATION_STOP_LEVEL', 888):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use tag value instead of global constant
        expected_stop_level = int(stop_level_value)
        assert config['stop_level'] == expected_stop_level, \
            f"Expected stop level {expected_stop_level}, got {config['stop_level']}"
        assert config['stop_level'] != 888, \
            "Should not use global constant when valid tag is present"


@settings(max_examples=20)
@given(bucket_name_strategy())
def test_property_8_stop_level_fallback(bucket_name):
    """Property 8: Stop level fallback behavior.
    
    For any bucket without the invalidator:ConsolidationStopLevel tag, the system
    should use the default CONSOLIDATION_STOP_LEVEL constant set to 1.
    
    **Feature: dynamic-bucket-consolidation-config, Property 8: Stop level fallback behavior**
    **Validates: Requirements 2.3**
    """
    tags = {}  # No configuration tags
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.CONSOLIDATION_STOP_LEVEL', 77):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use default value when tag is missing
        assert config['stop_level'] == 77, \
            f"Expected default stop level 77, got {config['stop_level']}"
        assert config['stop_level_source'] == 'default', \
            f"Expected source 'default', got {config['stop_level_source']}"


@settings(max_examples=20)
@given(bucket_name_strategy())
def test_property_15_configuration_logging_completeness(bucket_name):
    """Property 15: Configuration logging completeness.
    
    For any bucket tag reading operation for consolidation configuration, the system
    should log the discovered tag values in valid JSON format.
    
    **Feature: dynamic-bucket-consolidation-config, Property 15: Configuration logging completeness**
    **Validates: Requirements 5.1**
    """
    tags = {
        'invalidator:DirectoryConsolidationThreshold': '5',
        'invalidator:ConsolidationStopLevel': '2'
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.logger') as mock_logger:
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should log configuration discovery
        assert mock_logger.info.called, "Should log configuration information"
        
        # Check that final configuration log contains the expected structure
        final_log_call = None
        for call in mock_logger.info.call_args_list:
            if 'Effective consolidation configuration' in str(call):
                final_log_call = call
                break
        
        assert final_log_call is not None, "Should log effective configuration"
        
        # Verify the log contains the expected fields
        log_extra = final_log_call[1]['extra']['extra_fields']
        assert 'bucket_name' in log_extra
        assert 'directory_threshold' in log_extra
        assert 'stop_level' in log_extra
        assert 'configuration_tags_found' in log_extra


@settings(max_examples=20)
@given(bucket_name_strategy())
def test_property_16_default_value_logging(bucket_name):
    """Property 16: Default value logging.
    
    For any configuration value that uses a default due to missing tags, the system
    should log which default values are being applied.
    
    **Feature: dynamic-bucket-consolidation-config, Property 16: Default value logging**
    **Validates: Requirements 5.2**
    """
    tags = {}  # No configuration tags
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.logger') as mock_logger:
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should log that defaults are being used
        assert mock_logger.info.called, "Should log configuration information"
        
        # Check that final configuration log shows default sources
        final_log_call = None
        for call in mock_logger.info.call_args_list:
            if 'Effective consolidation configuration' in str(call):
                final_log_call = call
                break
        
        assert final_log_call is not None, "Should log effective configuration"
        
        # Verify the log shows default sources
        log_extra = final_log_call[1]['extra']['extra_fields']
        assert log_extra['directory_threshold_source'] == 'default'
        assert log_extra['stop_level_source'] == 'default'


@settings(max_examples=20)
@given(bucket_name_strategy(), invalid_tag_value_strategy())
def test_property_17_invalid_tag_logging(bucket_name, invalid_value):
    """Property 17: Invalid tag value logging.
    
    For any invalid tag value encountered, the system should log a warning containing
    the invalid value and the fallback behavior being applied.
    
    **Feature: dynamic-bucket-consolidation-config, Property 17: Invalid tag value logging**
    **Validates: Requirements 5.3**
    """
    tags = {
        'invalidator:DirectoryConsolidationThreshold': invalid_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.logger') as mock_logger:
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should log warning about invalid tag value
        assert mock_logger.warning.called, "Should log warning for invalid tag value"
        
        # Check that warning contains the invalid value
        warning_logged = False
        for call in mock_logger.warning.call_args_list:
            call_str = str(call)
            if invalid_value in call_str and 'Invalid DirectoryConsolidationThreshold' in call_str:
                warning_logged = True
                break
        
        assert warning_logged, f"Should log warning about invalid value '{invalid_value}'"


@given(
    directory_threshold=st.integers(min_value=1, max_value=1000),
    stop_level=st.integers(min_value=0, max_value=1000),
    aggregation_window=st.integers(min_value=60, max_value=3600)
)
@settings(max_examples=20)  # Reduced iterations per testing guidelines
def test_property_environment_variable_configuration(directory_threshold, stop_level, aggregation_window):
    """
    **Feature: dynamic-bucket-consolidation-config, Property 13: Environment variable configuration**
    **Validates: Requirements 3.5**
    
    Property: For any Lambda function startup, the system should read DIRECTORY_CONSOLIDATION_THRESHOLD,
    CONSOLIDATION_STOP_LEVEL, and AGGREGATION_WINDOW_SECONDS values from environment variables
    set by CloudFormation parameters.
    """
    # Set up environment variables
    env_vars = {
        'DIRECTORY_CONSOLIDATION_THRESHOLD': str(directory_threshold),
        'CONSOLIDATION_STOP_LEVEL': str(stop_level),
        'AGGREGATION_WINDOW_SECONDS': str(aggregation_window)
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        # Import constants module to trigger environment variable reading
        # We need to reload the module to pick up the new environment variables
        if 'common.constants' in sys.modules:
            del sys.modules['common.constants']
        
        from common.constants import (
            DIRECTORY_CONSOLIDATION_THRESHOLD as loaded_threshold,
            CONSOLIDATION_STOP_LEVEL as loaded_stop_level,
            AGGREGATION_WINDOW_SECONDS as loaded_window
        )
        
        # Property: Environment variables should be read and used as constants
        assert loaded_threshold == directory_threshold, f"Expected threshold {directory_threshold}, got {loaded_threshold}"
        assert loaded_stop_level == stop_level, f"Expected stop level {stop_level}, got {loaded_stop_level}"
        assert loaded_window == aggregation_window, f"Expected window {aggregation_window}, got {loaded_window}"