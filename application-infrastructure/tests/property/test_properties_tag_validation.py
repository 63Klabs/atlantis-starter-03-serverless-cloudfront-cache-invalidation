"""Property-based tests for tag validation functions."""

import pytest
from hypothesis import given, strategies as st, assume

from functions.processor.tag_validator import (
    validate_bucket_tags_from_dict,
    get_bucket_consolidation_config_from_dict,
    validate_consolidation_tag_value
)


class TestValidateBucketTagsFromDictProperties:
    """Property-based tests for validate_bucket_tags_from_dict."""
    
    @given(st.dictionaries(st.text(), st.text()))
    def test_never_crashes_with_any_dict(self, tags):
        """Property: Validation never crashes regardless of input dictionary."""
        result = validate_bucket_tags_from_dict(tags)
        assert isinstance(result, bool)
    
    @given(st.text())
    def test_only_exact_true_string_validates(self, value):
        """Property: Only the exact string 'true' validates successfully."""
        tags = {'AllowInvalidationEvents': value}
        result = validate_bucket_tags_from_dict(tags)
        
        if value == 'true':
            assert result is True
        else:
            assert result is False
    
    @given(st.dictionaries(st.text(min_size=1), st.text()))
    def test_missing_required_tag_always_fails(self, tags):
        """Property: Missing AllowInvalidationEvents tag always fails validation."""
        # Ensure the required tag is not present
        assume('AllowInvalidationEvents' not in tags)
        
        result = validate_bucket_tags_from_dict(tags)
        assert result is False
    
    def test_none_input_always_fails(self):
        """Property: None input always fails validation."""
        result = validate_bucket_tags_from_dict(None)
        assert result is False


class TestGetBucketConsolidationConfigFromDictProperties:
    """Property-based tests for get_bucket_consolidation_config_from_dict."""
    
    @given(st.dictionaries(st.text(), st.text()), st.text())
    def test_never_crashes_with_any_input(self, tags, bucket_name):
        """Property: Config extraction never crashes regardless of input."""
        config = get_bucket_consolidation_config_from_dict(tags, bucket_name)
        
        # Always returns a dict with required keys
        assert isinstance(config, dict)
        assert 'directory_threshold' in config
        assert 'stop_level' in config
        assert 'sibling_directory_threshold' in config
        assert 'directory_threshold_source' in config
        assert 'stop_level_source' in config
        assert 'sibling_directory_threshold_source' in config
    
    @given(st.text())
    def test_none_tags_always_returns_defaults(self, bucket_name):
        """Property: None tags always returns default configuration."""
        config = get_bucket_consolidation_config_from_dict(None, bucket_name)
        
        assert config['directory_threshold'] == 3
        assert config['stop_level'] == 1
        assert config['sibling_directory_threshold'] == 10
        assert config['directory_threshold_source'] == 'default'
        assert config['stop_level_source'] == 'default'
        assert config['sibling_directory_threshold_source'] == 'default'
    
    @given(st.integers(min_value=1, max_value=1000))
    def test_valid_threshold_tag_is_used(self, threshold_value):
        """Property: Valid threshold values are used from tags."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': str(threshold_value)
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == threshold_value
        assert config['directory_threshold_source'] == 'tag'
    
    @given(st.integers(min_value=0, max_value=20))
    def test_valid_stop_level_tag_is_used(self, stop_level_value):
        """Property: Valid stop level values are used from tags."""
        tags = {
            'invalidator:ConsolidationStopLevel': str(stop_level_value)
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['stop_level'] == stop_level_value
        assert config['stop_level_source'] == 'tag'
    
    @given(st.integers(min_value=1, max_value=1000))
    def test_valid_sibling_threshold_tag_is_used(self, sibling_threshold_value):
        """Property: Valid sibling threshold values are used from tags."""
        tags = {
            'invalidator:SiblingDirectoryConsolidationThreshold': str(sibling_threshold_value)
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['sibling_directory_threshold'] == sibling_threshold_value
        assert config['sibling_directory_threshold_source'] == 'tag'
    
    @given(st.integers().filter(lambda x: x < 1 or x > 1000))
    def test_invalid_threshold_falls_back_to_default(self, invalid_value):
        """Property: Out-of-range threshold values fall back to defaults."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': str(invalid_value)
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 3  # Default
        assert config['directory_threshold_source'] == 'default'
    
    @given(st.integers().filter(lambda x: x < 0 or x > 20))
    def test_invalid_stop_level_falls_back_to_default(self, invalid_value):
        """Property: Out-of-range stop level values fall back to defaults."""
        tags = {
            'invalidator:ConsolidationStopLevel': str(invalid_value)
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['stop_level'] == 1  # Default
        assert config['stop_level_source'] == 'default'
    
    @given(st.text().filter(lambda x: not x.isdigit()))
    def test_non_numeric_threshold_falls_back_to_default(self, non_numeric):
        """Property: Non-numeric threshold values fall back to defaults."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': non_numeric
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 3  # Default
        assert config['directory_threshold_source'] == 'default'


class TestValidateConsolidationTagValueProperties:
    """Property-based tests for validate_consolidation_tag_value."""
    
    @given(st.text())
    def test_never_crashes_with_any_string(self, value):
        """Property: Validation never crashes with any string input."""
        result = validate_consolidation_tag_value(value, 1, 1000)
        
        # Result is either None or an integer in range
        if result is not None:
            assert isinstance(result, int)
            assert 1 <= result <= 1000
    
    @given(st.integers(min_value=1, max_value=1000))
    def test_valid_integers_are_accepted(self, value):
        """Property: Valid integer strings are accepted."""
        result = validate_consolidation_tag_value(str(value), 1, 1000)
        
        assert result == value
    
    @given(st.integers().filter(lambda x: x < 1 or x > 1000))
    def test_out_of_range_integers_are_rejected(self, value):
        """Property: Out-of-range integer strings are rejected."""
        result = validate_consolidation_tag_value(str(value), 1, 1000)
        
        assert result is None
    
    @given(st.text().filter(lambda x: not x.lstrip('-').isdigit()))
    def test_non_numeric_strings_are_rejected(self, value):
        """Property: Non-numeric strings are rejected."""
        result = validate_consolidation_tag_value(value, 1, 1000)
        
        assert result is None
    
    @given(st.integers(min_value=0, max_value=20))
    def test_stop_level_range_validation(self, value):
        """Property: Stop level range (0-20) is validated correctly."""
        result = validate_consolidation_tag_value(str(value), 0, 20)
        
        assert result == value
    
    @given(st.integers().filter(lambda x: x < 0 or x > 20))
    def test_stop_level_out_of_range_rejected(self, value):
        """Property: Stop level values outside 0-20 are rejected."""
        result = validate_consolidation_tag_value(str(value), 0, 20)
        
        assert result is None


class TestEquivalenceProperties:
    """Property-based tests for equivalence with original functions."""
    
    @given(st.dictionaries(st.text(), st.text()))
    def test_validation_result_is_deterministic(self, tags):
        """Property: Validation produces same result when called multiple times."""
        result1 = validate_bucket_tags_from_dict(tags)
        result2 = validate_bucket_tags_from_dict(tags)
        
        assert result1 == result2
    
    @given(st.dictionaries(st.text(), st.text()), st.text())
    def test_config_extraction_is_deterministic(self, tags, bucket_name):
        """Property: Config extraction produces same result when called multiple times."""
        config1 = get_bucket_consolidation_config_from_dict(tags, bucket_name)
        config2 = get_bucket_consolidation_config_from_dict(tags, bucket_name)
        
        assert config1 == config2
    
    @given(st.dictionaries(st.text(), st.text()))
    def test_validation_is_pure_function(self, tags):
        """Property: Validation doesn't modify input dictionary."""
        original_tags = tags.copy()
        validate_bucket_tags_from_dict(tags)
        
        assert tags == original_tags
    
    @given(st.dictionaries(st.text(), st.text()), st.text())
    def test_config_extraction_is_pure_function(self, tags, bucket_name):
        """Property: Config extraction doesn't modify input dictionary."""
        original_tags = tags.copy()
        get_bucket_consolidation_config_from_dict(tags, bucket_name)
        
        assert tags == original_tags
