"""
Section header management for CloudWatch Dashboard enhancement.

This module handles adding section headers to organize dashboard content
into logical groups as specified in requirements 4.1, 4.2, 4.3, 4.4, 4.5.
"""

import json
from typing import Dict, List, Any, Optional
from .layout_analyzer import Widget, DashboardLayoutAnalyzer
from .layout_plan import DashboardLayoutPlan


class SectionHeaderManager:
    """Manages section headers for dashboard organization."""
    
    def __init__(self, dashboard_json: str):
        """Initialize with dashboard JSON.
        
        Args:
            dashboard_json: JSON string containing dashboard configuration
        """
        self.dashboard_data = json.loads(dashboard_json)
        self.analyzer = DashboardLayoutAnalyzer(dashboard_json)
        self.widgets = self.analyzer.widgets
    
    def add_ingestor_section_header(self) -> str:
        """Add Ingestor function section header to dashboard.
        
        Returns:
            Updated dashboard JSON string with Ingestor header added
        """
        # Check if header already exists
        if self._has_ingestor_header():
            return json.dumps(self.dashboard_data, indent=2)
        
        # Calculate position for Ingestor header
        header_position = self._calculate_ingestor_header_position()
        
        # Create header widget
        header_widget = self._create_ingestor_header_widget(header_position)
        
        # Insert header and adjust other widgets
        updated_widgets = self._insert_header_and_adjust_widgets(header_widget, header_position)
        
        # Create updated dashboard
        updated_dashboard = self.dashboard_data.copy()
        updated_dashboard['widgets'] = updated_widgets
        
        return json.dumps(updated_dashboard, indent=2)
    
    def add_sqs_section_header(self) -> str:
        """Add SQS queues section header to dashboard.
        
        Returns:
            Updated dashboard JSON string with SQS header added
        """
        # Check if header already exists
        if self._has_sqs_header():
            return json.dumps(self.dashboard_data, indent=2)
        
        # Calculate position for SQS header
        header_position = self._calculate_sqs_header_position()
        
        # Create header widget
        header_widget = self._create_sqs_header_widget(header_position)
        
        # Insert header and adjust other widgets
        updated_widgets = self._insert_header_and_adjust_widgets(header_widget, header_position)
        
        # Create updated dashboard
        updated_dashboard = self.dashboard_data.copy()
        updated_dashboard['widgets'] = updated_widgets
        
        return json.dumps(updated_dashboard, indent=2)
    
    def add_processor_section_header(self) -> str:
        """Add Processor function section header to dashboard.
        
        Returns:
            Updated dashboard JSON string with Processor header added
        """
        # Check if header already exists
        if self._has_processor_header():
            return json.dumps(self.dashboard_data, indent=2)
        
        # Calculate position for Processor header
        header_position = self._calculate_processor_header_position()
        
        # Create header widget
        header_widget = self._create_processor_header_widget(header_position)
        
        # Insert header and adjust other widgets
        updated_widgets = self._insert_header_and_adjust_widgets(header_widget, header_position)
        
        # Create updated dashboard
        updated_dashboard = self.dashboard_data.copy()
        updated_dashboard['widgets'] = updated_widgets
        
        return json.dumps(updated_dashboard, indent=2)
    
    def _has_ingestor_header(self) -> bool:
        """Check if Ingestor section header already exists."""
        for widget in self.widgets:
            if widget.type == 'text':
                markdown_content = widget.properties.get('markdown', '').lower()
                if 'ingestor' in markdown_content and 'lambda' in markdown_content:
                    return True
        return False
    
    def _has_sqs_header(self) -> bool:
        """Check if SQS section header already exists."""
        for widget in self.widgets:
            if widget.type == 'text':
                markdown_content = widget.properties.get('markdown', '').lower()
                if 'sqs queues' in markdown_content:
                    return True
        return False
    
    def _has_processor_header(self) -> bool:
        """Check if Processor section header already exists."""
        for widget in self.widgets:
            if widget.type == 'text':
                markdown_content = widget.properties.get('markdown', '').lower()
                if 'processor' in markdown_content and 'lambda' in markdown_content:
                    return True
        return False
    
    def _calculate_ingestor_header_position(self) -> Dict[str, int]:
        """Calculate position for Ingestor section header.
        
        The header should be positioned after the alarms widget and before
        any existing metric widgets that will become part of the Ingestor section.
        
        Returns:
            Dictionary with x, y, width, height for header position
        """
        # Find alarms widget to position header after it
        alarms_widget = self._find_alarms_widget()
        
        if alarms_widget:
            # Position header right after alarms widget
            header_y = alarms_widget.y + alarms_widget.height
        else:
            # If no alarms widget, find the first metric widget and position before it
            metric_widgets = [w for w in self.widgets if w.type == 'metric']
            if metric_widgets:
                # Sort by Y position to find the topmost metric widget
                metric_widgets.sort(key=lambda w: w.y)
                header_y = metric_widgets[0].y
            else:
                # Fallback: position after title
                title_widget = self._find_title_widget()
                header_y = title_widget.y + title_widget.height if title_widget else 2
        
        return {
            'x': 0,
            'y': header_y,
            'width': 24,  # Full width for section header
            'height': 2   # Standard height for text headers
        }
    
    def _calculate_sqs_header_position(self) -> Dict[str, int]:
        """Calculate position for SQS section header.
        
        The header should be positioned after the Ingestor section and before
        any SQS metric widgets. Based on coordinate mapping, this should be at y=22.
        
        Returns:
            Dictionary with x, y, width, height for header position
        """
        # Based on coordinate mapping, SQS header should be at y=22
        # This is after the Ingestor section (which ends at y=22) and before SQS metrics
        return {
            'x': 0,
            'y': 22,
            'width': 24,  # Full width for section header
            'height': 2   # Standard height for text headers
        }
    
    def _calculate_processor_header_position(self) -> Dict[str, int]:
        """Calculate position for Processor section header.
        
        The header should be positioned above existing Processor metrics.
        We need to find the first Processor widget and position the header before it.
        
        Returns:
            Dictionary with x, y, width, height for header position
        """
        # Find the first Processor widget to position header before it
        processor_widgets = []
        for widget in self.widgets:
            if widget.type == 'metric':
                # Check if this widget contains Processor metrics
                metrics = widget.properties.get('metrics', [])
                for metric in metrics:
                    if (len(metric) >= 4 and 
                        isinstance(metric[3], str) and
                        '${ProcessorFunction}' in metric[3]):
                        processor_widgets.append(widget)
                        break
            elif widget.type == 'log':
                # Check if this log widget references ProcessorFunction
                query = widget.properties.get('query', '')
                if '${ProcessorFunction}' in query:
                    processor_widgets.append(widget)
        
        if processor_widgets:
            # Sort by Y position to find the topmost Processor widget
            processor_widgets.sort(key=lambda w: w.y)
            header_y = processor_widgets[0].y
        else:
            # Fallback: position after title if no Processor widgets found
            title_widget = self._find_title_widget()
            header_y = title_widget.y + title_widget.height if title_widget else 2
        
        return {
            'x': 0,
            'y': header_y,
            'width': 24,  # Full width for section header
            'height': 2   # Standard height for text headers
        }
    
    def _create_ingestor_header_widget(self, position: Dict[str, int]) -> Dict[str, Any]:
        """Create Ingestor section header widget.
        
        Args:
            position: Dictionary with x, y, width, height for widget position
            
        Returns:
            Widget dictionary for Ingestor section header
        """
        return {
            "type": "text",
            "x": position['x'],
            "y": position['y'],
            "width": position['width'],
            "height": position['height'],
            "properties": {
                "markdown": "## Lambda Functions - Ingestor"
            }
        }
    
    def _create_sqs_header_widget(self, position: Dict[str, int]) -> Dict[str, Any]:
        """Create SQS section header widget.
        
        Args:
            position: Dictionary with x, y, width, height for widget position
            
        Returns:
            Widget dictionary for SQS section header
        """
        return {
            "type": "text",
            "x": position['x'],
            "y": position['y'],
            "width": position['width'],
            "height": position['height'],
            "properties": {
                "markdown": "## SQS Queues"
            }
        }
    
    def _create_processor_header_widget(self, position: Dict[str, int]) -> Dict[str, Any]:
        """Create Processor section header widget.
        
        Args:
            position: Dictionary with x, y, width, height for widget position
            
        Returns:
            Widget dictionary for Processor section header
        """
        return {
            "type": "text",
            "x": position['x'],
            "y": position['y'],
            "width": position['width'],
            "height": position['height'],
            "properties": {
                "markdown": "## Lambda Functions - Processor"
            }
        }
    
    def _insert_header_and_adjust_widgets(self, header_widget: Dict[str, Any], 
                                        header_position: Dict[str, int]) -> List[Dict[str, Any]]:
        """Insert header widget and adjust positions of other widgets.
        
        Args:
            header_widget: The header widget to insert
            header_position: Position information for the header
            
        Returns:
            Updated widgets list with header inserted and positions adjusted
        """
        updated_widgets = []
        header_inserted = False
        
        # Sort existing widgets by Y position to maintain order
        widgets_data = list(enumerate(self.dashboard_data['widgets']))
        widgets_data.sort(key=lambda item: (item[1]['y'], item[1]['x']))
        
        for original_index, widget_data in widgets_data:
            widget_y = widget_data['y']
            
            # Insert header before the first widget that comes after header position
            if not header_inserted and widget_y >= header_position['y']:
                updated_widgets.append(header_widget)
                header_inserted = True
            
            # Adjust widget position if it needs to move down for the header
            if widget_y >= header_position['y']:
                adjusted_widget = widget_data.copy()
                adjusted_widget['y'] = widget_y + header_position['height']
                updated_widgets.append(adjusted_widget)
            else:
                # Keep widget in original position
                updated_widgets.append(widget_data)
        
        # If header wasn't inserted yet (all widgets were above header position), add it at the end
        if not header_inserted:
            updated_widgets.append(header_widget)
        
        return updated_widgets
    
    def _find_alarms_widget(self) -> Optional[Widget]:
        """Find the alarms widget."""
        for widget in self.widgets:
            if widget.type == 'alarm':
                return widget
        return None
    
    def _find_title_widget(self) -> Optional[Widget]:
        """Find the title widget (text widget at y=0)."""
        for widget in self.widgets:
            if widget.type == 'text' and widget.y == 0:
                return widget
        return None
    
    def validate_ingestor_header(self) -> Dict[str, Any]:
        """Validate that Ingestor header meets requirements.
        
        Returns:
            Dictionary containing validation results
        """
        # Get dashboard with header added
        updated_json = self.add_ingestor_section_header()
        updated_analyzer = DashboardLayoutAnalyzer(updated_json)
        
        validation_results = {
            'header_exists': False,
            'correct_formatting': False,
            'proper_positioning': False,
            'consistent_with_design': False,
            'no_overlaps': False,
            'issues': []
        }
        
        # Check if header exists (Requirement 4.1)
        ingestor_header = None
        for widget in updated_analyzer.widgets:
            if widget.type == 'text':
                markdown_content = widget.properties.get('markdown', '')
                if 'Lambda Functions - Ingestor' in markdown_content:
                    ingestor_header = widget
                    validation_results['header_exists'] = True
                    break
        
        if not ingestor_header:
            validation_results['issues'].append("Ingestor section header not found")
            return validation_results
        
        # Check formatting consistency (Requirement 4.4)
        expected_markdown = "## Lambda Functions - Ingestor"
        actual_markdown = ingestor_header.properties.get('markdown', '')
        if actual_markdown == expected_markdown:
            validation_results['correct_formatting'] = True
        else:
            validation_results['issues'].append(
                f"Header formatting incorrect: expected '{expected_markdown}', got '{actual_markdown}'"
            )
        
        # Check dimensions (Requirement 4.4)
        if ingestor_header.width == 24 and ingestor_header.height == 2:
            validation_results['consistent_with_design'] = True
        else:
            validation_results['issues'].append(
                f"Header dimensions incorrect: width={ingestor_header.width}, height={ingestor_header.height}"
            )
        
        # Check positioning (Requirements 4.1, 4.5)
        # Header should be positioned logically in the dashboard flow
        alarms_widget = None
        for widget in updated_analyzer.widgets:
            if widget.type == 'alarm':
                alarms_widget = widget
                break
        
        if alarms_widget and ingestor_header.y >= alarms_widget.y + alarms_widget.height:
            validation_results['proper_positioning'] = True
        else:
            validation_results['issues'].append("Header not properly positioned after alarms widget")
        
        # Check for overlaps
        overlapping_pairs = updated_analyzer.find_overlapping_widgets()
        if len(overlapping_pairs) == 0:
            validation_results['no_overlaps'] = True
        else:
            validation_results['issues'].append(f"Found {len(overlapping_pairs)} overlapping widget pairs")
        
        return validation_results
    
    def validate_sqs_header(self) -> Dict[str, Any]:
        """Validate that SQS header meets requirements.
        
        Returns:
            Dictionary containing validation results
        """
        # Get dashboard with header added
        updated_json = self.add_sqs_section_header()
        updated_analyzer = DashboardLayoutAnalyzer(updated_json)
        
        validation_results = {
            'header_exists': False,
            'correct_formatting': False,
            'proper_positioning': False,
            'consistent_with_design': False,
            'no_overlaps': False,
            'issues': []
        }
        
        # Check if header exists (Requirement 4.2)
        sqs_header = None
        for widget in updated_analyzer.widgets:
            if widget.type == 'text':
                markdown_content = widget.properties.get('markdown', '')
                if 'SQS Queues' in markdown_content:
                    sqs_header = widget
                    validation_results['header_exists'] = True
                    break
        
        if not sqs_header:
            validation_results['issues'].append("SQS section header not found")
            return validation_results
        
        # Check formatting consistency (Requirement 4.4)
        expected_markdown = "## SQS Queues"
        actual_markdown = sqs_header.properties.get('markdown', '')
        if actual_markdown == expected_markdown:
            validation_results['correct_formatting'] = True
        else:
            validation_results['issues'].append(
                f"Header formatting incorrect: expected '{expected_markdown}', got '{actual_markdown}'"
            )
        
        # Check dimensions (Requirement 4.4)
        if sqs_header.width == 24 and sqs_header.height == 2:
            validation_results['consistent_with_design'] = True
        else:
            validation_results['issues'].append(
                f"Header dimensions incorrect: width={sqs_header.width}, height={sqs_header.height}"
            )
        
        # Check positioning (Requirements 4.2, 4.5)
        # Header should be positioned at y=22 based on coordinate mapping
        if sqs_header.y == 22:
            validation_results['proper_positioning'] = True
        else:
            validation_results['issues'].append(f"Header not properly positioned: expected y=22, got y={sqs_header.y}")
        
        # Check for overlaps
        overlapping_pairs = updated_analyzer.find_overlapping_widgets()
        if len(overlapping_pairs) == 0:
            validation_results['no_overlaps'] = True
        else:
            validation_results['issues'].append(f"Found {len(overlapping_pairs)} overlapping widget pairs")
        
        return validation_results
    
    def validate_processor_header(self) -> Dict[str, Any]:
        """Validate that Processor header meets requirements.
        
        Returns:
            Dictionary containing validation results
        """
        # Get dashboard with header added
        updated_json = self.add_processor_section_header()
        updated_analyzer = DashboardLayoutAnalyzer(updated_json)
        
        validation_results = {
            'header_exists': False,
            'correct_formatting': False,
            'proper_positioning': False,
            'consistent_with_design': False,
            'no_overlaps': False,
            'existing_widgets_preserved': False,
            'issues': []
        }
        
        # Check if header exists (Requirement 4.3)
        processor_header = None
        for widget in updated_analyzer.widgets:
            if widget.type == 'text':
                markdown_content = widget.properties.get('markdown', '')
                if 'Lambda Functions - Processor' in markdown_content:
                    processor_header = widget
                    validation_results['header_exists'] = True
                    break
        
        if not processor_header:
            validation_results['issues'].append("Processor section header not found")
            return validation_results
        
        # Check formatting consistency (Requirement 4.4)
        expected_markdown = "## Lambda Functions - Processor"
        actual_markdown = processor_header.properties.get('markdown', '')
        if actual_markdown == expected_markdown:
            validation_results['correct_formatting'] = True
        else:
            validation_results['issues'].append(
                f"Header formatting incorrect: expected '{expected_markdown}', got '{actual_markdown}'"
            )
        
        # Check dimensions (Requirement 4.4)
        if processor_header.width == 24 and processor_header.height == 2:
            validation_results['consistent_with_design'] = True
        else:
            validation_results['issues'].append(
                f"Header dimensions incorrect: width={processor_header.width}, height={processor_header.height}"
            )
        
        # Check positioning (Requirements 4.3, 4.5)
        # Header should be positioned above existing Processor widgets
        processor_widgets = []
        for widget in updated_analyzer.widgets:
            if widget != processor_header:  # Exclude the header itself
                if widget.type == 'metric':
                    metrics = widget.properties.get('metrics', [])
                    for metric in metrics:
                        if (len(metric) >= 4 and 
                            isinstance(metric[3], str) and
                            '${ProcessorFunction}' in metric[3]):
                            processor_widgets.append(widget)
                            break
                elif widget.type == 'log':
                    query = widget.properties.get('query', '')
                    if '${ProcessorFunction}' in query:
                        processor_widgets.append(widget)
        
        if processor_widgets:
            # Header should be positioned above all Processor widgets
            min_processor_y = min(w.y for w in processor_widgets)
            if processor_header.y < min_processor_y:
                validation_results['proper_positioning'] = True
            else:
                validation_results['issues'].append(
                    f"Header not properly positioned above Processor widgets: header y={processor_header.y}, min processor y={min_processor_y}"
                )
        else:
            # If no Processor widgets found, positioning is acceptable
            validation_results['proper_positioning'] = True
        
        # Check for overlaps
        overlapping_pairs = updated_analyzer.find_overlapping_widgets()
        if len(overlapping_pairs) == 0:
            validation_results['no_overlaps'] = True
        else:
            validation_results['issues'].append(f"Found {len(overlapping_pairs)} overlapping widget pairs")
        
        # Check that existing Processor widgets are preserved (Requirement 3.5)
        original_processor_count = len([w for w in self.widgets if self._is_processor_widget(w)])
        updated_processor_count = len([w for w in updated_analyzer.widgets if self._is_processor_widget(w)])
        
        if updated_processor_count >= original_processor_count:
            validation_results['existing_widgets_preserved'] = True
        else:
            validation_results['issues'].append(
                f"Processor widgets not preserved: original={original_processor_count}, updated={updated_processor_count}"
            )
        
        return validation_results
    
    def _is_processor_widget(self, widget: Widget) -> bool:
        """Check if a widget is a Processor widget."""
        if widget.type == 'metric':
            metrics = widget.properties.get('metrics', [])
            for metric in metrics:
                if (len(metric) >= 4 and 
                    isinstance(metric[3], str) and
                    '${ProcessorFunction}' in metric[3]):
                    return True
        elif widget.type == 'log':
            query = widget.properties.get('query', '')
            if '${ProcessorFunction}' in query:
                return True
        return False


def add_ingestor_section_header(dashboard_json: str) -> str:
    """Convenience function to add Ingestor section header.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Updated dashboard JSON string with Ingestor header added
    """
    manager = SectionHeaderManager(dashboard_json)
    return manager.add_ingestor_section_header()


def validate_ingestor_section_header(dashboard_json: str) -> Dict[str, Any]:
    """Convenience function to validate Ingestor section header.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Dictionary containing validation results
    """
    manager = SectionHeaderManager(dashboard_json)
    return manager.validate_ingestor_header()


def add_sqs_section_header(dashboard_json: str) -> str:
    """Convenience function to add SQS section header.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Updated dashboard JSON string with SQS header added
    """
    manager = SectionHeaderManager(dashboard_json)
    return manager.add_sqs_section_header()


def validate_sqs_section_header(dashboard_json: str) -> Dict[str, Any]:
    """Convenience function to validate SQS section header.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Dictionary containing validation results
    """
    manager = SectionHeaderManager(dashboard_json)
    return manager.validate_sqs_header()


def add_processor_section_header(dashboard_json: str) -> str:
    """Convenience function to add Processor section header.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Updated dashboard JSON string with Processor header added
    """
    manager = SectionHeaderManager(dashboard_json)
    return manager.add_processor_section_header()


def validate_processor_section_header(dashboard_json: str) -> Dict[str, Any]:
    """Convenience function to validate Processor section header.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Dictionary containing validation results
    """
    manager = SectionHeaderManager(dashboard_json)
    return manager.validate_processor_header()