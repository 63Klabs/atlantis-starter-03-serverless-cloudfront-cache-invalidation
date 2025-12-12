#!/usr/bin/env python3
"""
Add SQS Widgets to Dashboard

This script adds SQS queue metrics widgets to the CloudWatch Dashboard
template based on the coordinate mapping.
"""

import json
import yaml
from pathlib import Path
from sqs_metrics_manager import SQSMetricsManager


def load_coordinate_mapping():
    """Load coordinate mapping from JSON file."""
    mapping_path = Path("application-infrastructure/coordinate_mapping.json")
    with open(mapping_path, 'r') as f:
        return json.load(f)


def load_dashboard_template():
    """Load the dashboard template."""
    template_path = Path("application-infrastructure/template-dashboard.yml")
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def save_dashboard_template(template):
    """Save the dashboard template."""
    template_path = Path("application-infrastructure/template-dashboard.yml")
    with open(template_path, 'w') as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)


def parse_dashboard_body(dashboard_body):
    """Parse the dashboard body from CloudFormation Fn::Sub format."""
    if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
        json_str = dashboard_body['Fn::Sub']
    else:
        json_str = dashboard_body
    
    return json.loads(json_str)


def format_dashboard_body(dashboard_data):
    """Format dashboard data back to CloudFormation Fn::Sub format."""
    json_str = json.dumps(dashboard_data, indent=2)
    return {"Fn::Sub": json_str}


def find_insertion_point(widgets, target_y):
    """Find the insertion point for new widgets based on Y coordinate."""
    for i, widget in enumerate(widgets):
        if widget.get('y', 0) >= target_y:
            return i
    return len(widgets)


def add_sqs_widgets():
    """Add all SQS widgets to the dashboard."""
    # Load coordinate mapping and template
    coordinate_mapping = load_coordinate_mapping()
    template = load_dashboard_template()
    
    # Parse dashboard body
    dashboard_body = template['Dashboard']['Properties']['DashboardBody']
    dashboard_data = parse_dashboard_body(dashboard_body)
    
    # Get existing widgets
    widgets = dashboard_data.get('widgets', [])
    
    # Create SQS metrics manager
    sqs_manager = SQSMetricsManager(coordinate_mapping)
    
    # Create SQS widgets
    sqs_widgets = sqs_manager.create_all_sqs_widgets()
    
    # Find insertion point (after SQS header)
    sqs_header_y = coordinate_mapping["new_widgets"]["sqs_header"]["y"]
    insertion_point = find_insertion_point(widgets, sqs_header_y + 2)  # After header
    
    # Insert widgets
    for i, widget in enumerate(sqs_widgets):
        widgets.insert(insertion_point + i, widget)
    
    # Update dashboard data
    dashboard_data['widgets'] = widgets
    
    # Update template
    template['Dashboard']['Properties']['DashboardBody'] = format_dashboard_body(dashboard_data)
    
    # Save template
    save_dashboard_template(template)
    
    print("Successfully added SQS widgets to dashboard template.")
    print(f"Added {len(sqs_widgets)} SQS metrics widgets:")
    for widget in sqs_widgets:
        title = widget['properties']['title']
        x, y = widget['x'], widget['y']
        print(f"  - {title} at position ({x}, {y})")


if __name__ == "__main__":
    add_sqs_widgets()