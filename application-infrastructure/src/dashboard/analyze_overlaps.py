#!/usr/bin/env python3
"""
Analyze Dashboard Overlaps

This script analyzes the dashboard for overlapping widgets to understand
if overlaps are pre-existing or caused by header insertion.
"""

import sys
import os
import json
import yaml
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.layout_analyzer import DashboardLayoutAnalyzer


def load_dashboard_template():
    """Load the dashboard template."""
    current_dir = Path(__file__).parent
    template_path = current_dir / ".." / ".." / "template-dashboard.yml"
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def parse_dashboard_body(dashboard_body):
    """Parse the dashboard body from CloudFormation Fn::Sub format."""
    if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
        json_str = dashboard_body['Fn::Sub']
    else:
        json_str = dashboard_body
    
    return json.loads(json_str)


def analyze_dashboard_overlaps():
    """Analyze dashboard for overlapping widgets."""
    print("Analyzing dashboard for overlapping widgets...")
    
    # Load template
    template = load_dashboard_template()
    
    # Get dashboard body
    dashboard_body = template['Dashboard']['Properties']['DashboardBody']
    dashboard_data = parse_dashboard_body(dashboard_body)
    
    # Convert to JSON string for analysis
    dashboard_json = json.dumps(dashboard_data)
    
    # Analyze overlaps
    analyzer = DashboardLayoutAnalyzer(dashboard_json)
    overlapping_pairs = analyzer.find_overlapping_widgets()
    
    print(f"Found {len(overlapping_pairs)} overlapping widget pairs:")
    
    for i, (widget1, widget2) in enumerate(overlapping_pairs, 1):
        print(f"\n{i}. Overlap between:")
        print(f"   Widget 1: {widget1.type} at ({widget1.x}, {widget1.y}) size {widget1.width}x{widget1.height}")
        if widget1.type == 'text':
            markdown = widget1.properties.get('markdown', '')[:50]
            print(f"             Text: {markdown}...")
        elif widget1.type == 'metric':
            title = widget1.properties.get('title', 'No title')
            print(f"             Title: {title}")
        
        print(f"   Widget 2: {widget2.type} at ({widget2.x}, {widget2.y}) size {widget2.width}x{widget2.height}")
        if widget2.type == 'text':
            markdown = widget2.properties.get('markdown', '')[:50]
            print(f"             Text: {markdown}...")
        elif widget2.type == 'metric':
            title = widget2.properties.get('title', 'No title')
            print(f"             Title: {title}")
    
    # Show all widgets for reference
    print(f"\nAll widgets in dashboard ({len(analyzer.widgets)} total):")
    for i, widget in enumerate(analyzer.widgets):
        print(f"{i+1:2d}. {widget.type:6s} at ({widget.x:2d}, {widget.y:2d}) size {widget.width:2d}x{widget.height}")
        if widget.type == 'text':
            markdown = widget.properties.get('markdown', '')[:40]
            print(f"      Text: {markdown}...")
        elif widget.type == 'metric':
            title = widget.properties.get('title', 'No title')[:40]
            print(f"      Title: {title}")
        elif widget.type == 'log':
            title = widget.properties.get('title', 'No title')[:40]
            print(f"      Title: {title}")
        elif widget.type == 'alarm':
            print(f"      Alarms widget")


def main():
    """Main function."""
    try:
        analyze_dashboard_overlaps()
    except Exception as e:
        print(f"\n❌ Error analyzing dashboard: {e}")
        exit(1)


if __name__ == "__main__":
    main()