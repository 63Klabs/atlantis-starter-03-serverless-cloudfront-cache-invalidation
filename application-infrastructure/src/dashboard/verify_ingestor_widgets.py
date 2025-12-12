#!/usr/bin/env python3
"""
Verify Ingestor Widgets

This script verifies that Ingestor widgets were added correctly to the dashboard.
"""

import json
import yaml
from pathlib import Path


def load_dashboard_template():
    """Load the dashboard template."""
    template_path = Path("application-infrastructure/template-dashboard.yml")
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def parse_dashboard_body(dashboard_body):
    """Parse the dashboard body from CloudFormation Fn::Sub format."""
    if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
        json_str = dashboard_body['Fn::Sub']
    else:
        json_str = dashboard_body
    
    return json.loads(json_str)


def verify_ingestor_widgets():
    """Verify that Ingestor widgets were added correctly."""
    template = load_dashboard_template()
    dashboard_body = template['Dashboard']['Properties']['DashboardBody']
    dashboard_data = parse_dashboard_body(dashboard_body)
    
    widgets = dashboard_data.get('widgets', [])
    
    print(f"Total widgets in dashboard: {len(widgets)}")
    print("\nWidget summary:")
    
    ingestor_widgets = []
    
    for i, widget in enumerate(widgets):
        widget_type = widget.get('type', 'unknown')
        x, y = widget.get('x', 0), widget.get('y', 0)
        width, height = widget.get('width', 0), widget.get('height', 0)
        
        title = "No title"
        if widget_type == 'text':
            title = widget.get('properties', {}).get('markdown', 'No markdown')[:50]
        elif widget_type == 'metric':
            title = widget.get('properties', {}).get('title', 'No title')
        elif widget_type == 'alarm':
            title = widget.get('properties', {}).get('title', 'Alarms')
        elif widget_type == 'log':
            title = widget.get('properties', {}).get('title', 'Log query')
        
        print(f"  {i:2d}: {widget_type:6s} ({x:2d},{y:2d}) {width:2d}x{height:2d} - {title}")
        
        # Check if this is an Ingestor widget
        if widget_type == 'metric' and 'IngestorFunction' in str(widget.get('properties', {})):
            ingestor_widgets.append((i, widget))
    
    print(f"\nFound {len(ingestor_widgets)} Ingestor widgets:")
    for i, (widget_index, widget) in enumerate(ingestor_widgets):
        title = widget.get('properties', {}).get('title', 'No title')
        x, y = widget.get('x', 0), widget.get('y', 0)
        metrics = widget.get('properties', {}).get('metrics', [])
        metric_names = []
        for metric in metrics:
            if len(metric) >= 2 and isinstance(metric[1], str):
                metric_names.append(metric[1])
        
        print(f"  {i+1}. Widget {widget_index}: {title}")
        print(f"     Position: ({x}, {y})")
        print(f"     Metrics: {', '.join(metric_names)}")
        print()
    
    return len(ingestor_widgets) == 5


if __name__ == "__main__":
    success = verify_ingestor_widgets()
    if success:
        print("✓ All 5 Ingestor widgets found successfully!")
    else:
        print("✗ Not all Ingestor widgets found.")