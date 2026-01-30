"""Unit tests for tag_validator module - new _from_dict functions."""

import pytest
from unittest.mock import patch, MagicMock

from functions.processor.tag_validator import (
    validate_bucket_tags_from_dict,
    get_bucket_consolidation_config_from_dict
)


class TestValidateBucketTagsFromDict:
    """Tests for validate_bucket_tags_from_dict function."""
    
    def test_valid_tags_returns_true(self):
        """Test validation with valid AllowInvalidationEvents tag."""
        tags = {'AllowInvalidationEvents': 'true'}
        
        result = validate_bucket_tags_from_dict(tags)
        
        assert result is True
    
    def test_invalid_tag_value_returns_false(self):
        """Test validation with invalid tag value."""
        tags = {'AllowInvalidationEvents': 'false'}
        
        result = validate_bucket_tags_from_dict(tags)
        
        assert result is False
    
    def test_none_input_returns_false(self):
        """Test validation with None input."""
        result = validate_bucket_tags_from_dict(None)
        
        assert result is False
    
    def test_missing_tag_returns_false(self):
        """Test validation with missing AllowInvalidationEvents tag."""
        tags = {'SomeOtherTag': 'value'}
        
        result = validate_bucket_tags_from_dict(tags)
        
        assert result is False
    
    def test_empty_dict_returns_false(self):
        """Test validation with empty tag dictionary."""
        tags = {}
        
        result = validate_bucket_tags_from_dict(tags)
        
        assert result is False
    
    def test_case_sensitive_tag_value(self):
        """Test that tag value is case-sensitive."""
        tags = {'AllowInvalidationEvents': 'True'}  # Capital T
        
        result = validate_bucket_tags_from_dict(tags)
        
        assert result is False
    
    def test_whitespace_in_tag_value(self):
        """Test that whitespace in tag value causes failure."""
        tags = {'AllowInvalidationEvents': ' true '}
        
        result = validate_bucket_tags_from_dict(tags)
        
        assert result is False




class TestGetBucketConsolidationConfigFromDict:
    """Tests for get_bucket_consolidation_config_from_dict function."""
    
    def test_with_all_valid_tags(self):
        """Test config extraction with all valid tags."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '5',
            'invalidator:ConsolidationStopLevel': '2',
            'invalidator:SiblingDirectoryConsolidationThreshold': '15'
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 5
        assert config['stop_level'] == 2
        assert config['sibling_directory_threshold'] == 15
        assert config['directory_threshold_source'] == 'tag'
        assert config['stop_level_source'] == 'tag'
        assert config['sibling_directory_threshold_source'] == 'tag'
    
    def test_with_no_tags_uses_defaults(self):
        """Test config extraction with empty tag dictionary."""
        tags = {}
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should use default values from constants
        assert config['directory_threshold'] == 3  # DIRECTORY_CONSOLIDATION_THRESHOLD
        assert config['stop_level'] == 1  # CONSOLIDATION_STOP_LEVEL
        assert config['sibling_directory_threshold'] == 10  # SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD
        assert config['directory_threshold_source'] == 'default'
        assert config['stop_level_source'] == 'default'
        assert config['sibling_directory_threshold_source'] == 'default'
    
    def test_with_none_input_uses_defaults(self):
        """Test config extraction with None input."""
        config = get_bucket_consolidation_config_from_dict(None, 'test-bucket')
        
        # Should use default values
        assert config['directory_threshold'] == 3
        assert config['stop_level'] == 1
        assert config['sibling_directory_threshold'] == 10
        assert config['directory_threshold_source'] == 'default'
        assert config['stop_level_source'] == 'default'
        assert config['sibling_directory_threshold_source'] == 'default'
    
    def test_with_partial_tags(self):
        """Test config extraction with only some tags present."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '7'
            # Missing other tags
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 7
        assert config['directory_threshold_source'] == 'tag'
        assert config['stop_level'] == 1  # Default
        assert config['stop_level_source'] == 'default'
        assert config['sibling_directory_threshold'] == 10  # Default
        assert config['sibling_directory_threshold_source'] == 'default'
    
    def test_with_invalid_threshold_value(self):
        """Test config extraction with invalid threshold value."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': 'invalid'
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should fall back to default
        assert config['directory_threshold'] == 3
        assert config['directory_threshold_source'] == 'default'
    
    def test_with_out_of_range_threshold(self):
        """Test config extraction with out-of-range threshold value."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '2000'  # Max is 1000
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should fall back to default
        assert config['directory_threshold'] == 3
        assert config['directory_threshold_source'] == 'default'
    
    def test_with_negative_threshold(self):
        """Test config extraction with negative threshold value."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '-5'
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should fall back to default
        assert config['directory_threshold'] == 3
        assert config['directory_threshold_source'] == 'default'
    
    def test_with_invalid_stop_level(self):
        """Test config extraction with invalid stop level value."""
        tags = {
            'invalidator:ConsolidationStopLevel': 'not_a_number'
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should fall back to default
        assert config['stop_level'] == 1
        assert config['stop_level_source'] == 'default'
    
    def test_with_out_of_range_stop_level(self):
        """Test config extraction with out-of-range stop level."""
        tags = {
            'invalidator:ConsolidationStopLevel': '25'  # Max is 20
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should fall back to default
        assert config['stop_level'] == 1
        assert config['stop_level_source'] == 'default'
    
    def test_with_invalid_sibling_threshold(self):
        """Test config extraction with invalid sibling threshold."""
        tags = {
            'invalidator:SiblingDirectoryConsolidationThreshold': 'abc'
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        # Should fall back to default
        assert config['sibling_directory_threshold'] == 10
        assert config['sibling_directory_threshold_source'] == 'default'
    
    def test_with_mixed_valid_and_invalid_tags(self):
        """Test config extraction with mix of valid and invalid tags."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '8',  # Valid
            'invalidator:ConsolidationStopLevel': 'invalid',  # Invalid
            'invalidator:SiblingDirectoryConsolidationThreshold': '20'  # Valid
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 8
        assert config['directory_threshold_source'] == 'tag'
        assert config['stop_level'] == 1  # Default due to invalid
        assert config['stop_level_source'] == 'default'
        assert config['sibling_directory_threshold'] == 20
        assert config['sibling_directory_threshold_source'] == 'tag'
    
    def test_with_boundary_values(self):
        """Test config extraction with boundary values."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '1',  # Min valid
            'invalidator:ConsolidationStopLevel': '0',  # Min valid
            'invalidator:SiblingDirectoryConsolidationThreshold': '1000'  # Max valid
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 1
        assert config['stop_level'] == 0
        assert config['sibling_directory_threshold'] == 1000
        assert config['directory_threshold_source'] == 'tag'
        assert config['stop_level_source'] == 'tag'
        assert config['sibling_directory_threshold_source'] == 'tag'
    
    def test_with_extra_tags_ignored(self):
        """Test that extra unrelated tags are ignored."""
        tags = {
            'invalidator:DirectoryConsolidationThreshold': '5',
            'SomeOtherTag': 'value',
            'AnotherTag': '123'
        }
        
        config = get_bucket_consolidation_config_from_dict(tags, 'test-bucket')
        
        assert config['directory_threshold'] == 5
        assert config['directory_threshold_source'] == 'tag'
        # Other tags should not affect defaults
        assert config['stop_level'] == 1
        assert config['sibling_directory_threshold'] == 10
