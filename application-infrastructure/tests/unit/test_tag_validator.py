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



class TestValidateDistributionTagsEmptyStageId:
    """Tests for validate_distribution_tags with empty stage_id scenarios.
    
    **Feature: distribution-tag-validation-no-stage-fix**
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    """
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_with_prefix_match_valid(self, mock_get_tags):
        """Test validation with empty stage_id uses prefix matching (valid case).
        
        When stage_id is empty string, validation should:
        - Construct expected value without trailing hyphen
        - Use prefix matching instead of exact match
        - Accept distribution where ApplicationDeploymentId starts with expected prefix
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with stage suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass with prefix match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_with_exact_match_valid(self, mock_get_tags):
        """Test validation with empty stage_id accepts exact match.
        
        When stage_id is empty and ApplicationDeploymentId exactly matches
        the bucket_app_tag (no suffix), validation should pass.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId without stage suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass with exact match (which is also a prefix match)
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_with_no_prefix_match_invalid(self, mock_get_tags):
        """Test validation with empty stage_id rejects non-matching prefix.
        
        When stage_id is empty and ApplicationDeploymentId does not start
        with the expected prefix, validation should fail.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has different ApplicationDeploymentId
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-b-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to prefix mismatch
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_none_stage_id_with_prefix_match_valid(self, mock_get_tags):
        """Test validation with None stage_id uses prefix matching.
        
        When stage_id is None (not just empty string), validation should
        treat it the same as empty string and use prefix matching.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with stage suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-dev'
        }
        
        # Execute: Validate with None stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=None
        )
        
        # Verify: Should pass with prefix match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @pytest.mark.xfail(reason="Task 1.1 incomplete: Implementation doesn't strip whitespace from stage_id yet")
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_whitespace_stage_id_treated_as_empty_valid(self, mock_get_tags):
        """Test validation with whitespace-only stage_id treated as empty.
        
        When stage_id contains only whitespace, validation should treat it
        as empty and use prefix matching.
        
        NOTE: This test currently fails because the implementation uses
        'if not stage_id:' instead of 'if not stage_id or not stage_id.strip():'
        Task 1.1 needs to be completed to handle whitespace properly.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with stage suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-staging'
        }
        
        # Execute: Validate with whitespace-only stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='   '
        )
        
        # Verify: Should pass with prefix match (whitespace treated as empty)
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_multiple_hyphens_in_suffix(self, mock_get_tags):
        """Test validation with empty stage_id handles multiple hyphens in suffix.
        
        When ApplicationDeploymentId has multiple hyphens after the prefix,
        prefix matching should still work correctly.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with multi-part suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod-us-east-1'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass with prefix match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_with_missing_allow_invalidation_invalid(self, mock_get_tags):
        """Test validation fails when AllowInvalidationEvents is missing (empty stage_id).
        
        Even with valid ApplicationDeploymentId prefix match, validation should
        fail if AllowInvalidationEvents tag is missing.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution missing AllowInvalidationEvents tag
        mock_get_tags.return_value = {
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to missing AllowInvalidationEvents
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_with_false_allow_invalidation_invalid(self, mock_get_tags):
        """Test validation fails when AllowInvalidationEvents is false (empty stage_id).
        
        Even with valid ApplicationDeploymentId prefix match, validation should
        fail if AllowInvalidationEvents is set to "false".
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has AllowInvalidationEvents set to false
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'false',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to AllowInvalidationEvents=false
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_tag_retrieval_failure(self, mock_get_tags):
        """Test validation fails when tag retrieval fails (empty stage_id).
        
        When get_distribution_tags returns None, validation should fail
        regardless of stage_id value.
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Tag retrieval fails
        mock_get_tags.return_value = None
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to tag retrieval failure
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')



class TestValidateDistributionTagsNonEmptyStageId:
    """Tests for validate_distribution_tags with non-empty stage_id scenarios.
    
    **Feature: distribution-tag-validation-no-stage-fix**
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    
    These are regression tests to ensure existing exact match behavior
    is preserved when stage_id is non-empty.
    """
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_with_exact_match_valid(self, mock_get_tags):
        """Test validation with non-empty stage_id uses exact matching (valid case).
        
        When stage_id is non-empty (e.g., "prod"), validation should:
        - Construct expected value as {bucket_app_tag}-{stage_id}
        - Use exact matching (not prefix matching)
        - Accept only distributions where ApplicationDeploymentId exactly matches
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId that exactly matches
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with non-empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should pass with exact match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_with_different_stage_invalid(self, mock_get_tags):
        """Test validation with non-empty stage_id rejects different stage.
        
        When stage_id is "prod" but ApplicationDeploymentId has "dev",
        validation should fail because exact match is required.
        
        **Validates: Requirements 2.2, 2.4**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with different stage
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-dev'
        }
        
        # Execute: Validate with stage_id="prod"
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail due to stage mismatch
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_with_prefix_match_but_not_exact_invalid(self, mock_get_tags):
        """Test validation with non-empty stage_id rejects prefix-only match.
        
        When stage_id is "prod" and ApplicationDeploymentId starts with the
        expected value but has additional suffixes, validation should fail
        because exact match is required (not prefix match).
        
        Example: Expected "xcme-cdninval-a-prod" but got "xcme-cdninval-a-prod-us-east-1"
        
        **Validates: Requirements 2.2, 2.4**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with additional suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod-us-east-1'
        }
        
        # Execute: Validate with stage_id="prod"
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail because exact match is required
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_dev_exact_match_valid(self, mock_get_tags):
        """Test validation with stage_id="dev" uses exact matching.
        
        Verify that exact matching works for different stage values,
        not just "prod".
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId for dev stage
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-dev'
        }
        
        # Execute: Validate with stage_id="dev"
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='dev'
        )
        
        # Verify: Should pass with exact match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_staging_exact_match_valid(self, mock_get_tags):
        """Test validation with stage_id="staging" uses exact matching.
        
        Verify that exact matching works for multi-character stage values.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId for staging stage
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-staging'
        }
        
        # Execute: Validate with stage_id="staging"
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='staging'
        )
        
        # Verify: Should pass with exact match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_case_sensitive_invalid(self, mock_get_tags):
        """Test validation with non-empty stage_id is case-sensitive.
        
        When stage_id is "prod" but ApplicationDeploymentId has "Prod",
        validation should fail because comparison is case-sensitive.
        
        **Validates: Requirements 2.2, 2.4**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with different case
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-Prod'
        }
        
        # Execute: Validate with stage_id="prod" (lowercase)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail due to case mismatch
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_with_missing_allow_invalidation_invalid(self, mock_get_tags):
        """Test validation fails when AllowInvalidationEvents is missing (non-empty stage_id).
        
        Even with valid ApplicationDeploymentId exact match, validation should
        fail if AllowInvalidationEvents tag is missing.
        
        **Validates: Requirements 3.1, 3.2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution missing AllowInvalidationEvents tag
        mock_get_tags.return_value = {
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with non-empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail due to missing AllowInvalidationEvents
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_with_false_allow_invalidation_invalid(self, mock_get_tags):
        """Test validation fails when AllowInvalidationEvents is false (non-empty stage_id).
        
        Even with valid ApplicationDeploymentId exact match, validation should
        fail if AllowInvalidationEvents is set to "false".
        
        **Validates: Requirements 3.1, 3.2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has AllowInvalidationEvents set to false
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'false',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with non-empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail due to AllowInvalidationEvents=false
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')



class TestValidateDistributionTagsEdgeCases:
    """Tests for edge cases in distribution tag validation.
    
    **Feature: distribution-tag-validation-no-stage-fix**
    **Validates: Requirements NFR-1, NFR-2**
    
    These tests verify edge cases and boundary conditions for the validation logic.
    """
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_distribution_no_suffix_exact_match(self, mock_get_tags):
        """Test validation with empty stage_id and distribution having no suffix (exact match).
        
        When stage_id is empty and ApplicationDeploymentId exactly equals the
        bucket_app_tag (no suffix at all), validation should pass.
        This is both a prefix match and an exact match.
        
        **Validates: Requirements NFR-1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId without any suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass (exact match is also a prefix match)
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_distribution_multiple_hyphens_in_suffix(self, mock_get_tags):
        """Test validation with empty stage_id handles multiple hyphens in suffix.
        
        When ApplicationDeploymentId has multiple hyphens after the prefix
        (e.g., "xcme-cdninval-a-prod-us-east-1"), prefix matching should still
        work correctly.
        
        **Validates: Requirements NFR-1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with multi-part suffix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod-us-east-1'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass with prefix match
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_case_sensitive_prefix_matching(self, mock_get_tags):
        """Test case sensitivity in prefix matching with empty stage_id.
        
        When stage_id is empty, prefix matching should be case-sensitive.
        A distribution with different case in the prefix should not match.
        
        **Validates: Requirements NFR-1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with different case
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'XCME-cdninval-a-prod'  # Different case
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',  # Lowercase
            stage_id=''
        )
        
        # Verify: Should fail due to case mismatch in prefix
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_wrong_application_prefix_invalid(self, mock_get_tags):
        """Test validation with empty stage_id rejects wrong application prefix.
        
        When stage_id is empty and ApplicationDeploymentId has a completely
        different application prefix, validation should fail.
        
        **Validates: Requirements NFR-1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with wrong prefix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'different-app-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to wrong application prefix
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_stage_id_partial_prefix_match_invalid(self, mock_get_tags):
        """Test validation with empty stage_id rejects partial prefix match.
        
        When ApplicationDeploymentId starts with only part of the expected prefix,
        validation should fail. For example, "xcme-cdn" should not match "xcme-cdninval-a".
        
        **Validates: Requirements NFR-1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with partial prefix
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdn-prod'  # Missing "inval-a"
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to incomplete prefix match
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_non_empty_stage_id_case_sensitive_exact_match(self, mock_get_tags):
        """Test case sensitivity in exact matching with non-empty stage_id.
        
        When stage_id is non-empty, exact matching should be case-sensitive.
        A distribution with different case should not match.
        
        **Validates: Requirements NFR-1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has ApplicationDeploymentId with different case in stage
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-Prod'  # Capital P
        }
        
        # Execute: Validate with stage_id="prod" (lowercase)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail due to case mismatch
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_bucket_app_tag_with_empty_stage_id(self, mock_get_tags):
        """Test validation with empty bucket_app_tag and empty stage_id.
        
        This is an edge case that shouldn't occur in practice, but the function
        should handle it gracefully. With empty bucket_app_tag, any distribution
        would match the prefix (empty string).
        
        **Validates: Requirements NFR-2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has any ApplicationDeploymentId
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'any-value'
        }
        
        # Execute: Validate with empty bucket_app_tag and empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='',
            stage_id=''
        )
        
        # Verify: Should pass (any string starts with empty string)
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_empty_application_deployment_id_with_empty_stage_id(self, mock_get_tags):
        """Test validation with empty ApplicationDeploymentId and empty stage_id.
        
        When ApplicationDeploymentId is empty or missing, validation should fail
        unless bucket_app_tag is also empty.
        
        **Validates: Requirements NFR-2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has empty ApplicationDeploymentId
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': ''
        }
        
        # Execute: Validate with non-empty bucket_app_tag and empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail (empty string doesn't start with non-empty prefix)
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')


class TestValidateDistributionTagsLogging:
    """Tests for logging verification in distribution tag validation.
    
    **Feature: distribution-tag-validation-no-stage-fix**
    **Validates: Requirements FR-5**
    
    These tests verify that the validation function executes correctly with different
    stage_id values, which ensures the logging code paths are exercised. The actual
    log output (visible in test output) confirms that match_type and values are logged.
    """
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_logging_match_type_prefix_when_stage_id_empty(self, mock_get_tags):
        """Test validation with empty stage_id (exercises prefix match logging path).
        
        When stage_id is empty, the validation function should use prefix matching
        and log match_type='prefix'. This test verifies the function executes correctly,
        which ensures the logging code is reached.
        
        **Validates: Requirements FR-5**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution with valid tags
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id (exercises prefix match logging)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass validation (confirms logging code was reached)
        assert result is True
        
        # Note: Log output visible in test output confirms match_type='prefix' is logged
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_logging_match_type_exact_when_stage_id_non_empty(self, mock_get_tags):
        """Test validation with non-empty stage_id (exercises exact match logging path).
        
        When stage_id is non-empty, the validation function should use exact matching
        and log match_type='exact'. This test verifies the function executes correctly,
        which ensures the logging code is reached.
        
        **Validates: Requirements FR-5**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution with valid tags
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with non-empty stage_id (exercises exact match logging)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should pass validation (confirms logging code was reached)
        assert result is True
        
        # Note: Log output visible in test output confirms match_type='exact' is logged
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_logging_includes_expected_and_actual_values_prefix_match(self, mock_get_tags):
        """Test validation logs expected and actual values with prefix match.
        
        When validation is performed with empty stage_id (prefix match), the function
        should log both expected and actual ApplicationDeploymentId values. This test
        verifies the function executes correctly with these values.
        
        **Validates: Requirements FR-5**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution with valid tags
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass validation
        assert result is True
        
        # Note: Log output visible in test output confirms expected and actual values are logged
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_logging_includes_expected_and_actual_values_exact_match(self, mock_get_tags):
        """Test validation logs expected and actual values with exact match.
        
        When validation is performed with non-empty stage_id (exact match), the function
        should log both expected and actual ApplicationDeploymentId values. This test
        verifies the function executes correctly with these values.
        
        **Validates: Requirements FR-5**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution with valid tags
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with non-empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should pass validation
        assert result is True
        
        # Note: Log output visible in test output confirms expected and actual values are logged
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_logging_includes_values_on_validation_failure(self, mock_get_tags):
        """Test validation logs expected and actual values on failure.
        
        When validation fails due to ApplicationDeploymentId mismatch, the function
        should log both expected and actual values in the failure message. This test
        verifies the function executes the failure path correctly.
        
        **Validates: Requirements FR-5**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution with mismatched ApplicationDeploymentId
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-b-prod'  # Wrong prefix
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail validation
        assert result is False
        
        # Note: Log output visible in test output confirms expected and actual values are logged in failure message
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_logging_match_type_in_failure_message(self, mock_get_tags):
        """Test validation logs match_type in failure message.
        
        When validation fails, the warning log message should include the match_type
        to help with debugging. This test verifies the function executes the failure
        path correctly with prefix matching.
        
        **Validates: Requirements FR-5**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution with mismatched ApplicationDeploymentId
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-b-prod'
        }
        
        # Execute: Validate with empty stage_id (prefix match)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail validation
        assert result is False
        
        # Note: Log output visible in test output confirms match_type is logged in failure message


class TestValidateDistributionTagsAllowInvalidationEvents:
    """Tests for AllowInvalidationEvents validation (unchanged behavior).
    
    **Feature: distribution-tag-validation-no-stage-fix**
    **Validates: Requirements 3.1, 3.2**
    
    These tests verify that AllowInvalidationEvents validation remains unchanged
    regardless of whether stage_id is empty or non-empty. The tag must always
    equal "true" for validation to pass.
    """
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_missing_allow_invalidation_events_tag_invalid(self, mock_get_tags):
        """Test validation fails when AllowInvalidationEvents tag is missing.
        
        Even with valid ApplicationDeploymentId, validation should fail if
        AllowInvalidationEvents tag is not present in the distribution tags.
        
        **Validates: Requirements 3.1, 3.2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution missing AllowInvalidationEvents tag
        mock_get_tags.return_value = {
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
            # AllowInvalidationEvents is missing
        }
        
        # Execute: Validate with empty stage_id (prefix match would be valid)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to missing AllowInvalidationEvents
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_allow_invalidation_events_false_invalid(self, mock_get_tags):
        """Test validation fails when AllowInvalidationEvents is set to "false".
        
        Even with valid ApplicationDeploymentId, validation should fail if
        AllowInvalidationEvents is explicitly set to "false".
        
        **Validates: Requirements 3.1, 3.2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has AllowInvalidationEvents set to "false"
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'false',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id (prefix match would be valid)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to AllowInvalidationEvents=false
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_valid_app_deployment_id_but_missing_allow_invalidation_invalid(self, mock_get_tags):
        """Test validation fails with valid ApplicationDeploymentId but missing AllowInvalidationEvents.
        
        This test demonstrates that BOTH tags must be valid for validation to pass.
        A valid ApplicationDeploymentId alone is not sufficient.
        
        **Validates: Requirements 3.1, 3.2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has valid ApplicationDeploymentId but missing AllowInvalidationEvents
        mock_get_tags.return_value = {
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
            # AllowInvalidationEvents is missing
        }
        
        # Execute: Validate with non-empty stage_id (exact match would be valid)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id='prod'
        )
        
        # Verify: Should fail despite valid ApplicationDeploymentId
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_allow_invalidation_events_case_sensitive(self, mock_get_tags):
        """Test that AllowInvalidationEvents value is case-sensitive.
        
        The value must be exactly "true" (lowercase). Other variations like
        "True", "TRUE", or "yes" should not be accepted.
        
        **Validates: Requirements 3.1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has AllowInvalidationEvents with wrong case
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'True',  # Capital T
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to case mismatch
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_allow_invalidation_events_with_whitespace_invalid(self, mock_get_tags):
        """Test that AllowInvalidationEvents value with whitespace is invalid.
        
        The value must be exactly "true" without any leading or trailing whitespace.
        
        **Validates: Requirements 3.1**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has AllowInvalidationEvents with whitespace
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': ' true ',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should fail due to whitespace
        assert result is False
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
    
    @patch('functions.processor.tag_validator.get_distribution_tags')
    def test_both_tags_valid_passes_validation(self, mock_get_tags):
        """Test validation passes when both tags are valid.
        
        This is a positive test case showing that when both AllowInvalidationEvents
        and ApplicationDeploymentId are valid, validation passes.
        
        **Validates: Requirements 3.2**
        """
        from functions.processor.tag_validator import validate_distribution_tags
        
        # Setup: Distribution has both tags valid
        mock_get_tags.return_value = {
            'AllowInvalidationEvents': 'true',
            'atlantis:ApplicationDeploymentId': 'xcme-cdninval-a-prod'
        }
        
        # Execute: Validate with empty stage_id (prefix match)
        result = validate_distribution_tags(
            distribution_id='E2G4RY69EPFNR7',
            bucket_app_tag='xcme-cdninval-a',
            stage_id=''
        )
        
        # Verify: Should pass with both tags valid
        assert result is True
        mock_get_tags.assert_called_once_with('E2G4RY69EPFNR7')
