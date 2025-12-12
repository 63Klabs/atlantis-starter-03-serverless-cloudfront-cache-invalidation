#!/usr/bin/env python3
"""
Add Processor Section Header

This script adds the "Lambda Functions - Processor" section header to the
CloudWatch Dashboard template as specified in task 7 and requirements 4.3, 4.4, 4.5.
"""

import sys
import os
import json
import yaml
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.section_header_manager import add_processor_section_header, validate_processor_section_header


def load_dashboard_template():
    """Load the dashboard template."""
    # Get the path relative to the application-infrastructure directory
    current_dir = Path(__file__).parent
    template_path = current_dir / ".." / ".." / "template-dashboard.yml"
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def save_dashboard_template(template):
    """Save the dashboard template."""
    # Get the path relative to the application-infrastructure directory
    current_dir = Path(__file__).parent
    template_path = current_dir / ".." / ".." / "template-dashboard.yml"
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
    dashboard_json_str = json.dumps(dashboard_data, indent=2)
    return {"Fn::Sub": dashboard_json_str}


def add_processor_header_to_template():
    """Add Processor section header to the dashboard template."""
    print("Adding Processor section header to dashboard template...")
    
    # Load template
    template = load_dashboard_template()
    
    # Get dashboard body
    dashboard_body = template['Dashboard']['Properties']['DashboardBody']
    dashboard_data = parse_dashboard_body(dashboard_body)
    
    # Convert to JSON string for processing
    dashboard_json = json.dumps(dashboard_data)
    
    # Add Processor section header
    updated_dashboard_json = add_processor_section_header(dashboard_json)
    updated_dashboard_data = json.loads(updated_dashboard_json)
    
    # Update template
    template['Dashboard']['Properties']['DashboardBody'] = format_dashboard_body(updated_dashboard_data)
    
    # Save template
    save_dashboard_template(template)
    
    print("✓ Processor section header added successfully")
    
    # Validate the result
    print("\nValidating Processor section header...")
    validation_results = validate_processor_section_header(updated_dashboard_json)
    
    print(f"Header exists: {'✓' if validation_results['header_exists'] else '✗'}")
    print(f"Correct formatting: {'✓' if validation_results['correct_formatting'] else '✗'}")
    print(f"Proper positioning: {'✓' if validation_results['proper_positioning'] else '✗'}")
    print(f"Consistent with design: {'✓' if validation_results['consistent_with_design'] else '✗'}")
    print(f"No overlaps: {'✓' if validation_results['no_overlaps'] else '✗'}")
    print(f"Existing widgets preserved: {'✓' if validation_results['existing_widgets_preserved'] else '✗'}")
    
    if validation_results['issues']:
        print("\nIssues found:")
        for issue in validation_results['issues']:
            print(f"  - {issue}")
        return False
    else:
        print("\n🎉 All validation checks passed!")
        return True


def main():
    """Main function."""
    try:
        success = add_processor_header_to_template()
        if success:
            print("\n✅ Task 7: Add Processor function section header completed successfully!")
        else:
            print("\n❌ Task 7: Add Processor function section header failed validation!")
            exit(1)
    except Exception as e:
        print(f"\n❌ Error adding Processor section header: {e}")
        exit(1)


if __name__ == "__main__":
    main()