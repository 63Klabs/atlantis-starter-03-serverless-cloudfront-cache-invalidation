"""
Dashboard Updater

This module handles updating the CloudWatch Dashboard template with new widgets
while preserving existing widgets and maintaining proper positioning.
"""

import json
import yaml
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from .ingestor_metrics_manager import IngestorMetricsManager
from .coordinate_mapping import CoordinateMapping


class DashboardUpdater:
    """Updates CloudWatch Dashboard template with new widgets."""
    
    def __init__(self, template_path: str, coordinate_mapping_path: str):
        """
        Initialize the Dashboard Updater.
        
        Args:
            template_path: Path to the CloudFormation template file
            coordinate_mapping_path: Path to the coordinate mapping JSON file
        """
        self.template_path = Path(template_path)
        self.coordinate_mapping_path = Path(coordinate_mapping_path)
        self.coordinate_mapping = self._load_coordinate_mapping()
        
    def _load_coordinate_mapping(self) -> Dict[str, Any]:
        """Load coordinate mapping from JSON file."""
        with open(self.coordinate_mapping_path, 'r') as f:
            return json.load(f)
    
    def _load_template(self) -> Dict[str, Any]:
        """Load CloudFormation template."""
        with open(self.template_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _save_template(self, template: Dict[str, Any]) -> None:
        """Save CloudFormation template."""
        with open(self.template_path, 'w') as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    
    def _parse_dashboard_body(self, dashboard_body: str) -> Dict[str, Any]:
        """Parse the dashboard body JSON string."""
        # Handle CloudFormation Fn::Sub function
        if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
            dashboard_json_str = dashboard_body['Fn::Sub']
        else:
            dashboard_json_str = dashboard_body
            
        # Parse the JSON string
        return json.loads(dashboard_json_str)
    
    def _format_dashboard_body(self, dashboard_data: Dict[str, Any]) -> Dict[str, str]:
        """Format dashboard data back to CloudFormation Fn::Sub format."""
        dashboard_json_str = json.dumps(dashboard_data, indent=2)
        return {"Fn::Sub": dashboard_json_str}
    
    def add_ingestor_widgets(self) -> None:
        """Add Ingestor metrics widgets to the dashboard."""
        # Load template
        template = self._load_template()
        
        # Get dashboard body
        dashboard_body = template['Dashboard']['Properties']['DashboardBody']
        dashboard_data = self._parse_dashboard_body(dashboard_body)
        
        # Create Ingestor metrics manager
        ingestor_manager = IngestorMetricsManager(self.coordinate_mapping)
        
        # Get existing widgets
        existing_widgets = dashboard_data.get('widgets', [])
        
        # Create new Ingestor widgets
        ingestor_widgets = ingestor_manager.create_all_ingestor_widgets()
        
        # Find insertion point (after alarms widget, before existing processor widgets)
        # Based on coordinate mapping, Ingestor widgets should be inserted after the alarms
        insertion_index = self._find_ingestor_insertion_point(existing_widgets)
        
        # Insert Ingestor widgets
        for i, widget in enumerate(ingestor_widgets):
            existing_widgets.insert(insertion_index + i, widget)
        
        # Update dashboard data
        dashboard_data['widgets'] = existing_widgets
        
        # Update template
        template['Dashboard']['Properties']['DashboardBody'] = self._format_dashboard_body(dashboard_data)
        
        # Save template
        self._save_template(template)
    
    def _find_ingestor_insertion_point(self, widgets: List[Dict[str, Any]]) -> int:
        """
        Find the insertion point for Ingestor widgets.
        
        Args:
            widgets: List of existing widgets
            
        Returns:
            Index where Ingestor widgets should be inserted
        """
        # Look for the Ingestor header widget position
        ingestor_header_y = self.coordinate_mapping["new_widgets"]["ingestor_header"]["position"]["y"]
        
        # Find the widget that comes right before the Ingestor section
        for i, widget in enumerate(widgets):
            widget_y = widget.get('y', 0)
            if widget_y >= ingestor_header_y:
                return i
        
        # If no widget found, append at the end
        return len(widgets)
    
    def update_widget_positions(self) -> None:
        """Update existing widget positions based on coordinate mapping."""
        # Load template
        template = self._load_template()
        
        # Get dashboard body
        dashboard_body = template['Dashboard']['Properties']['DashboardBody']
        dashboard_data = self._parse_dashboard_body(dashboard_body)
        
        # Get existing widgets
        widgets = dashboard_data.get('widgets', [])
        
        # Update positions based on coordinate mapping
        moved_widgets = self.coordinate_mapping.get('widget_details', {}).get('moved_widgets', {})
        
        for i, widget in enumerate(widgets):
            widget_key = f"widget_{i}_{widget.get('type', 'unknown')}"
            if widget_key in moved_widgets:
                new_position = moved_widgets[widget_key]['new_position']
                widget['x'] = new_position['x']
                widget['y'] = new_position['y']
                widget['width'] = new_position['width']
                widget['height'] = new_position['height']
        
        # Update dashboard data
        dashboard_data['widgets'] = widgets
        
        # Update template
        template['Dashboard']['Properties']['DashboardBody'] = self._format_dashboard_body(dashboard_data)
        
        # Save template
        self._save_template(template)