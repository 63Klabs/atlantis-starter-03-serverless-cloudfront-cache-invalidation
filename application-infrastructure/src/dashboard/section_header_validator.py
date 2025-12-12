"""
Section Header Validator

This module validates and adjusts section header formatting to ensure consistency
across all text header widgets in the CloudWatch Dashboard.
"""

import json
import yaml
import re
from typing import Dict, List, Any, Tuple
from pathlib import Path


class SectionHeaderValidator:
    """Validates and adjusts section header formatting for consistency."""
    
    # Standard header formatting requirements
    STANDARD_HEADER_WIDTH = 24
    STANDARD_HEADER_HEIGHT = 2
    STANDARD_HEADER_X = 0
    
    # Expected header patterns
    HEADER_PATTERNS = {
        'main_title': r'^#\s+.*',  # Main dashboard title (H1)
        'section_header': r'^##\s+.*',  # Section headers (H2)
        'subsection_header': r'^###\s+.*'  # Subsection headers (H3)
    }
    
    def __init__(self, template_path: str):
        """
        Initialize the Section Header Validator.
        
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
    
    def _classify_header_type(self, markdown_text: str) -> str:
        """
        Classify the type of header based on markdown content.
        
        Args:
            markdown_text: The markdown text content
            
        Returns:
            Header type classification
        """
        for header_type, pattern in self.HEADER_PATTERNS.items():
            if re.match(pattern, markdown_text.strip()):
                return header_type
        
        return 'unknown'
    
    def _is_section_header(self, widget: Dict[str, Any]) -> bool:
        """
        Check if a widget is a section header (H2).
        
        Args:
            widget: Widget dictionary
            
        Returns:
            True if widget is a section header
        """
        if widget.get('type') != 'text':
            return False
        
        properties = widget.get('properties', {})
        markdown = properties.get('markdown', '')
        
        return self._classify_header_type(markdown) == 'section_header'
    
    def _is_text_widget(self, widget: Dict[str, Any]) -> bool:
        """
        Check if a widget is a text widget.
        
        Args:
            widget: Widget dictionary
            
        Returns:
            True if widget is a text widget
        """
        return widget.get('type') == 'text'
    
    def validate_section_headers(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate section header formatting against standard requirements.
        
        Returns:
            Tuple of (compliant_headers, non_compliant_headers)
        """
        # Load template
        template = self._load_template()
        
        # Get dashboard body
        dashboard_body = template['Dashboard']['Properties']['DashboardBody']
        dashboard_data = self._parse_dashboard_body(dashboard_body)
        
        # Get widgets
        widgets = dashboard_data.get('widgets', [])
        
        compliant_headers = []
        non_compliant_headers = []
        
        for i, widget in enumerate(widgets):
            if not self._is_text_widget(widget):
                continue
            
            properties = widget.get('properties', {})
            markdown = properties.get('markdown', '')
            header_type = self._classify_header_type(markdown)
            
            x = widget.get('x', 0)
            y = widget.get('y', 0)
            width = widget.get('width', 0)
            height = widget.get('height', 0)
            
            # Check formatting requirements
            issues = []
            
            # Check width (should be 24 for all headers)
            if width != self.STANDARD_HEADER_WIDTH:
                issues.append(f"width should be {self.STANDARD_HEADER_WIDTH}, got {width}")
            
            # Check height (should be 2 for section headers)
            if header_type == 'section_header' and height != self.STANDARD_HEADER_HEIGHT:
                issues.append(f"height should be {self.STANDARD_HEADER_HEIGHT}, got {height}")
            
            # Check x position (should be 0 for full-width headers)
            if x != self.STANDARD_HEADER_X:
                issues.append(f"x position should be {self.STANDARD_HEADER_X}, got {x}")
            
            # Check markdown formatting
            if header_type == 'unknown' and markdown.strip():
                issues.append(f"markdown format not recognized: '{markdown.strip()}'")
            
            header_info = {
                'index': i,
                'type': header_type,
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'markdown': markdown.strip(),
                'issues': issues
            }
            
            if issues:
                non_compliant_headers.append(header_info)
            else:
                compliant_headers.append(header_info)
        
        return compliant_headers, non_compliant_headers
    
    def adjust_section_headers(self) -> Dict[str, Any]:
        """
        Adjust non-compliant section headers to standard formatting.
        
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
            if not self._is_text_widget(widget):
                continue
            
            properties = widget.get('properties', {})
            markdown = properties.get('markdown', '')
            header_type = self._classify_header_type(markdown)
            
            old_values = {
                'x': widget.get('x', 0),
                'y': widget.get('y', 0),
                'width': widget.get('width', 0),
                'height': widget.get('height', 0)
            }
            
            changes_made = []
            
            # Adjust width to standard
            if widget.get('width', 0) != self.STANDARD_HEADER_WIDTH:
                widget['width'] = self.STANDARD_HEADER_WIDTH
                changes_made.append(f"width: {old_values['width']} -> {self.STANDARD_HEADER_WIDTH}")
            
            # Adjust x position to standard
            if widget.get('x', 0) != self.STANDARD_HEADER_X:
                widget['x'] = self.STANDARD_HEADER_X
                changes_made.append(f"x: {old_values['x']} -> {self.STANDARD_HEADER_X}")
            
            # Adjust height for section headers
            if header_type == 'section_header' and widget.get('height', 0) != self.STANDARD_HEADER_HEIGHT:
                widget['height'] = self.STANDARD_HEADER_HEIGHT
                changes_made.append(f"height: {old_values['height']} -> {self.STANDARD_HEADER_HEIGHT}")
            
            if changes_made:
                adjustments_made.append({
                    'index': i,
                    'type': header_type,
                    'markdown': markdown.strip(),
                    'old_values': old_values,
                    'new_values': {
                        'x': widget.get('x'),
                        'y': widget.get('y'),
                        'width': widget.get('width'),
                        'height': widget.get('height')
                    },
                    'changes': changes_made
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
            'standard_requirements': {
                'width': self.STANDARD_HEADER_WIDTH,
                'height': self.STANDARD_HEADER_HEIGHT,
                'x': self.STANDARD_HEADER_X
            }
        }
    
    def get_header_formatting_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive header formatting report.
        
        Returns:
            Dictionary with detailed header analysis
        """
        compliant_headers, non_compliant_headers = self.validate_section_headers()
        
        # Calculate statistics
        total_headers = len(compliant_headers) + len(non_compliant_headers)
        compliance_rate = len(compliant_headers) / total_headers if total_headers > 0 else 0
        
        # Group by header type
        header_type_distribution = {}
        for header in compliant_headers + non_compliant_headers:
            header_type = header['type']
            if header_type not in header_type_distribution:
                header_type_distribution[header_type] = {'compliant': 0, 'non_compliant': 0}
            
            if header in compliant_headers:
                header_type_distribution[header_type]['compliant'] += 1
            else:
                header_type_distribution[header_type]['non_compliant'] += 1
        
        return {
            'total_headers': total_headers,
            'compliant_headers': len(compliant_headers),
            'non_compliant_headers': len(non_compliant_headers),
            'compliance_rate': compliance_rate,
            'standard_requirements': {
                'width': self.STANDARD_HEADER_WIDTH,
                'height': self.STANDARD_HEADER_HEIGHT,
                'x': self.STANDARD_HEADER_X
            },
            'header_type_distribution': header_type_distribution,
            'compliant_details': compliant_headers,
            'non_compliant_details': non_compliant_headers
        }
    
    def find_section_headers_and_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find section headers and their associated metric widgets.
        
        Returns:
            Dictionary mapping section names to their widgets
        """
        # Load template
        template = self._load_template()
        
        # Get dashboard body
        dashboard_body = template['Dashboard']['Properties']['DashboardBody']
        dashboard_data = self._parse_dashboard_body(dashboard_body)
        
        # Get widgets
        widgets = dashboard_data.get('widgets', [])
        
        sections = {}
        current_section = None
        
        for i, widget in enumerate(widgets):
            if self._is_section_header(widget):
                properties = widget.get('properties', {})
                markdown = properties.get('markdown', '')
                
                # Extract section name from markdown
                section_name = markdown.replace('##', '').strip()
                current_section = section_name
                
                sections[current_section] = {
                    'header': {
                        'index': i,
                        'widget': widget,
                        'y': widget.get('y', 0)
                    },
                    'metrics': []
                }
            elif current_section and widget.get('type') in ['metric', 'log']:
                # Add metric/log widgets to current section
                sections[current_section]['metrics'].append({
                    'index': i,
                    'widget': widget,
                    'type': widget.get('type'),
                    'y': widget.get('y', 0)
                })
        
        return sections