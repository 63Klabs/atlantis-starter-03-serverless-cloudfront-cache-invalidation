#!/usr/bin/env python3
"""
Add Ingestor Widgets to Dashboard

This script adds Ingestor Lambda function metrics widgets to the CloudWatch Dashboard
template based on the coordinate mapping.
"""

import json
import yaml
import re
from pathlib import Path


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


def create_ingestor_invocations_errors_widget(coordinate_mapping):
    """Create Ingestor invocations and errors widget."""
    position = coordinate_mapping["new_widgets"]["ingestor_invocations"]
    
    return {
        "type": "metric",
        "x": position["x"],
        "y": position["y"],
        "width": position["width"],
        "height": position["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Invocations",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "id": "m1",
                        "color": "#1f77b4",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "AWS/Lambda",
                    "Errors",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "id": "m2",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Ingestor Invocations & Errors",
            "period": 300,
            "stat": "Sum"
        }
    }


def create_ingestor_duration_widget(coordinate_mapping):
    """Create Ingestor duration metrics widget."""
    position = coordinate_mapping["new_widgets"]["ingestor_duration"]
    
    return {
        "type": "metric",
        "x": position["x"],
        "y": position["y"],
        "width": position["width"],
        "height": position["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Duration",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "id": "m1",
                        "color": "#ff7f0e",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "...",
                    {
                        "id": "m2",
                        "stat": "Maximum",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "...",
                    {
                        "id": "m3",
                        "stat": "Minimum",
                        "color": "#2ca02c",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Ingestor Duration",
            "period": 300,
            "stat": "Average"
        }
    }


def create_ingestor_concurrent_widget(coordinate_mapping):
    """Create Ingestor concurrent executions widget."""
    position = coordinate_mapping["new_widgets"]["ingestor_concurrent"]
    
    return {
        "type": "metric",
        "x": position["x"],
        "y": position["y"],
        "width": position["width"],
        "height": position["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "ConcurrentExecutions",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Ingestor Concurrent Executions",
            "period": 300,
            "stat": "Average"
        }
    }


def create_ingestor_summary_widget(coordinate_mapping):
    """Create Ingestor invocation summary widget."""
    position = coordinate_mapping["new_widgets"]["ingestor_summary"]
    
    return {
        "type": "metric",
        "x": position["x"],
        "y": position["y"],
        "width": position["width"],
        "height": position["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Invocations",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "id": "m1",
                        "color": "#1f77b4",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "AWS/Lambda",
                    "Errors",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "id": "m2",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "singleValue",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Ingestor Invocations Summary",
            "period": 3600,
            "stat": "Sum",
            "setPeriodToTimeRange": True,
            "sparkline": False,
            "trend": False
        }
    }


def create_ingestor_errors_widget(coordinate_mapping):
    """Create dedicated Ingestor errors widget."""
    position = coordinate_mapping["new_widgets"]["ingestor_errors"]
    
    return {
        "type": "metric",
        "x": position["x"],
        "y": position["y"],
        "width": position["width"],
        "height": position["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Errors",
                    "FunctionName",
                    "${IngestorFunction}",
                    {
                        "id": "m1",
                        "visible": True,
                        "stat": "Sum",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Ingestor Errors",
            "period": 300,
            "stat": "Sum"
        }
    }


def find_insertion_point(widgets, target_y):
    """Find the insertion point for new widgets based on Y coordinate."""
    for i, widget in enumerate(widgets):
        if widget.get('y', 0) >= target_y:
            return i
    return len(widgets)


def add_ingestor_widgets():
    """Add all Ingestor widgets to the dashboard."""
    # Load coordinate mapping and template
    coordinate_mapping = load_coordinate_mapping()
    template = load_dashboard_template()
    
    # Parse dashboard body
    dashboard_body = template['Dashboard']['Properties']['DashboardBody']
    dashboard_data = parse_dashboard_body(dashboard_body)
    
    # Get existing widgets
    widgets = dashboard_data.get('widgets', [])
    
    # Create Ingestor widgets
    ingestor_widgets = [
        create_ingestor_invocations_errors_widget(coordinate_mapping),
        create_ingestor_duration_widget(coordinate_mapping),
        create_ingestor_concurrent_widget(coordinate_mapping),
        create_ingestor_summary_widget(coordinate_mapping),
        create_ingestor_errors_widget(coordinate_mapping)
    ]
    
    # Find insertion point (after Ingestor header)
    ingestor_header_y = coordinate_mapping["new_widgets"]["ingestor_header"]["y"]
    insertion_point = find_insertion_point(widgets, ingestor_header_y + 2)  # After header
    
    # Insert widgets
    for i, widget in enumerate(ingestor_widgets):
        widgets.insert(insertion_point + i, widget)
    
    # Update dashboard data
    dashboard_data['widgets'] = widgets
    
    # Update template
    template['Dashboard']['Properties']['DashboardBody'] = format_dashboard_body(dashboard_data)
    
    # Save template
    save_dashboard_template(template)
    
    print("Successfully added Ingestor widgets to dashboard template.")
    print(f"Added {len(ingestor_widgets)} Ingestor metrics widgets:")
    for widget in ingestor_widgets:
        title = widget['properties']['title']
        x, y = widget['x'], widget['y']
        print(f"  - {title} at position ({x}, {y})")


if __name__ == "__main__":
    add_ingestor_widgets()