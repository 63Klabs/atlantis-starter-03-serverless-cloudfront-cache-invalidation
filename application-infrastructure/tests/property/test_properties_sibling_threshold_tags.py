"""Property-based tests for sibling directory threshold tag validation."""

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
def valid_sibling_threshold_tag_strategy(draw):
    """Generate valid SiblingDirectoryConsolidationThreshold tag values (1-1000)."""
    return str(draw(st.integers(min_value=1, max_value=1000)))


@st.composite
def valid_stop_level_tag_strategy(draw):
    """Generate valid ConsolidationStopLevel tag values (0-20)."""
    return str(draw(st.integers(min_value=0, max_value=20)))


@st.composite
def invalid_sibling_threshold_tag_strategy(draw):
    """Generate invalid sibling threshold tag values (non-numeric or out of range)."""
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
        return str(draw(st.integers(max_value=0)))
    elif invalid_type == 'too_large':
        return str(draw(st.integers(min_value=1001)))
    elif invalid_type == 'empty':
        return ''
    elif invalid_type == 'float':
        return str(draw(st.floats(min_value=1.1, max_value=999.9)))


@st.composite
def invalid_stop_level_tag_strategy(draw):
    """Generate invalid ConsolidationStopLevel tag values (out of new 0-20 range)."""
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
        return str(draw(st.integers(min_value=21)))  # Above new max of 20
    elif invalid_type == 'empty':
        return ''
    elif invalid_type == 'float':
        return str(draw(st.floats(min_value=1.1, max_value=19.9)))


# Property Tests

@settings(max_examples=10)  # Minimal iterations per testing guidelines
@given(bucket_name_strategy(), valid_sibling_threshold_tag_strategy())
def test_property_4_bucket_tag_reading(bucket_name, sibling_threshold_value):
    """Property 4: Bucket tag reading.
    
    For any bucket with the invalidator:SiblingDirectoryConsolidationThreshold tag,
    the system should read and attempt to validate the tag value.
    
    **Feature: sibling-directory-consolidation-threshold, Property 4: Bucket tag reading**
    **Validates: Requirements 2.1**
    """
    tags = {
        'invalidator:SiblingDirectoryConsolidationThreshold': sibling_threshold_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags:
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should read and use the sibling threshold tag value
        expected_threshold = int(sibling_threshold_value)
        assert config['sibling_directory_threshold'] == expected_threshold, \
            f"Expected sibling threshold {expected_threshold}, got {config['sibling_directory_threshold']}"
        assert config['sibling_directory_threshold_source'] == 'tag', \
            f"Expected source 'tag', got {config['sibling_directory_threshold_source']}"


@settings(max_examples=10)
@given(bucket_name_strategy(), valid_sibling_threshold_tag_strategy())
def test_property_5_valid_tag_value_usage(bucket_name, sibling_threshold_value):
    """Property 5: Valid tag value usage.
    
    For any bucket with a valid invalidator:SiblingDirectoryConsolidationThreshold tag value (1-1000),
    the system should use that value instead of the default threshold.
    
    **Feature: sibling-directory-consolidation-threshold, Property 5: Valid tag value usage**
    **Validates: Requirements 2.2**
    """
    tags = {
        'invalidator:SiblingDirectoryConsolidationThreshold': sibling_threshold_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD', 999):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use tag value instead of global constant
        expected_threshold = int(sibling_threshold_value)
        assert config['sibling_directory_threshold'] == expected_threshold, \
            f"Expected sibling threshold {expected_threshold}, got {config['sibling_directory_threshold']}"
        assert config['sibling_directory_threshold'] != 999, \
            "Should not use global constant when valid tag is present"
        assert config['sibling_directory_threshold_source'] == 'tag', \
            "Should use tag source when valid tag is present"


@settings(max_examples=10)
@given(bucket_name_strategy(), invalid_sibling_threshold_tag_strategy())
def test_property_6_invalid_tag_value_handling(bucket_name, invalid_value):
    """Property 6: Invalid tag value handling.
    
    For any bucket with an invalid invalidator:SiblingDirectoryConsolidationThreshold tag value,
    the system should log a warning and use the default threshold.
    
    **Feature: sibling-directory-consolidation-threshold, Property 6: Invalid tag value handling**
    **Validates: Requirements 2.3**
    """
    tags = {
        'invalidator:SiblingDirectoryConsolidationThreshold': invalid_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD', 55), \
         patch('functions.processor.tag_validator.logger') as mock_logger:
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use default value when tag is invalid
        assert config['sibling_directory_threshold'] == 55, \
            f"Expected default sibling threshold 55, got {config['sibling_directory_threshold']}"
        assert config['sibling_directory_threshold_source'] == 'default', \
            f"Expected source 'default', got {config['sibling_directory_threshold_source']}"
        
        # Property: Should log warning about invalid tag value
        assert mock_logger.warning.called, "Should log warning for invalid tag value"


@settings(max_examples=10)
@given(bucket_name_strategy())
def test_property_7_missing_tag_fallback(bucket_name):
    """Property 7: Missing tag fallback.
    
    For any bucket without the invalidator:SiblingDirectoryConsolidationThreshold tag,
    the system should use the default threshold from the environment variable.
    
    **Feature: sibling-directory-consolidation-threshold, Property 7: Missing tag fallback**
    **Validates: Requirements 2.4**
    """
    tags = {}  # No sibling threshold tag
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD', 42):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use default value when tag is missing
        assert config['sibling_directory_threshold'] == 42, \
            f"Expected default sibling threshold 42, got {config['sibling_directory_threshold']}"
        assert config['sibling_directory_threshold_source'] == 'default', \
            f"Expected source 'default', got {config['sibling_directory_threshold_source']}"


@settings(max_examples=10)
@given(bucket_name_strategy(), valid_sibling_threshold_tag_strategy())
def test_property_8_configuration_priority_resolution(bucket_name, sibling_threshold_value):
    """Property 8: Configuration priority resolution.
    
    For any bucket with both tag and parameter configurations, the tag value should
    take precedence over the parameter value.
    
    **Feature: sibling-directory-consolidation-threshold, Property 8: Configuration priority resolution**
    **Validates: Requirements 3.1**
    """
    tags = {
        'invalidator:SiblingDirectoryConsolidationThreshold': sibling_threshold_value
    }
    
    # Set a different default value to ensure tag takes precedence
    different_default = int(sibling_threshold_value) + 100 if int(sibling_threshold_value) < 900 else int(sibling_threshold_value) - 100
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD', different_default):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Tag value should take precedence over parameter/default value
        expected_threshold = int(sibling_threshold_value)
        assert config['sibling_directory_threshold'] == expected_threshold, \
            f"Expected tag value {expected_threshold}, got {config['sibling_directory_threshold']}"
        assert config['sibling_directory_threshold'] != different_default, \
            f"Tag value should override default {different_default}"
        assert config['sibling_directory_threshold_source'] == 'tag', \
            "Should indicate tag as the source when tag is present"


@settings(max_examples=10)
@given(bucket_name_strategy())
def test_property_9_parameter_fallback_behavior(bucket_name):
    """Property 9: Parameter fallback behavior.
    
    For any bucket with missing or invalid tags, the system should use the
    CloudFormation parameter value as the fallback.
    
    **Feature: sibling-directory-consolidation-threshold, Property 9: Parameter fallback behavior**
    **Validates: Requirements 3.2**
    """
    tags = {}  # No tags
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD', 77):
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should use parameter/default value when tags are missing
        assert config['sibling_directory_threshold'] == 77, \
            f"Expected parameter value 77, got {config['sibling_directory_threshold']}"
        assert config['sibling_directory_threshold_source'] == 'default', \
            f"Expected source 'default', got {config['sibling_directory_threshold_source']}"


@settings(max_examples=10)
@given(bucket_name_strategy(), valid_sibling_threshold_tag_strategy())
def test_property_10_configuration_source_logging(bucket_name, sibling_threshold_value):
    """Property 10: Configuration source logging.
    
    For any configuration resolution, the system should log the source of each
    configuration value (tag, parameter, or default).
    
    **Feature: sibling-directory-consolidation-threshold, Property 10: Configuration source logging**
    **Validates: Requirements 3.4**
    """
    tags = {
        'invalidator:SiblingDirectoryConsolidationThreshold': sibling_threshold_value
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.logger') as mock_logger:
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Should log configuration source information
        assert mock_logger.info.called, "Should log configuration information"
        
        # Check that final configuration log contains the expected structure
        final_log_call = None
        for call in mock_logger.info.call_args_list:
            if 'Effective consolidation configuration' in str(call):
                final_log_call = call
                break
        
        assert final_log_call is not None, "Should log effective configuration"
        
        # Verify the log contains the sibling threshold fields
        log_extra = final_log_call[1]['extra']['extra_fields']
        assert 'sibling_directory_threshold' in log_extra
        assert 'sibling_directory_threshold_source' in log_extra
        assert 'configuration_tags_found' in log_extra
        assert 'SiblingDirectoryConsolidationThreshold' in log_extra['configuration_tags_found']


@settings(max_examples=10)
@given(bucket_name_strategy(), invalid_stop_level_tag_strategy())
def test_property_12_consolidation_stop_level_tag_validation(bucket_name, invalid_stop_level):
    """Property 12: ConsolidationStopLevel tag validation.
    
    For any invalidator:ConsolidationStopLevel tag value, the system should accept
    values between 0 and 20 inclusive and reject values outside this range.
    
    **Feature: sibling-directory-consolidation-threshold, Property 12: ConsolidationStopLevel tag validation**
    **Validates: Requirements 4.2**
    """
    tags = {
        'invalidator:ConsolidationStopLevel': invalid_stop_level
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags, \
         patch('functions.processor.tag_validator.CONSOLIDATION_STOP_LEVEL', 1), \
         patch('functions.processor.tag_validator.logger') as mock_logger:
        
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Invalid values should fall back to default
        assert config['stop_level'] == 1, \
            f"Expected default stop level 1 for invalid value '{invalid_stop_level}', got {config['stop_level']}"
        assert config['stop_level_source'] == 'default', \
            f"Expected source 'default', got {config['stop_level_source']}"
        
        # Property: Should log warning about invalid tag value
        assert mock_logger.warning.called, "Should log warning for invalid tag value"


@settings(max_examples=10)
@given(bucket_name_strategy(), valid_stop_level_tag_strategy())
def test_property_consolidation_stop_level_valid_range(bucket_name, valid_stop_level):
    """Test that valid ConsolidationStopLevel tag values (0-20) are accepted.
    
    **Feature: sibling-directory-consolidation-threshold, Property 12: ConsolidationStopLevel tag validation**
    **Validates: Requirements 4.2**
    """
    tags = {
        'invalidator:ConsolidationStopLevel': valid_stop_level
    }
    
    with patch('functions.processor.tag_validator.get_bucket_tags') as mock_get_tags:
        mock_get_tags.return_value = tags
        
        config = get_bucket_consolidation_config(bucket_name)
        
        # Property: Valid values should be used as-is
        expected_stop_level = int(valid_stop_level)
        assert config['stop_level'] == expected_stop_level, \
            f"Expected stop level {expected_stop_level}, got {config['stop_level']}"
        assert config['stop_level_source'] == 'tag', \
            f"Expected source 'tag', got {config['stop_level_source']}"