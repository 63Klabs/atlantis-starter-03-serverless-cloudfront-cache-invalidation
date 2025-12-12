"""Dashboard layout analysis and coordinate management."""

import json
from typing import Dict, List, Tuple, Any, Optional


class Widget:
    """Represents a CloudWatch Dashboard widget with positioning information."""
    
    def __init__(self, widget_data: Dict[str, Any]):
        """Initialize widget from dashboard JSON data.
        
        Args:
            widget_data: Dictionary containing widget configuration from dashboard JSON
        """
        self.type = widget_data.get('type', '')
        self.x = widget_data.get('x', 0)
        self.y = widget_data.get('y', 0)
        self.width = widget_data.get('width', 1)
        self.height = widget_data.get('height', 1)
        self.properties = widget_data.get('properties', {})
        self.raw_data = widget_data
    
    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get widget bounds as (x1, y1, x2, y2)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)
    
    def overlaps_with(self, other: 'Widget') -> bool:
        """Check if this widget overlaps with another widget.
        
        Args:
            other: Another widget to check overlap with
            
        Returns:
            True if widgets overlap, False otherwise
        """
        x1, y1, x2, y2 = self.get_bounds()
        ox1, oy1, ox2, oy2 = other.get_bounds()
        
        # No overlap if one widget is completely to the left, right, above, or below the other
        return not (x2 <= ox1 or x1 >= ox2 or y2 <= oy1 or y1 >= oy2)
    
    def is_within_grid(self, grid_width: int = 24) -> bool:
        """Check if widget is within the dashboard grid bounds.
        
        Args:
            grid_width: Width of the dashboard grid (default 24 columns)
            
        Returns:
            True if widget is within bounds, False otherwise
        """
        return (self.x >= 0 and 
                self.y >= 0 and 
                self.x + self.width <= grid_width and
                self.width > 0 and 
                self.height > 0)
    
    def __repr__(self) -> str:
        return f"Widget(type='{self.type}', x={self.x}, y={self.y}, width={self.width}, height={self.height})"


class DashboardLayoutAnalyzer:
    """Analyzes and manages CloudWatch Dashboard layout."""
    
    def __init__(self, dashboard_json: str):
        """Initialize analyzer with dashboard JSON.
        
        Args:
            dashboard_json: JSON string containing dashboard configuration
        """
        self.dashboard_data = json.loads(dashboard_json)
        self.widgets = [Widget(widget_data) for widget_data in self.dashboard_data.get('widgets', [])]
    
    def get_current_layout(self) -> Dict[str, Any]:
        """Get current dashboard layout information.
        
        Returns:
            Dictionary containing layout analysis
        """
        layout_info = {
            'total_widgets': len(self.widgets),
            'widget_types': {},
            'max_y': 0,
            'max_x': 0,
            'overlapping_widgets': [],
            'out_of_bounds_widgets': []
        }
        
        # Analyze widget types and positions
        for widget in self.widgets:
            widget_type = widget.type
            if widget_type not in layout_info['widget_types']:
                layout_info['widget_types'][widget_type] = 0
            layout_info['widget_types'][widget_type] += 1
            
            # Track maximum coordinates
            layout_info['max_y'] = max(layout_info['max_y'], widget.y + widget.height)
            layout_info['max_x'] = max(layout_info['max_x'], widget.x + widget.width)
            
            # Check for out of bounds widgets
            if not widget.is_within_grid():
                layout_info['out_of_bounds_widgets'].append(widget)
        
        # Check for overlapping widgets
        layout_info['overlapping_widgets'] = self.find_overlapping_widgets()
        
        return layout_info
    
    def find_overlapping_widgets(self) -> List[Tuple[Widget, Widget]]:
        """Find all pairs of overlapping widgets.
        
        Returns:
            List of tuples containing overlapping widget pairs
        """
        overlapping_pairs = []
        
        for i, widget1 in enumerate(self.widgets):
            for j, widget2 in enumerate(self.widgets[i + 1:], i + 1):
                if widget1.overlaps_with(widget2):
                    overlapping_pairs.append((widget1, widget2))
        
        return overlapping_pairs
    
    def calculate_new_layout_for_alarms_repositioning(self) -> Dict[str, Any]:
        """Calculate new widget positions to accommodate alarms at top.
        
        Returns:
            Dictionary containing coordinate mapping for repositioning
        """
        # Find the title widget (should be at y=0)
        title_widget = None
        alarms_widget = None
        other_widgets = []
        
        for widget in self.widgets:
            if widget.type == 'text' and widget.y == 0:
                title_widget = widget
            elif widget.type == 'alarm':
                alarms_widget = widget
            else:
                other_widgets.append(widget)
        
        coordinate_mapping = {
            'title_widget': title_widget,
            'alarms_widget': alarms_widget,
            'other_widgets': other_widgets,
            'new_positions': {}
        }
        
        if title_widget and alarms_widget:
            # Calculate new alarms position (right after title)
            new_alarms_y = title_widget.y + title_widget.height
            alarms_height = alarms_widget.height
            
            coordinate_mapping['new_positions']['alarms'] = {
                'x': 0,  # Full width positioning
                'y': new_alarms_y,
                'width': 24,  # Full width for visibility
                'height': alarms_height
            }
            
            # Calculate offset for other widgets
            y_offset = new_alarms_y + alarms_height - min(w.y for w in other_widgets if w.y > title_widget.y + title_widget.height)
            
            # Calculate new positions for other widgets
            for widget in other_widgets:
                if widget.y > title_widget.y + title_widget.height:
                    coordinate_mapping['new_positions'][f'widget_{id(widget)}'] = {
                        'x': widget.x,
                        'y': widget.y + y_offset,
                        'width': widget.width,
                        'height': widget.height
                    }
                else:
                    # Keep widgets that are at title level unchanged
                    coordinate_mapping['new_positions'][f'widget_{id(widget)}'] = {
                        'x': widget.x,
                        'y': widget.y,
                        'width': widget.width,
                        'height': widget.height
                    }
        
        return coordinate_mapping
    
    def validate_widget_positioning(self) -> Dict[str, Any]:
        """Validate current widget positioning against requirements.
        
        Returns:
            Dictionary containing validation results
        """
        validation_results = {
            'has_overlaps': len(self.find_overlapping_widgets()) > 0,
            'all_within_bounds': all(w.is_within_grid() for w in self.widgets),
            'consistent_widths': self._check_width_consistency(),
            'alarms_at_top': self._check_alarms_positioning(),
            'has_section_headers': self._check_section_headers()
        }
        
        return validation_results
    
    def _check_width_consistency(self) -> bool:
        """Check if all widgets follow standard width patterns (6, 12, 24)."""
        standard_widths = {6, 12, 24}
        return all(widget.width in standard_widths for widget in self.widgets)
    
    def _check_alarms_positioning(self) -> bool:
        """Check if alarms widget is positioned at the top."""
        alarms_widgets = [w for w in self.widgets if w.type == 'alarm']
        if not alarms_widgets:
            return True  # No alarms widget to check
        
        alarms_widget = alarms_widgets[0]
        # Find non-title widgets with smaller y coordinates
        non_title_widgets = [w for w in self.widgets if w.type != 'text' or w.y != 0]
        
        return all(alarms_widget.y <= w.y for w in non_title_widgets if w != alarms_widget)
    
    def _check_section_headers(self) -> Dict[str, bool]:
        """Check for presence of section headers."""
        text_widgets = [w for w in self.widgets if w.type == 'text']
        
        # Look for section headers in text widget content
        headers_found = {
            'ingestor_header': False,
            'sqs_header': False,
            'processor_header': False
        }
        
        for widget in text_widgets:
            markdown_content = widget.properties.get('markdown', '').lower()
            if 'ingestor' in markdown_content and 'lambda' in markdown_content:
                headers_found['ingestor_header'] = True
            elif 'sqs' in markdown_content and 'queue' in markdown_content:
                headers_found['sqs_header'] = True
            elif 'processor' in markdown_content and 'lambda' in markdown_content:
                headers_found['processor_header'] = True
        
        return headers_found


def parse_dashboard_from_cloudformation_template(template_content: str) -> Optional[str]:
    """Extract dashboard JSON from CloudFormation template.
    
    Args:
        template_content: CloudFormation template content (YAML or JSON)
        
    Returns:
        Dashboard JSON string if found, None otherwise
    """
    try:
        import yaml
        
        # Try parsing as YAML first
        try:
            template_data = yaml.safe_load(template_content)
        except yaml.YAMLError:
            # If YAML parsing fails, try JSON
            template_data = json.loads(template_content)
        
        # Check if Dashboard is at top level (template fragment)
        if 'Dashboard' in template_data and template_data['Dashboard'].get('Type') == 'AWS::CloudWatch::Dashboard':
            dashboard_body = template_data['Dashboard'].get('Properties', {}).get('DashboardBody')
            if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
                # Extract the dashboard JSON from Fn::Sub
                dashboard_json = dashboard_body['Fn::Sub']
                if isinstance(dashboard_json, list) and len(dashboard_json) > 0:
                    return dashboard_json[0]
                elif isinstance(dashboard_json, str):
                    return dashboard_json
            elif isinstance(dashboard_body, str):
                return dashboard_body
        
        # Navigate to Dashboard resource in Resources section
        resources = template_data.get('Resources', {})
        for resource_name, resource_data in resources.items():
            if resource_data.get('Type') == 'AWS::CloudWatch::Dashboard':
                dashboard_body = resource_data.get('Properties', {}).get('DashboardBody')
                if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
                    # Extract the dashboard JSON from Fn::Sub
                    dashboard_json = dashboard_body['Fn::Sub']
                    if isinstance(dashboard_json, list) and len(dashboard_json) > 0:
                        return dashboard_json[0]
                    elif isinstance(dashboard_json, str):
                        return dashboard_json
                elif isinstance(dashboard_body, str):
                    return dashboard_body
        
        return None
        
    except Exception:
        return None