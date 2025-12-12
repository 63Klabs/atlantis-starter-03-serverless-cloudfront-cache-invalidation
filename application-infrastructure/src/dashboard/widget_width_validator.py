"""
Widget Width Validator

This module validates and adjusts widget widths to ensure consistency
with the standard CloudWatch Dashboard width patterns (6, 12, 24 columns).
"""

import json
import yaml
from typing import Dict, List, Any, Tuple
from pathlib import Path


class WidgetWidthValidator:
    """Validates and adjusts widget widths for consistency."""
    
    # Standard width patterns for CloudWatch Dashboard (24-column grid)
    STANDARD_WIDTHS = [6, 12, 24]
    
    def __init__(self, template_path: str):
        """
        Initialize the Widget Width Validator.
        
        Args:
            template_path: Path to the CloudFormation template file
        """
        self.template_path = Path(template_path)
    
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
    
    def _get_closest_standard_width(self, current_width: int, widget_x: int) -> int:
        """
        Get the closest standard width that fits within grid bounds.
        
        Args:
            current_width: Current widget width
            widget_x: Widget x position
            
        Returns:
            Closest standard width that fits
        """
        max_allowed_width = 24 - widget_x
        
        # Find the largest standard width that fits
        valid_widths = [w for w in self.STANDARD_WIDTHS if w <= max_allowed_width]
        
        if not valid_widths:
            # If no standard width fits, use the maximum allowed
            return max_allowed_width
        
        # Find the closest standard width to current width
        closest_width = min(valid_widths, key=lambda w: abs(w - current_width))
        
        return closest_width
    
    def validate_widget_widths(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate widget widths against standard patterns.
        
        Returns:
            Tuple of (compliant_widgets, non_compliant_widgets)
        """
        # Load template
        template = self._load_template()
        
        # Get dashboard body
        dashboard_body = template['Dashboard']['Properties']['DashboardBody']
        dashboard_data = self._parse_dashboard_body(dashboard_body)
        
        # Get widgets
        widgets = dashboard_data.get('widgets', [])
        
        compliant_widgets = []
        non_compliant_widgets = []
        
        for i, widget in enumerate(widgets):
            width = widget.get('width', 0)
            x = widget.get('x', 0)
            widget_type = widget.get('type', 'unknown')
            
            # Check if width is standard
            if width in self.STANDARD_WIDTHS:
                compliant_widgets.append({
                    'index': i,
                    'type': widget_type,
                    'x': x,
                    'width': width,
                    'status': 'compliant'
                })
            else:
                suggested_width = self._get_closest_standard_width(width, x)
                non_compliant_widgets.append({
                    'index': i,
                    'type': widget_type,
                    'x': x,
                    'current_width': width,
                    'suggested_width': suggested_width,
                    'status': 'non_compliant'
                })
        
        return compliant_widgets, non_compliant_widgets
    
    def adjust_widget_widths(self) -> Dict[str, Any]:
        """
        Adjust non-compliant widget widths to standard patterns.
        
        Returns:
            Dictionary with adjustment results
        """
        # Load template
        template = self._load_template()
        
        # Get dashboard body
        dashboard_body = template['Dashboard']['Properties']['DashboardBody']
        dashboard_data = self._parse_dashboard_body(dashboard_body)
        
        # Get widgets
        widgets = dashboard_data.get('widgets', [])
        
        adjustments_made = []
        
        for i, widget in enumerate(widgets):
            width = widget.get('width', 0)
            x = widget.get('x', 0)
            widget_type = widget.get('type', 'unknown')
            
            # Check if width needs adjustment
            if width not in self.STANDARD_WIDTHS:
                suggested_width = self._get_closest_standard_width(width, x)
                
                # Make adjustment
                old_width = width
                widget['width'] = suggested_width
                
                adjustments_made.append({
                    'index': i,
                    'type': widget_type,
                    'x': x,
                    'old_width': old_width,
                    'new_width': suggested_width
                })
        
        # Update dashboard data
        dashboard_data['widgets'] = widgets
        
        # Update template
        template['Dashboard']['Properties']['DashboardBody'] = self._format_dashboard_body(dashboard_data)
        
        # Save template
        self._save_template(template)
        
        return {
            'adjustments_made': adjustments_made,
            'total_adjustments': len(adjustments_made),
            'standard_widths': self.STANDARD_WIDTHS
        }
    
    def get_width_consistency_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive width consistency report.
        
        Returns:
            Dictionary with detailed width analysis
        """
        compliant_widgets, non_compliant_widgets = self.validate_widget_widths()
        
        # Calculate statistics
        total_widgets = len(compliant_widgets) + len(non_compliant_widgets)
        compliance_rate = len(compliant_widgets) / total_widgets if total_widgets > 0 else 0
        
        # Group by width
        width_distribution = {}
        for widget in compliant_widgets:
            width = widget['width']
            if width not in width_distribution:
                width_distribution[width] = {'compliant': 0, 'non_compliant': 0}
            width_distribution[width]['compliant'] += 1
        
        for widget in non_compliant_widgets:
            width = widget['current_width']
            if width not in width_distribution:
                width_distribution[width] = {'compliant': 0, 'non_compliant': 0}
            width_distribution[width]['non_compliant'] += 1
        
        return {
            'total_widgets': total_widgets,
            'compliant_widgets': len(compliant_widgets),
            'non_compliant_widgets': len(non_compliant_widgets),
            'compliance_rate': compliance_rate,
            'standard_widths': self.STANDARD_WIDTHS,
            'width_distribution': width_distribution,
            'compliant_details': compliant_widgets,
            'non_compliant_details': non_compliant_widgets
        }