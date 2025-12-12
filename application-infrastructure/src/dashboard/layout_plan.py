"""
Comprehensive layout plan for CloudWatch Dashboard enhancement.

This module creates a detailed coordinate mapping for repositioning widgets
to accommodate alarms at top and new Ingestor/SQS sections.
"""

from typing import Dict, List, Any, Tuple
from .current_layout_analysis import analyze_current_dashboard_structure


class DashboardLayoutPlan:
    """Creates and manages the layout plan for dashboard enhancement."""
    
    def __init__(self, template_path: str):
        """Initialize with current dashboard analysis.
        
        Args:
            template_path: Path to the CloudFormation template file
        """
        self.analysis = analyze_current_dashboard_structure(template_path)
        self.current_widgets = self._extract_current_widgets()
        self.new_layout = self._calculate_new_layout()
    
    def _extract_current_widgets(self) -> List[Dict[str, Any]]:
        """Extract current widget information from analysis."""
        widgets = []
        
        # Extract from coordinate mapping
        current_positions = self.analysis['coordinate_mapping']['current_positions']
        
        for widget_id, position in current_positions.items():
            widgets.append({
                'id': widget_id,
                'type': position['type'],
                'x': position['x'],
                'y': position['y'],
                'width': position['width'],
                'height': position['height']
            })
        
        return widgets
    
    def _calculate_new_layout(self) -> Dict[str, Any]:
        """Calculate complete new layout with all sections."""
        layout = {
            'sections': {},
            'widget_positions': {},
            'y_coordinates': {}
        }
        
        # Define section structure
        current_y = 0
        
        # 1. Title section (unchanged)
        title_widget = self._find_widget_by_type('text', y_position=0)
        if title_widget:
            layout['sections']['title'] = {
                'start_y': current_y,
                'height': title_widget['height'],
                'widgets': ['title']
            }
            layout['widget_positions']['title'] = {
                'x': title_widget['x'],
                'y': current_y,
                'width': title_widget['width'],
                'height': title_widget['height']
            }
            current_y += title_widget['height']
        
        # 2. Alarms section (moved to top)
        alarms_widget = self._find_widget_by_type('alarm')
        if alarms_widget:
            layout['sections']['alarms'] = {
                'start_y': current_y,
                'height': alarms_widget['height'],
                'widgets': ['alarms']
            }
            layout['widget_positions']['alarms'] = {
                'x': 0,  # Full width for visibility
                'y': current_y,
                'width': 24,  # Full width
                'height': alarms_widget['height']
            }
            current_y += alarms_widget['height']
        
        # 3. Ingestor Lambda Functions section (NEW)
        ingestor_section_height = self._calculate_ingestor_section_height()
        layout['sections']['ingestor'] = {
            'start_y': current_y,
            'height': ingestor_section_height,
            'widgets': ['ingestor_header', 'ingestor_invocations', 'ingestor_duration', 
                       'ingestor_concurrent', 'ingestor_summary']
        }
        
        # Ingestor section header
        layout['widget_positions']['ingestor_header'] = {
            'x': 0, 'y': current_y, 'width': 24, 'height': 2
        }
        current_y += 2
        
        # Ingestor metrics widgets (2 rows of 3 widgets each)
        # Row 1: Invocations, Duration, Concurrent Executions
        layout['widget_positions']['ingestor_invocations'] = {
            'x': 0, 'y': current_y, 'width': 6, 'height': 7
        }
        layout['widget_positions']['ingestor_duration'] = {
            'x': 6, 'y': current_y, 'width': 6, 'height': 7
        }
        layout['widget_positions']['ingestor_concurrent'] = {
            'x': 12, 'y': current_y, 'width': 6, 'height': 7
        }
        layout['widget_positions']['ingestor_summary'] = {
            'x': 18, 'y': current_y, 'width': 6, 'height': 5
        }
        current_y += 7
        
        # Row 2: Errors widget
        layout['widget_positions']['ingestor_errors'] = {
            'x': 0, 'y': current_y, 'width': 6, 'height': 7
        }
        current_y += 7
        
        # 4. SQS Queues section (NEW)
        sqs_section_height = self._calculate_sqs_section_height()
        layout['sections']['sqs'] = {
            'start_y': current_y,
            'height': sqs_section_height,
            'widgets': ['sqs_header', 'sqs_message_count', 'sqs_age', 'sqs_dlq', 'sqs_rates']
        }
        
        # SQS section header
        layout['widget_positions']['sqs_header'] = {
            'x': 0, 'y': current_y, 'width': 24, 'height': 2
        }
        current_y += 2
        
        # SQS metrics widgets (2 rows)
        # Row 1: Message counts, Age, DLQ
        layout['widget_positions']['sqs_message_count'] = {
            'x': 0, 'y': current_y, 'width': 6, 'height': 7
        }
        layout['widget_positions']['sqs_age'] = {
            'x': 6, 'y': current_y, 'width': 6, 'height': 7
        }
        layout['widget_positions']['sqs_dlq'] = {
            'x': 12, 'y': current_y, 'width': 6, 'height': 7
        }
        layout['widget_positions']['sqs_rates'] = {
            'x': 18, 'y': current_y, 'width': 6, 'height': 7
        }
        current_y += 7
        
        # 5. Processor Lambda Functions section (existing widgets repositioned)
        processor_section_height = self._calculate_processor_section_height()
        layout['sections']['processor'] = {
            'start_y': current_y,
            'height': processor_section_height,
            'widgets': ['processor_header'] + self._get_existing_processor_widgets()
        }
        
        # Processor section header
        layout['widget_positions']['processor_header'] = {
            'x': 0, 'y': current_y, 'width': 24, 'height': 2
        }
        current_y += 2
        
        # Reposition existing processor widgets
        processor_widgets = self._get_existing_processor_metric_widgets()
        current_y = self._position_processor_widgets(layout, processor_widgets, current_y)
        
        # 6. Logs and Analysis section (existing widgets repositioned)
        logs_section_height = self._calculate_logs_section_height()
        layout['sections']['logs'] = {
            'start_y': current_y,
            'height': logs_section_height,
            'widgets': self._get_existing_log_widgets()
        }
        
        # Reposition existing log widgets
        log_widgets = self._get_existing_log_widgets_data()
        self._position_log_widgets(layout, log_widgets, current_y)
        
        # Store Y coordinates for reference
        layout['y_coordinates'] = {
            'title_end': layout['sections']['title']['start_y'] + layout['sections']['title']['height'],
            'alarms_end': layout['sections']['alarms']['start_y'] + layout['sections']['alarms']['height'],
            'ingestor_end': layout['sections']['ingestor']['start_y'] + layout['sections']['ingestor']['height'],
            'sqs_end': layout['sections']['sqs']['start_y'] + layout['sections']['sqs']['height'],
            'processor_end': layout['sections']['processor']['start_y'] + layout['sections']['processor']['height'],
            'logs_end': layout['sections']['logs']['start_y'] + layout['sections']['logs']['height']
        }
        
        return layout
    
    def _find_widget_by_type(self, widget_type: str, y_position: int = None) -> Dict[str, Any]:
        """Find widget by type and optionally by Y position."""
        for widget in self.current_widgets:
            if widget['type'] == widget_type:
                if y_position is None or widget['y'] == y_position:
                    return widget
        return None
    
    def _calculate_ingestor_section_height(self) -> int:
        """Calculate height needed for Ingestor section."""
        # Header (2) + First row of metrics (7) + Second row with errors (7)
        return 2 + 7 + 7
    
    def _calculate_sqs_section_height(self) -> int:
        """Calculate height needed for SQS section."""
        # Header (2) + Metrics row (7)
        return 2 + 7
    
    def _calculate_processor_section_height(self) -> int:
        """Calculate height needed for Processor section."""
        processor_widgets = self._get_existing_processor_metric_widgets()
        if not processor_widgets:
            return 2  # Just header
        
        # Header + height of existing processor widgets
        max_y = max(w['y'] + w['height'] for w in processor_widgets)
        min_y = min(w['y'] for w in processor_widgets)
        return 2 + (max_y - min_y)
    
    def _calculate_logs_section_height(self) -> int:
        """Calculate height needed for Logs section."""
        log_widgets = self._get_existing_log_widgets_data()
        if not log_widgets:
            return 0
        
        max_y = max(w['y'] + w['height'] for w in log_widgets)
        min_y = min(w['y'] for w in log_widgets)
        return max_y - min_y
    
    def _get_existing_processor_widgets(self) -> List[str]:
        """Get list of existing processor widget IDs."""
        processor_widgets = []
        for widget in self.current_widgets:
            if (widget['type'] == 'metric' and 
                widget['y'] > 0):  # Exclude title
                processor_widgets.append(widget['id'])
        return processor_widgets
    
    def _get_existing_processor_metric_widgets(self) -> List[Dict[str, Any]]:
        """Get existing processor metric widgets data."""
        processor_widgets = []
        for widget in self.current_widgets:
            if (widget['type'] == 'metric' and 
                widget['y'] > 0):  # Exclude title
                processor_widgets.append(widget)
        return processor_widgets
    
    def _get_existing_log_widgets(self) -> List[str]:
        """Get list of existing log widget IDs."""
        log_widgets = []
        for widget in self.current_widgets:
            if widget['type'] == 'log':
                log_widgets.append(widget['id'])
        return log_widgets
    
    def _get_existing_log_widgets_data(self) -> List[Dict[str, Any]]:
        """Get existing log widgets data."""
        log_widgets = []
        for widget in self.current_widgets:
            if widget['type'] == 'log':
                log_widgets.append(widget)
        return log_widgets
    
    def _position_processor_widgets(self, layout: Dict[str, Any], 
                                  processor_widgets: List[Dict[str, Any]], 
                                  start_y: int) -> int:
        """Position existing processor widgets in new layout."""
        if not processor_widgets:
            return start_y
        
        # Sort widgets by original Y position to maintain relative positioning
        processor_widgets.sort(key=lambda w: (w['y'], w['x']))
        
        # Find the original Y range
        original_min_y = min(w['y'] for w in processor_widgets)
        
        # Calculate offset to new position
        y_offset = start_y - original_min_y
        
        # Position each widget
        max_new_y = start_y
        for widget in processor_widgets:
            new_y = widget['y'] + y_offset
            layout['widget_positions'][widget['id']] = {
                'x': widget['x'],
                'y': new_y,
                'width': widget['width'],
                'height': widget['height']
            }
            max_new_y = max(max_new_y, new_y + widget['height'])
        
        return max_new_y
    
    def _position_log_widgets(self, layout: Dict[str, Any], 
                            log_widgets: List[Dict[str, Any]], 
                            start_y: int) -> int:
        """Position existing log widgets in new layout."""
        if not log_widgets:
            return start_y
        
        # Sort widgets by original Y position
        log_widgets.sort(key=lambda w: (w['y'], w['x']))
        
        # Find the original Y range
        original_min_y = min(w['y'] for w in log_widgets)
        
        # Calculate offset to new position
        y_offset = start_y - original_min_y
        
        # Position each widget
        max_new_y = start_y
        for widget in log_widgets:
            new_y = widget['y'] + y_offset
            layout['widget_positions'][widget['id']] = {
                'x': widget['x'],
                'y': new_y,
                'width': widget['width'],
                'height': widget['height']
            }
            max_new_y = max(max_new_y, new_y + widget['height'])
        
        return max_new_y
    
    def get_coordinate_mapping(self) -> Dict[str, Any]:
        """Get complete coordinate mapping for all widgets."""
        mapping = {
            'current_positions': {},
            'new_positions': {},
            'new_widgets': {},
            'adjustments_summary': {
                'widgets_moved': 0,
                'widgets_added': 0,
                'max_y_change': 0
            }
        }
        
        # Map current positions
        for widget in self.current_widgets:
            mapping['current_positions'][widget['id']] = {
                'x': widget['x'],
                'y': widget['y'],
                'width': widget['width'],
                'height': widget['height']
            }
        
        # Map new positions from layout plan
        mapping['new_positions'] = self.new_layout['widget_positions'].copy()
        
        # Identify new widgets
        new_widget_ids = [
            'ingestor_header', 'ingestor_invocations', 'ingestor_duration',
            'ingestor_concurrent', 'ingestor_summary', 'ingestor_errors',
            'sqs_header', 'sqs_message_count', 'sqs_age', 'sqs_dlq', 'sqs_rates',
            'processor_header'
        ]
        
        for widget_id in new_widget_ids:
            if widget_id in mapping['new_positions']:
                mapping['new_widgets'][widget_id] = mapping['new_positions'][widget_id]
        
        # Calculate adjustment summary
        widgets_moved = 0
        max_y_change = 0
        
        for widget_id in mapping['current_positions']:
            if widget_id in mapping['new_positions']:
                old_y = mapping['current_positions'][widget_id]['y']
                new_y = mapping['new_positions'][widget_id]['y']
                if old_y != new_y:
                    widgets_moved += 1
                    max_y_change = max(max_y_change, abs(new_y - old_y))
        
        mapping['adjustments_summary'] = {
            'widgets_moved': widgets_moved,
            'widgets_added': len(mapping['new_widgets']),
            'max_y_change': max_y_change
        }
        
        return mapping
    
    def get_layout_summary(self) -> Dict[str, Any]:
        """Get summary of the new layout plan."""
        coordinate_mapping = self.get_coordinate_mapping()
        
        return {
            'sections': list(self.new_layout['sections'].keys()),
            'total_widgets': len(self.new_layout['widget_positions']),
            'new_widgets_count': len(coordinate_mapping['new_widgets']),
            'moved_widgets_count': coordinate_mapping['adjustments_summary']['widgets_moved'],
            'max_y_coordinate': max(
                pos['y'] + pos['height'] 
                for pos in self.new_layout['widget_positions'].values()
            ),
            'sections_summary': {
                section: {
                    'start_y': data['start_y'],
                    'height': data['height'],
                    'widget_count': len(data['widgets'])
                }
                for section, data in self.new_layout['sections'].items()
            },
            'y_coordinates': self.new_layout['y_coordinates']
        }
    
    def validate_layout_plan(self) -> Dict[str, Any]:
        """Validate the layout plan against requirements."""
        validation = {
            'no_overlaps': True,
            'within_grid_bounds': True,
            'alarms_at_top': True,
            'consistent_widths': True,
            'has_all_sections': True,
            'issues': []
        }
        
        positions = self.new_layout['widget_positions']
        
        # Check for overlaps
        widget_list = list(positions.items())
        for i, (id1, pos1) in enumerate(widget_list):
            for id2, pos2 in widget_list[i+1:]:
                if self._widgets_overlap(pos1, pos2):
                    validation['no_overlaps'] = False
                    validation['issues'].append(f"Overlap detected: {id1} and {id2}")
        
        # Check grid bounds
        for widget_id, pos in positions.items():
            if (pos['x'] < 0 or pos['y'] < 0 or 
                pos['x'] + pos['width'] > 24 or
                pos['width'] <= 0 or pos['height'] <= 0):
                validation['within_grid_bounds'] = False
                validation['issues'].append(f"Widget {widget_id} exceeds grid bounds")
        
        # Check alarms positioning
        if 'alarms' in positions:
            alarms_y = positions['alarms']['y']
            non_title_widgets = [
                pos for widget_id, pos in positions.items() 
                if widget_id not in ['title', 'alarms']
            ]
            if any(pos['y'] < alarms_y for pos in non_title_widgets):
                validation['alarms_at_top'] = False
                validation['issues'].append("Alarms widget is not at the top")
        
        # Check width consistency
        standard_widths = {6, 12, 24}
        for widget_id, pos in positions.items():
            if pos['width'] not in standard_widths:
                validation['consistent_widths'] = False
                validation['issues'].append(f"Widget {widget_id} has non-standard width: {pos['width']}")
        
        # Check section headers
        required_headers = ['ingestor_header', 'sqs_header', 'processor_header']
        for header in required_headers:
            if header not in positions:
                validation['has_all_sections'] = False
                validation['issues'].append(f"Missing section header: {header}")
        
        return validation
    
    def _widgets_overlap(self, pos1: Dict[str, int], pos2: Dict[str, int]) -> bool:
        """Check if two widget positions overlap."""
        x1, y1, w1, h1 = pos1['x'], pos1['y'], pos1['width'], pos1['height']
        x2, y2, w2, h2 = pos2['x'], pos2['y'], pos2['width'], pos2['height']
        
        return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def create_layout_plan(template_path: str) -> DashboardLayoutPlan:
    """Create a comprehensive layout plan for dashboard enhancement.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        DashboardLayoutPlan instance with complete coordinate mapping
    """
    return DashboardLayoutPlan(template_path)


def print_layout_plan(plan: DashboardLayoutPlan) -> None:
    """Print a formatted layout plan summary."""
    print("=== Dashboard Layout Plan ===\n")
    
    summary = plan.get_layout_summary()
    
    print("Layout Summary:")
    print(f"  Total widgets: {summary['total_widgets']}")
    print(f"  New widgets: {summary['new_widgets_count']}")
    print(f"  Moved widgets: {summary['moved_widgets_count']}")
    print(f"  Maximum Y coordinate: {summary['max_y_coordinate']}")
    print()
    
    print("Sections:")
    for section, data in summary['sections_summary'].items():
        print(f"  {section.title()}: Y {data['start_y']}-{data['start_y'] + data['height']} "
              f"({data['widget_count']} widgets)")
    print()
    
    validation = plan.validate_layout_plan()
    print("Validation Results:")
    print(f"  No overlaps: {validation['no_overlaps']}")
    print(f"  Within grid bounds: {validation['within_grid_bounds']}")
    print(f"  Alarms at top: {validation['alarms_at_top']}")
    print(f"  Consistent widths: {validation['consistent_widths']}")
    print(f"  Has all sections: {validation['has_all_sections']}")
    
    if validation['issues']:
        print("  Issues found:")
        for issue in validation['issues']:
            print(f"    - {issue}")
    print()
    
    coordinate_mapping = plan.get_coordinate_mapping()
    print("Coordinate Changes:")
    print(f"  Widgets to be moved: {coordinate_mapping['adjustments_summary']['widgets_moved']}")
    print(f"  New widgets to add: {coordinate_mapping['adjustments_summary']['widgets_added']}")
    print(f"  Maximum Y change: {coordinate_mapping['adjustments_summary']['max_y_change']}")


if __name__ == "__main__":
    # Example usage
    template_path = "../template-dashboard.yml"
    try:
        plan = create_layout_plan(template_path)
        print_layout_plan(plan)
    except Exception as e:
        print(f"Error creating layout plan: {e}")
        import traceback
        traceback.print_exc()