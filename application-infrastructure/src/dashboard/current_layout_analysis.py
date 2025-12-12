"""Analysis of the current CloudWatch Dashboard layout and coordinate planning."""

import json
import yaml
from typing import Dict, List, Any
from .layout_analyzer import DashboardLayoutAnalyzer, parse_dashboard_from_cloudformation_template


def analyze_current_dashboard_structure(template_path: str) -> Dict[str, Any]:
    """Analyze the current dashboard structure from CloudFormation template.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Dictionary containing current layout analysis and new coordinate plan
    """
    # Read the CloudFormation template
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Extract dashboard JSON from template
    dashboard_json = parse_dashboard_from_cloudformation_template(template_content)
    
    if not dashboard_json:
        raise ValueError("Could not extract dashboard JSON from CloudFormation template")
    
    # Parse the dashboard JSON (it may contain CloudFormation substitutions)
    # For analysis purposes, we'll replace the substitutions with placeholder values
    import re
    # Replace CloudFormation variables with valid placeholders
    analysis_json = re.sub(r'\$\{([^}]+)\}', r'PLACEHOLDER_\1', dashboard_json)
    
    # Create analyzer
    analyzer = DashboardLayoutAnalyzer(analysis_json)
    
    # Get current layout information
    current_layout = analyzer.get_current_layout()
    
    # Calculate new layout for alarms repositioning
    new_layout_plan = analyzer.calculate_new_layout_for_alarms_repositioning()
    
    # Validate current positioning
    validation_results = analyzer.validate_widget_positioning()
    
    # Create comprehensive analysis
    analysis = {
        'current_layout': current_layout,
        'new_layout_plan': new_layout_plan,
        'validation_results': validation_results,
        'widgets_summary': _create_widgets_summary(analyzer.widgets),
        'coordinate_mapping': _create_coordinate_mapping(analyzer.widgets, new_layout_plan),
        'recommendations': _generate_layout_recommendations(current_layout, validation_results)
    }
    
    return analysis


def _create_widgets_summary(widgets: List) -> Dict[str, Any]:
    """Create a summary of current widgets."""
    summary = {
        'total_count': len(widgets),
        'by_type': {},
        'positioning': {
            'title_widget': None,
            'alarms_widget': None,
            'metric_widgets': [],
            'log_widgets': [],
            'text_widgets': []
        },
        'grid_usage': {
            'max_x': 0,
            'max_y': 0,
            'used_positions': []
        }
    }
    
    for widget in widgets:
        # Count by type
        widget_type = widget.type
        if widget_type not in summary['by_type']:
            summary['by_type'][widget_type] = 0
        summary['by_type'][widget_type] += 1
        
        # Categorize widgets
        if widget.type == 'text' and widget.y == 0:
            summary['positioning']['title_widget'] = {
                'x': widget.x, 'y': widget.y, 'width': widget.width, 'height': widget.height
            }
        elif widget.type == 'alarm':
            summary['positioning']['alarms_widget'] = {
                'x': widget.x, 'y': widget.y, 'width': widget.width, 'height': widget.height
            }
        elif widget.type == 'metric':
            summary['positioning']['metric_widgets'].append({
                'x': widget.x, 'y': widget.y, 'width': widget.width, 'height': widget.height
            })
        elif widget.type == 'log':
            summary['positioning']['log_widgets'].append({
                'x': widget.x, 'y': widget.y, 'width': widget.width, 'height': widget.height
            })
        elif widget.type == 'text':
            summary['positioning']['text_widgets'].append({
                'x': widget.x, 'y': widget.y, 'width': widget.width, 'height': widget.height,
                'content': widget.properties.get('markdown', '')[:50] + '...'
            })
        
        # Track grid usage
        summary['grid_usage']['max_x'] = max(summary['grid_usage']['max_x'], widget.x + widget.width)
        summary['grid_usage']['max_y'] = max(summary['grid_usage']['max_y'], widget.y + widget.height)
        summary['grid_usage']['used_positions'].append({
            'x': widget.x, 'y': widget.y, 'width': widget.width, 'height': widget.height
        })
    
    return summary


def _create_coordinate_mapping(widgets: List, new_layout_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Create detailed coordinate mapping for repositioning."""
    mapping = {
        'current_positions': {},
        'new_positions': {},
        'adjustments_needed': []
    }
    
    # Map current positions
    for i, widget in enumerate(widgets):
        widget_id = f"widget_{i}_{widget.type}"
        mapping['current_positions'][widget_id] = {
            'type': widget.type,
            'x': widget.x,
            'y': widget.y,
            'width': widget.width,
            'height': widget.height
        }
    
    # Calculate new positions based on alarms repositioning
    title_widget = new_layout_plan.get('title_widget')
    alarms_widget = new_layout_plan.get('alarms_widget')
    
    if title_widget and alarms_widget:
        # New alarms position
        new_alarms_y = title_widget.y + title_widget.height
        mapping['new_positions']['alarms'] = {
            'x': 0,
            'y': new_alarms_y,
            'width': 24,
            'height': alarms_widget.height
        }
        
        # Calculate Y offset for other widgets
        current_min_y_after_title = min(
            w.y for w in widgets 
            if w.type != 'text' and w.type != 'alarm' and w.y > title_widget.y + title_widget.height
        )
        y_offset = (new_alarms_y + alarms_widget.height) - current_min_y_after_title
        
        # Map new positions for other widgets
        for i, widget in enumerate(widgets):
            widget_id = f"widget_{i}_{widget.type}"
            
            if widget.type == 'text' and widget.y == 0:
                # Title stays the same
                mapping['new_positions'][widget_id] = mapping['current_positions'][widget_id]
            elif widget.type == 'alarm':
                # Alarms moved to new position
                mapping['new_positions'][widget_id] = mapping['new_positions']['alarms']
            else:
                # Other widgets adjusted by offset
                new_y = widget.y + y_offset if widget.y > title_widget.y + title_widget.height else widget.y
                mapping['new_positions'][widget_id] = {
                    'type': widget.type,
                    'x': widget.x,
                    'y': new_y,
                    'width': widget.width,
                    'height': widget.height
                }
                
                if new_y != widget.y:
                    mapping['adjustments_needed'].append({
                        'widget_id': widget_id,
                        'old_y': widget.y,
                        'new_y': new_y,
                        'offset': y_offset
                    })
    
    return mapping


def _generate_layout_recommendations(current_layout: Dict[str, Any], validation_results: Dict[str, Any]) -> List[str]:
    """Generate recommendations for layout improvements."""
    recommendations = []
    
    if current_layout['overlapping_widgets']:
        recommendations.append(f"Fix {len(current_layout['overlapping_widgets'])} overlapping widget pairs")
    
    if current_layout['out_of_bounds_widgets']:
        recommendations.append(f"Adjust {len(current_layout['out_of_bounds_widgets'])} widgets that exceed grid bounds")
    
    if not validation_results['consistent_widths']:
        recommendations.append("Standardize widget widths to follow 6/12/24 column patterns")
    
    if not validation_results['alarms_at_top']:
        recommendations.append("Move alarms widget to top position for better visibility")
    
    section_headers = validation_results['has_section_headers']
    if not section_headers['ingestor_header']:
        recommendations.append("Add 'Lambda Functions - Ingestor' section header")
    
    if not section_headers['sqs_header']:
        recommendations.append("Add 'SQS Queues' section header")
    
    if not section_headers['processor_header']:
        recommendations.append("Add 'Lambda Functions - Processor' section header")
    
    # Calculate space needed for new sections
    new_widgets_needed = 0
    if not section_headers['ingestor_header']:
        new_widgets_needed += 5  # Header + 4 metric widgets
    if not section_headers['sqs_header']:
        new_widgets_needed += 5  # Header + 4 SQS widgets
    
    if new_widgets_needed > 0:
        recommendations.append(f"Plan space for approximately {new_widgets_needed} new widgets")
    
    return recommendations


def print_layout_analysis(analysis: Dict[str, Any]) -> None:
    """Print a formatted analysis of the dashboard layout."""
    print("=== CloudWatch Dashboard Layout Analysis ===\n")
    
    # Current layout summary
    current = analysis['current_layout']
    print(f"Current Layout Summary:")
    print(f"  Total widgets: {current['total_widgets']}")
    print(f"  Widget types: {current['widget_types']}")
    print(f"  Grid usage: {current['max_x']} x {current['max_y']}")
    print(f"  Overlapping widgets: {len(current['overlapping_widgets'])}")
    print(f"  Out of bounds widgets: {len(current['out_of_bounds_widgets'])}")
    print()
    
    # Widget positioning
    widgets_summary = analysis['widgets_summary']
    print("Widget Positioning:")
    if widgets_summary['positioning']['title_widget']:
        title = widgets_summary['positioning']['title_widget']
        print(f"  Title: ({title['x']}, {title['y']}) {title['width']}x{title['height']}")
    
    if widgets_summary['positioning']['alarms_widget']:
        alarms = widgets_summary['positioning']['alarms_widget']
        print(f"  Alarms: ({alarms['x']}, {alarms['y']}) {alarms['width']}x{alarms['height']}")
    
    print(f"  Metric widgets: {len(widgets_summary['positioning']['metric_widgets'])}")
    print(f"  Log widgets: {len(widgets_summary['positioning']['log_widgets'])}")
    print(f"  Text widgets: {len(widgets_summary['positioning']['text_widgets'])}")
    print()
    
    # Validation results
    validation = analysis['validation_results']
    print("Validation Results:")
    print(f"  Has overlaps: {validation['has_overlaps']}")
    print(f"  All within bounds: {validation['all_within_bounds']}")
    print(f"  Consistent widths: {validation['consistent_widths']}")
    print(f"  Alarms at top: {validation['alarms_at_top']}")
    print(f"  Section headers: {validation['has_section_headers']}")
    print()
    
    # Recommendations
    print("Recommendations:")
    for i, rec in enumerate(analysis['recommendations'], 1):
        print(f"  {i}. {rec}")
    print()
    
    # Coordinate mapping summary
    mapping = analysis['coordinate_mapping']
    if mapping['adjustments_needed']:
        print("Coordinate Adjustments Needed:")
        for adj in mapping['adjustments_needed']:
            print(f"  {adj['widget_id']}: Y {adj['old_y']} → {adj['new_y']} (offset: +{adj['offset']})")
        print()


if __name__ == "__main__":
    # Example usage
    template_path = "../template-dashboard.yml"
    try:
        analysis = analyze_current_dashboard_structure(template_path)
        print_layout_analysis(analysis)
    except Exception as e:
        print(f"Error analyzing dashboard: {e}")