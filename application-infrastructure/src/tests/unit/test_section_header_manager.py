"""
Unit tests for section header management functionality.

Tests the SectionHeaderManager class that adds section headers to organize
dashboard content as specified in requirements 4.1, 4.4, 4.5.
"""

import json
import pytest
from unittest.mock import patch, mock_open

from dashboard.section_header_manager import SectionHeaderManager, add_ingestor_section_header


class TestSectionHeaderManager:
    """Test cases for SectionHeaderManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_dashboard_json = json.dumps({
            "widgets": [
                {
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 24,
                    "height": 2,
                    "properties": {
                        "markdown": "# Test Dashboard"
                    }
                },
                {
                    "type": "alarm",
                    "x": 0,
                    "y": 2,
                    "width": 24,
                    "height": 4,
                    "properties": {
                        "title": "Alarms",
                        "alarms": ["arn:aws:cloudwatch:us-east-1:123456789012:alarm:TestAlarm"]
                    }
                },
                {
                    "type": "metric",
                    "x": 0,
                    "y": 6,
                    "width": 6,
                    "height": 7,
                    "properties": {
                        "metrics": [["AWS/Lambda", "Invocations", "FunctionName", "TestFunction"]],
                        "title": "Test Metric"
                    }
                }
            ]
        })
    
    def test_add_ingestor_section_header_success(self):
        """Test successful addition of Ingestor section header."""
        manager = SectionHeaderManager(self.sample_dashboard_json)
        
        # Add header
        result_json = manager.add_ingestor_section_header()
        result_data = json.loads(result_json)
        
        # Verify header was added
        text_widgets = [w for w in result_data['widgets'] if w['type'] == 'text']
        ingestor_headers = [
            w for w in text_widgets 
            if 'Lambda Functions - Ingestor' in w['properties'].get('markdown', '')
        ]
        
        assert len(ingestor_headers) == 1, "Ingestor header should be added"
        
        header = ingestor_headers[0]
        assert header['width'] == 24, "Header should be full width"
        assert header['height'] == 2, "Header should have standard height"
        assert header['x'] == 0, "Header should start at x=0"
        assert header['properties']['markdown'] == "## Lambda Functions - Ingestor"
    
    def test_header_positioning_after_alarms(self):
        """Test that header is positioned correctly after alarms widget."""
        manager = SectionHeaderManager(self.sample_dashboard_json)
        
        result_json = manager.add_ingestor_section_header()
        result_data = json.loads(result_json)
        
        # Find alarms and header widgets
        alarms_widget = next(w for w in result_data['widgets'] if w['type'] == 'alarm')
        header_widget = next(
            w for w in result_data['widgets'] 
            if w['type'] == 'text' and 'Lambda Functions - Ingestor' in w['properties'].get('markdown', '')
        )
        
        expected_header_y = alarms_widget['y'] + alarms_widget['height']
        assert header_widget['y'] == expected_header_y, "Header should be positioned after alarms widget"
    
    def test_widgets_adjusted_for_header(self):
        """Test that existing widgets are adjusted to make room for header."""
        manager = SectionHeaderManager(self.sample_dashboard_json)
        
        # Get original positions
        original_data = json.loads(self.sample_dashboard_json)
        original_metric_widget = next(w for w in original_data['widgets'] if w['type'] == 'metric')
        original_metric_y = original_metric_widget['y']
        
        # Add header
        result_json = manager.add_ingestor_section_header()
        result_data = json.loads(result_json)
        
        # Find updated metric widget
        updated_metric_widget = next(w for w in result_data['widgets'] if w['type'] == 'metric')
        
        # Verify it was moved down
        assert updated_metric_widget['y'] > original_metric_y, "Metric widget should be moved down for header"
    
    def test_header_already_exists(self):
        """Test behavior when Ingestor header already exists."""
        # Create dashboard with existing header
        dashboard_with_header = {
            "widgets": [
                {
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 24,
                    "height": 2,
                    "properties": {
                        "markdown": "# Test Dashboard"
                    }
                },
                {
                    "type": "text",
                    "x": 0,
                    "y": 2,
                    "width": 24,
                    "height": 2,
                    "properties": {
                        "markdown": "## Lambda Functions - Ingestor"
                    }
                }
            ]
        }
        
        dashboard_json = json.dumps(dashboard_with_header)
        manager = SectionHeaderManager(dashboard_json)
        
        # Try to add header
        result_json = manager.add_ingestor_section_header()
        result_data = json.loads(result_json)
        
        # Verify only one header exists
        ingestor_headers = [
            w for w in result_data['widgets'] 
            if w['type'] == 'text' and 'Lambda Functions - Ingestor' in w['properties'].get('markdown', '')
        ]
        
        assert len(ingestor_headers) == 1, "Should not duplicate existing header"
    
    def test_validate_ingestor_header_success(self):
        """Test validation of successfully added header."""
        manager = SectionHeaderManager(self.sample_dashboard_json)
        
        validation = manager.validate_ingestor_header()
        
        # All validations should pass
        assert validation['header_exists'] is True
        assert validation['correct_formatting'] is True
        assert validation['proper_positioning'] is True
        assert validation['consistent_with_design'] is True
        assert validation['no_overlaps'] is True
        assert len(validation['issues']) == 0
    
    def test_validate_header_without_alarms(self):
        """Test validation when no alarms widget exists."""
        # Create dashboard without alarms
        dashboard_no_alarms = {
            "widgets": [
                {
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 24,
                    "height": 2,
                    "properties": {
                        "markdown": "# Test Dashboard"
                    }
                },
                {
                    "type": "metric",
                    "x": 0,
                    "y": 2,
                    "width": 6,
                    "height": 7,
                    "properties": {
                        "metrics": [["AWS/Lambda", "Invocations", "FunctionName", "TestFunction"]],
                        "title": "Test Metric"
                    }
                }
            ]
        }
        
        dashboard_json = json.dumps(dashboard_no_alarms)
        manager = SectionHeaderManager(dashboard_json)
        
        validation = manager.validate_ingestor_header()
        
        # Header should still be added and validated
        assert validation['header_exists'] is True
        assert validation['correct_formatting'] is True
        assert validation['consistent_with_design'] is True


class TestConvenienceFunctions:
    """Test convenience functions for section header management."""
    
    def test_add_ingestor_section_header_function(self):
        """Test the convenience function for adding Ingestor header."""
        sample_dashboard = json.dumps({
            "widgets": [
                {
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 24,
                    "height": 2,
                    "properties": {
                        "markdown": "# Test Dashboard"
                    }
                }
            ]
        })
        
        result_json = add_ingestor_section_header(sample_dashboard)
        result_data = json.loads(result_json)
        
        # Verify header was added
        ingestor_headers = [
            w for w in result_data['widgets'] 
            if w['type'] == 'text' and 'Lambda Functions - Ingestor' in w['properties'].get('markdown', '')
        ]
        
        assert len(ingestor_headers) == 1, "Header should be added by convenience function"


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_dashboard(self):
        """Test behavior with empty dashboard."""
        empty_dashboard = json.dumps({"widgets": []})
        manager = SectionHeaderManager(empty_dashboard)
        
        result_json = manager.add_ingestor_section_header()
        result_data = json.loads(result_json)
        
        # Header should still be added
        assert len(result_data['widgets']) == 1
        assert result_data['widgets'][0]['type'] == 'text'
        assert 'Lambda Functions - Ingestor' in result_data['widgets'][0]['properties']['markdown']
    
    def test_invalid_json(self):
        """Test behavior with invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            SectionHeaderManager("invalid json")
    
    def test_dashboard_without_widgets_key(self):
        """Test behavior when dashboard doesn't have widgets key."""
        invalid_dashboard = json.dumps({"not_widgets": []})
        
        with pytest.raises(KeyError):
            manager = SectionHeaderManager(invalid_dashboard)
            manager.add_ingestor_section_header()