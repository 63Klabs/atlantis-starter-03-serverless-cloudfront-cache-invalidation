"""Unit tests for CloudFormation parameter integration."""

import os
import unittest
import re
from pathlib import Path
from unittest.mock import patch


class TestCloudFormationParameterIntegration(unittest.TestCase):
    """Test CloudFormation parameter integration with Lambda environment variables."""

    def setUp(self):
        """Set up test environment."""
        self.template_path = Path(__file__).parent.parent.parent / "template.yml"
        self.assertTrue(self.template_path.exists(), "CloudFormation template must exist")

    def test_parameter_validation_ranges(self):
        """Test parameter validation ranges in CloudFormation template."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Test DirectoryConsolidationThreshold parameter
        directory_threshold_pattern = r'DirectoryConsolidationThreshold:\s*\n\s*Type:\s*Number\s*\n.*?MinValue:\s*1\s*\n\s*MaxValue:\s*1000'
        self.assertIsNotNone(
            re.search(directory_threshold_pattern, template_content, re.DOTALL),
            "DirectoryConsolidationThreshold parameter should have MinValue: 1 and MaxValue: 1000"
        )

        # Test ConsolidationStopLevel parameter
        stop_level_pattern = r'ConsolidationStopLevel:\s*\n\s*Type:\s*Number\s*\n.*?MinValue:\s*0\s*\n\s*MaxValue:\s*20'
        self.assertIsNotNone(
            re.search(stop_level_pattern, template_content, re.DOTALL),
            "ConsolidationStopLevel parameter should have MinValue: 0 and MaxValue: 20"
        )

        # Test SiblingDirectoryConsolidationThreshold parameter
        sibling_threshold_pattern = r'SiblingDirectoryConsolidationThreshold:\s*\n\s*Type:\s*Number\s*\n.*?MinValue:\s*1\s*\n\s*MaxValue:\s*1000'
        self.assertIsNotNone(
            re.search(sibling_threshold_pattern, template_content, re.DOTALL),
            "SiblingDirectoryConsolidationThreshold parameter should have MinValue: 1 and MaxValue: 1000"
        )

        # Test AggregationWindowSeconds parameter (should already exist)
        aggregation_pattern = r'AggregationWindowSeconds:\s*\n\s*Type:\s*Number\s*\n.*?MinValue:\s*60\s*\n\s*MaxValue:\s*900'
        self.assertIsNotNone(
            re.search(aggregation_pattern, template_content, re.DOTALL),
            "AggregationWindowSeconds parameter should have MinValue: 60 and MaxValue: 900"
        )

    def test_environment_variable_setting_from_parameters(self):
        """Test environment variable setting from CloudFormation parameters."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Check that Processor Lambda function has the required environment variables
        processor_env_section = self._extract_processor_environment_section(template_content)
        
        # Test DIRECTORY_CONSOLIDATION_THRESHOLD environment variable
        self.assertIn('DIRECTORY_CONSOLIDATION_THRESHOLD: !Ref DirectoryConsolidationThreshold', processor_env_section,
                     "Processor Lambda should have DIRECTORY_CONSOLIDATION_THRESHOLD environment variable")

        # Test CONSOLIDATION_STOP_LEVEL environment variable
        self.assertIn('CONSOLIDATION_STOP_LEVEL: !Ref ConsolidationStopLevel', processor_env_section,
                     "Processor Lambda should have CONSOLIDATION_STOP_LEVEL environment variable")

        # Test SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable
        self.assertIn('SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD: !Ref SiblingDirectoryConsolidationThreshold', processor_env_section,
                     "Processor Lambda should have SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable")

        # Test AGGREGATION_WINDOW_SECONDS environment variable
        self.assertIn('AGGREGATION_WINDOW_SECONDS: !Ref AggregationWindowSeconds', processor_env_section,
                     "Processor Lambda should have AGGREGATION_WINDOW_SECONDS environment variable")

    def test_default_parameter_values_when_not_provided(self):
        """Test default parameter values when not provided."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Test DirectoryConsolidationThreshold default value
        directory_default_pattern = r'DirectoryConsolidationThreshold:\s*\n\s*Type:\s*Number\s*\n.*?Default:\s*3'
        self.assertIsNotNone(
            re.search(directory_default_pattern, template_content, re.DOTALL),
            "DirectoryConsolidationThreshold parameter should have Default: 3"
        )

        # Test ConsolidationStopLevel default value
        stop_level_default_pattern = r'ConsolidationStopLevel:\s*\n\s*Type:\s*Number\s*\n.*?Default:\s*1'
        self.assertIsNotNone(
            re.search(stop_level_default_pattern, template_content, re.DOTALL),
            "ConsolidationStopLevel parameter should have Default: 1"
        )

        # Test SiblingDirectoryConsolidationThreshold default value
        sibling_default_pattern = r'SiblingDirectoryConsolidationThreshold:\s*\n\s*Type:\s*Number\s*\n.*?Default:\s*10'
        self.assertIsNotNone(
            re.search(sibling_default_pattern, template_content, re.DOTALL),
            "SiblingDirectoryConsolidationThreshold parameter should have Default: 10"
        )

        # Test AggregationWindowSeconds default value
        aggregation_default_pattern = r'AggregationWindowSeconds:\s*\n\s*Type:\s*Number\s*\n.*?Default:\s*300'
        self.assertIsNotNone(
            re.search(aggregation_default_pattern, template_content, re.DOTALL),
            "AggregationWindowSeconds parameter should have Default: 300"
        )

    def test_parameters_in_application_parameters_section(self):
        """Test that new parameters are included in Application Parameters section."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract the Application Parameters section from metadata
        app_params_pattern = r'Label:\s*\n\s*default:\s*"Application Parameters"\s*\n\s*Parameters:\s*\n((?:\s*-\s*\w+\s*\n)*)'
        match = re.search(app_params_pattern, template_content)
        self.assertIsNotNone(match, "Application Parameters section should exist in metadata")
        
        app_params_section = match.group(1)
        
        # Check that new parameters are listed
        self.assertIn('- DirectoryConsolidationThreshold', app_params_section,
                     "DirectoryConsolidationThreshold should be in Application Parameters section")
        self.assertIn('- ConsolidationStopLevel', app_params_section,
                     "ConsolidationStopLevel should be in Application Parameters section")
        self.assertIn('- SiblingDirectoryConsolidationThreshold', app_params_section,
                     "SiblingDirectoryConsolidationThreshold should be in Application Parameters section")
        self.assertIn('- AggregationWindowSeconds', app_params_section,
                     "AggregationWindowSeconds should be in Application Parameters section")

    def test_parameter_descriptions_and_help_text(self):
        """Test parameter descriptions and help text."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Test DirectoryConsolidationThreshold description
        directory_desc_pattern = r'DirectoryConsolidationThreshold:\s*\n\s*Type:\s*Number\s*\n\s*Description:\s*"[^"]*consolidation[^"]*"'
        self.assertIsNotNone(
            re.search(directory_desc_pattern, template_content, re.IGNORECASE),
            "DirectoryConsolidationThreshold should have a descriptive description mentioning consolidation"
        )

        # Test ConsolidationStopLevel description
        stop_level_desc_pattern = r'ConsolidationStopLevel:\s*\n\s*Type:\s*Number\s*\n\s*Description:\s*"[^"]*depth[^"]*"'
        self.assertIsNotNone(
            re.search(stop_level_desc_pattern, template_content, re.IGNORECASE),
            "ConsolidationStopLevel should have a descriptive description mentioning depth"
        )

        # Test SiblingDirectoryConsolidationThreshold description
        sibling_desc_pattern = r'SiblingDirectoryConsolidationThreshold:\s*\n\s*Type:\s*Number\s*\n\s*Description:\s*"[^"]*sibling[^"]*"'
        self.assertIsNotNone(
            re.search(sibling_desc_pattern, template_content, re.IGNORECASE),
            "SiblingDirectoryConsolidationThreshold should have a descriptive description mentioning sibling"
        )

    def test_template_syntax_validity(self):
        """Test that the CloudFormation template is syntactically valid YAML."""
        try:
            with open(self.template_path, 'r') as f:
                # Note: We can't fully parse CloudFormation templates as YAML due to intrinsic functions
                # But we can check basic YAML structure
                content = f.read()
                
                # Basic CloudFormation structure checks
                self.assertIn('AWSTemplateFormatVersion', content)
                self.assertIn('Parameters:', content)
                self.assertIn('Resources:', content)
                self.assertIn('DirectoryConsolidationThreshold:', content)
                self.assertIn('ConsolidationStopLevel:', content)
                self.assertIn('SiblingDirectoryConsolidationThreshold:', content)
                
        except Exception as e:
            self.fail(f"CloudFormation template should be valid YAML structure: {e}")

    def test_ingestor_aggregation_window_environment_variable(self):
        """Test that Ingestor Lambda also has AGGREGATION_WINDOW_SECONDS environment variable."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract Ingestor environment section
        ingestor_env_section = self._extract_ingestor_environment_section(template_content)
        
        # Test AGGREGATION_WINDOW_SECONDS environment variable in Ingestor
        self.assertIn('AGGREGATION_WINDOW_SECONDS: !Ref AggregationWindowSeconds', ingestor_env_section,
                     "Ingestor Lambda should have AGGREGATION_WINDOW_SECONDS environment variable")

    def test_origin_path_pattern_parameter_exists(self):
        """Test that OriginPathPattern parameter exists with correct default."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Test OriginPathPattern parameter exists
        origin_pattern_param = r'OriginPathPattern:\s*\n\s*Type:\s*String'
        self.assertIsNotNone(
            re.search(origin_pattern_param, template_content),
            "OriginPathPattern parameter should exist with Type: String"
        )

        # Test default value
        origin_default_pattern = r'OriginPathPattern:\s*\n\s*Type:\s*String\s*\n.*?Default:\s*"/{stageId}/public"'
        self.assertIsNotNone(
            re.search(origin_default_pattern, template_content, re.DOTALL),
            "OriginPathPattern parameter should have Default: /{stageId}/public"
        )

    def test_origin_path_pattern_validation_regex(self):
        """Test that OriginPathPattern has proper validation regex."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Test AllowedPattern exists
        allowed_pattern = r'OriginPathPattern:\s*\n.*?AllowedPattern:\s*"[^"]*"'
        self.assertIsNotNone(
            re.search(allowed_pattern, template_content, re.DOTALL),
            "OriginPathPattern parameter should have AllowedPattern validation"
        )

        # Test ConstraintDescription exists
        constraint_desc = r'OriginPathPattern:\s*\n.*?ConstraintDescription:\s*"[^"]*"'
        self.assertIsNotNone(
            re.search(constraint_desc, template_content, re.DOTALL),
            "OriginPathPattern parameter should have ConstraintDescription"
        )

    def test_origin_path_pattern_invalid_patterns(self):
        """Test that specific invalid patterns would be rejected by the regex."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract the AllowedPattern regex
        pattern_match = re.search(
            r'OriginPathPattern:\s*\n.*?AllowedPattern:\s*"([^"]*)"',
            template_content,
            re.DOTALL
        )
        self.assertIsNotNone(pattern_match, "Should find AllowedPattern")
        
        # The regex from CloudFormation (need to unescape)
        cf_regex = pattern_match.group(1)
        # Convert CloudFormation regex to Python regex (remove extra escaping)
        python_regex = cf_regex.replace('\\\\', '\\')
        
        # Test invalid patterns that should NOT match
        invalid_patterns = [
            'public',  # Doesn't start with /
            '/public/',  # Ends with /
            '/{stage}/public',  # Wrong placeholder (not stageId)
            '/public/!@#',  # Invalid characters
            '/{stageId',  # Unclosed brace
            '/stageId}/public',  # Unopened brace
        ]
        
        for invalid in invalid_patterns:
            match = re.fullmatch(python_regex, invalid)
            # Empty string is allowed (uses default), so skip that check
            if invalid != '':
                self.assertIsNone(
                    match,
                    f"Pattern '{invalid}' should NOT match the AllowedPattern regex"
                )

    def test_origin_path_pattern_valid_patterns(self):
        """Test that specific valid patterns would be accepted by the regex."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract the AllowedPattern regex
        pattern_match = re.search(
            r'OriginPathPattern:\s*\n.*?AllowedPattern:\s*"([^"]*)"',
            template_content,
            re.DOTALL
        )
        self.assertIsNotNone(pattern_match, "Should find AllowedPattern")
        
        # The regex from CloudFormation (need to unescape)
        cf_regex = pattern_match.group(1)
        # Convert CloudFormation regex to Python regex (remove extra escaping)
        python_regex = cf_regex.replace('\\\\', '\\')
        
        # Test valid patterns that SHOULD match
        valid_patterns = [
            '',  # Empty (uses default)
            '/{stageId}/public',  # Default pattern
            '/public',  # No stage placeholder
            '/{stageId}/assets',  # Different directory
            '/content/{stageId}/public',  # Stage in middle
            '/public/{stageId}',  # Stage at end
            '/{stageId}',  # Just stage
        ]
        
        for valid in valid_patterns:
            match = re.fullmatch(python_regex, valid)
            self.assertIsNotNone(
                match,
                f"Pattern '{valid}' SHOULD match the AllowedPattern regex"
            )

    def test_origin_path_pattern_in_application_parameters_metadata(self):
        """Test that OriginPathPattern is in Application Parameters metadata group."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract the Application Parameters section from metadata
        app_params_pattern = r'Label:\s*\n\s*default:\s*"Application Parameters"\s*\n\s*Parameters:\s*\n((?:\s*-\s*\w+\s*\n)*)'
        match = re.search(app_params_pattern, template_content)
        self.assertIsNotNone(match, "Application Parameters section should exist in metadata")
        
        app_params_section = match.group(1)
        
        # Check that OriginPathPattern is listed
        self.assertIn('- OriginPathPattern', app_params_section,
                     "OriginPathPattern should be in Application Parameters section")

    def test_origin_path_pattern_environment_variable_ingestor(self):
        """Test that Ingestor Lambda has ORIGIN_PATH_PATTERN environment variable."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract Ingestor environment section
        ingestor_env_section = self._extract_ingestor_environment_section(template_content)
        
        # Test ORIGIN_PATH_PATTERN environment variable
        self.assertIn('ORIGIN_PATH_PATTERN: !Ref OriginPathPattern', ingestor_env_section,
                     "Ingestor Lambda should have ORIGIN_PATH_PATTERN environment variable")

    def test_origin_path_pattern_environment_variable_processor(self):
        """Test that Processor Lambda has ORIGIN_PATH_PATTERN environment variable."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()

        # Extract Processor environment section
        processor_env_section = self._extract_processor_environment_section(template_content)
        
        # Test ORIGIN_PATH_PATTERN environment variable
        self.assertIn('ORIGIN_PATH_PATTERN: !Ref OriginPathPattern', processor_env_section,
                     "Processor Lambda should have ORIGIN_PATH_PATTERN environment variable")

    def _extract_processor_environment_section(self, template_content: str) -> str:
        """Extract the Processor Lambda environment variables section."""
        # Find ProcessorFunction section and extract environment variables
        processor_pattern = r'ProcessorFunction:\s*\n.*?Environment:\s*\n\s*Variables:\s*\n(.*?)(?=\n\s*Tags:|$)'
        match = re.search(processor_pattern, template_content, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def _extract_ingestor_environment_section(self, template_content: str) -> str:
        """Extract the Ingestor Lambda environment variables section."""
        # Find IngestorFunction section and extract environment variables
        ingestor_pattern = r'IngestorFunction:\s*\n.*?Environment:\s*\n\s*Variables:\s*\n(.*?)(?=\n\s*Tags:|$)'
        match = re.search(ingestor_pattern, template_content, re.DOTALL)
        if match:
            return match.group(1)
        return ""


if __name__ == '__main__':
    unittest.main()