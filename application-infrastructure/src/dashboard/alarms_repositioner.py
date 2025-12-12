"""
Alarms widget repositioning implementation for CloudWatch Dashboard enhancement.

This module implements the repositioning of the alarms widget to the top of the dashboard
for better visibility, as specified in requirements 3.3, 5.1, 5.3, 5.4, 5.5.
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from .layout_analyzer import Widget, DashboardLayoutAnalyzer


class AlarmsRepositioner:
    """Handles repositioning of alarms widget to top of dashboard."""
    
    def __init__(self, dashboard_json: str):
        """Initialize with dashboard JSON.
        
        Args:
            dashboard_json: JSON string containing dashboard configuration
        """
        self.dashboard_data = json.loads(dashboard_json)
        self.analyzer = DashboardLayoutAnalyzer(dashboard_json)
        self.widgets = self.analyzer.widgets
    
    def reposition_alarms_to_top(self) -> str:
        """Reposition alarms widget to top and adjust other widgets.
        
        Returns:
            Updated dashboard JSON string with alarms repositioned
        """
        # Find title and alarms widgets
        title_widget = self._find_title_widget()
        alarms_widget = self._find_alarms_widget()
        
        if not title_widget or not alarms_widget:
            raise ValueError("Dashboard must contain both title and alarms widgets")
        
        # Calculate new positions
        new_positions = self._calculate_new_positions(title_widget, alarms_widget)
        
        # Update widget positions in dashboard data
        updated_widgets = self._update_widget_positions(new_positions)
        
        # Create updated dashboard
        updated_dashboard = self.dashboard_data.copy()
        updated_dashboard['widgets'] = updated_widgets
        
        return json.dumps(updated_dashboard, indent=2)
    
    def _find_title_widget(self) -> Optional[Widget]:
        """Find the title widget (text widget at y=0)."""
        for widget in self.widgets:
            if widget.type == 'text' and widget.y == 0:
                return widget
        return None
    
    def _find_alarms_widget(self) -> Optional[Widget]:
        """Find the alarms widget."""
        for widget in self.widgets:
            if widget.type == 'alarm':
                return widget
        return None
    
    def _calculate_new_positions(self, title_widget: Widget, alarms_widget: Widget) -> Dict[str, Dict[str, int]]:
        """Calculate new positions for all widgets.
        
        Args:
            title_widget: The title widget
            alarms_widget: The alarms widget
            
        Returns:
            Dictionary mapping widget indices to new positions
        """
        new_positions = {}
        
        # Calculate new alarms position (right after title)
        new_alarms_y = title_widget.y + title_widget.height
        alarms_height = alarms_widget.height
        
        # Set new alarms position (full width for visibility)
        alarms_index = self._get_widget_index(alarms_widget)
        new_positions[alarms_index] = {
            'x': 0,  # Full width positioning
            'y': new_alarms_y,
            'width': 24,  # Full width for maximum visibility
            'height': alarms_height
        }
        
        # Calculate the new minimum Y position for all other widgets
        new_min_y_for_others = new_alarms_y + alarms_height
        
        # Collect widgets that need to be repositioned (excluding title and alarms)
        widgets_to_reposition = [w for w in self.widgets if w != title_widget and w != alarms_widget]
        
        # Sort widgets by their original Y position to maintain relative order
        widgets_to_reposition.sort(key=lambda w: (w.y, w.x))
        
        # Calculate new positions, maintaining spacing between widgets
        current_y = new_min_y_for_others
        
        # Adjust positions for all widgets
        for widget in self.widgets:
            widget_index = self._get_widget_index(widget)
            
            if widget == title_widget:
                # Keep title unchanged
                new_positions[widget_index] = {
                    'x': widget.x,
                    'y': widget.y,
                    'width': widget.width,
                    'height': widget.height
                }
            elif widget == alarms_widget:
                # Already handled above
                continue
            else:
                # For widgets that need repositioning, assign them sequential Y positions
                new_positions[widget_index] = {
                    'x': widget.x,
                    'y': current_y,
                    'width': widget.width,
                    'height': widget.height
                }
                # Move to next Y position for the next widget
                current_y += widget.height
        
        return new_positions
    
    def _get_widget_index(self, target_widget: Widget) -> int:
        """Get the index of a widget in the dashboard widgets list."""
        # Use object identity from the widgets list to find the correct index
        for i, widget in enumerate(self.widgets):
            if widget is target_widget:
                return i
        raise ValueError(f"Widget not found: {target_widget}")
    
    def _update_widget_positions(self, new_positions: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
        """Update widget positions in dashboard data.
        
        Args:
            new_positions: Dictionary mapping widget indices to new positions
            
        Returns:
            Updated widgets list
        """
        updated_widgets = []
        
        for i, widget_data in enumerate(self.dashboard_data['widgets']):
            if i in new_positions:
                # Update position
                updated_widget = widget_data.copy()
                new_pos = new_positions[i]
                updated_widget['x'] = new_pos['x']
                updated_widget['y'] = new_pos['y']
                updated_widget['width'] = new_pos['width']
                updated_widget['height'] = new_pos['height']
                updated_widgets.append(updated_widget)
            else:
                # Keep original
                updated_widgets.append(widget_data)
        
        return updated_widgets
    
    def validate_repositioning(self) -> Dict[str, Any]:
        """Validate that alarms repositioning meets requirements.
        
        Returns:
            Dictionary containing validation results
        """
        # Get repositioned dashboard
        repositioned_json = self.reposition_alarms_to_top()
        repositioned_analyzer = DashboardLayoutAnalyzer(repositioned_json)
        
        validation_results = {
            'alarms_at_top': False,
            'alarms_full_width': False,
            'no_overlaps': False,
            'all_widgets_preserved': False,
            'coordinate_adjustments_correct': False,
            'issues': []
        }
        
        # Find repositioned widgets
        title_widget = None
        alarms_widget = None
        
        for widget in repositioned_analyzer.widgets:
            if widget.type == 'text' and widget.y == 0:
                title_widget = widget
            elif widget.type == 'alarm':
                alarms_widget = widget
        
        if not title_widget or not alarms_widget:
            validation_results['issues'].append("Missing title or alarms widget")
            return validation_results
        
        # Check alarms positioning (Requirements 3.3, 5.1, 5.3, 5.5)
        expected_alarms_y = title_widget.y + title_widget.height
        if alarms_widget.y == expected_alarms_y:
            validation_results['alarms_at_top'] = True
        else:
            validation_results['issues'].append(
                f"Alarms widget not at top: expected y={expected_alarms_y}, got y={alarms_widget.y}"
            )
        
        # Check alarms full width (Requirement 5.3)
        if alarms_widget.width == 24 and alarms_widget.x == 0:
            validation_results['alarms_full_width'] = True
        else:
            validation_results['issues'].append(
                f"Alarms widget not full width: x={alarms_widget.x}, width={alarms_widget.width}"
            )
        
        # Check for overlaps (Requirement 3.1)
        overlapping_pairs = repositioned_analyzer.find_overlapping_widgets()
        if len(overlapping_pairs) == 0:
            validation_results['no_overlaps'] = True
        else:
            validation_results['issues'].append(f"Found {len(overlapping_pairs)} overlapping widget pairs")
        
        # Check widget preservation (Requirement 3.5)
        original_widget_count = len(self.widgets)
        repositioned_widget_count = len(repositioned_analyzer.widgets)
        if original_widget_count == repositioned_widget_count:
            validation_results['all_widgets_preserved'] = True
        else:
            validation_results['issues'].append(
                f"Widget count changed: {original_widget_count} -> {repositioned_widget_count}"
            )
        
        # Check coordinate adjustments (Requirement 5.4)
        non_title_non_alarms_widgets = [
            w for w in repositioned_analyzer.widgets 
            if w.type != 'text' and w.type != 'alarm'
        ]
        
        if all(w.y >= expected_alarms_y + alarms_widget.height for w in non_title_non_alarms_widgets):
            validation_results['coordinate_adjustments_correct'] = True
        else:
            validation_results['issues'].append("Some widgets not properly adjusted for alarms positioning")
        
        return validation_results


def reposition_alarms_in_dashboard(dashboard_json: str) -> str:
    """Convenience function to reposition alarms widget to top.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Updated dashboard JSON string with alarms repositioned
    """
    repositioner = AlarmsRepositioner(dashboard_json)
    return repositioner.reposition_alarms_to_top()


def validate_alarms_repositioning(dashboard_json: str) -> Dict[str, Any]:
    """Convenience function to validate alarms repositioning.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Dictionary containing validation results
    """
    repositioner = AlarmsRepositioner(dashboard_json)
    return repositioner.validate_repositioning()