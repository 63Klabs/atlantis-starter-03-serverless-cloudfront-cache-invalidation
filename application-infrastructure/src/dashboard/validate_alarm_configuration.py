#!/usr/bin/env python3
"""
Validate alarm configuration in CloudWatch Dashboard template.

This script validates that the dashboard template includes all required alarm references
and that they are properly formatted according to requirement 5.2.
"""

import sys
import os
import json
import yaml

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.alarm_validator import AlarmValidator


def extract_dashboard_json_from_template(template_path: str) -> str:
    """Extract dashboard JSON from CloudFormation template.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Dashboard JSON string
    """
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Parse YAML template
    template_data = yaml.safe_load(template_content)
    
    # Check if this is a complete template with Resources section
    if 'Resources' in template_data:
        # Find Dashboard resource
        resources = template_data.get('Resources', {})
        dashboard_resource = None
        
        for resource_name, resource_data in resources.items():
            if resource_data.get('Type') == 'AWS::CloudWatch::Dashboard':
                dashboard_resource = resource_data
                break
        
        if not dashboard_resource:
            raise ValueError("No CloudWatch Dashboard resource found in template")
    elif 'Dashboard' in template_data:
        # This might be a template fragment with Dashboard as top-level key
        dashboard_resource = template_data['Dashboard']
        if dashboard_resource.get('Type') != 'AWS::CloudWatch::Dashboard':
            raise ValueError("Dashboard resource is not of correct type")
    else:
        # This might be just the Dashboard resource definition
        if template_data.get('Type') == 'AWS::CloudWatch::Dashboard':
            dashboard_resource = template_data
        else:
            raise ValueError("No CloudWatch Dashboard resource found in template")
    
    # Extract dashboard body
    properties = dashboard_resource.get('Properties', {})
    dashboard_body = properties.get('DashboardBody', {})
    
    if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
        # Extract the JSON string from Fn::Sub
        dashboard_json_str = dashboard_body['Fn::Sub']
        
        # Parse the JSON string (it may have CloudFormation substitutions)
        try:
            # Try to parse as JSON to validate structure
            dashboard_data = json.loads(dashboard_json_str)
            return dashboard_json_str
        except json.JSONDecodeError as e:
            print(f"Warning: Dashboard JSON contains CloudFormation substitutions: {e}")
            return dashboard_json_str
    else:
        raise ValueError("Unexpected dashboard body format")


def validate_dashboard_template(template_path: str) -> None:
    """Validate alarm configuration in dashboard template.
    
    Args:
        template_path: Path to the CloudFormation template file
    """
    print(f"Validating alarm configuration in: {template_path}")
    print("=" * 60)
    
    try:
        # Extract dashboard JSON from template
        dashboard_json = extract_dashboard_json_from_template(template_path)
        
        # Create validator
        validator = AlarmValidator(dashboard_json)
        
        # Validate alarm references
        validation_results = validator.validate_alarm_references()
        
        print("Alarm Widget Validation Results:")
        print("-" * 40)
        print(f"Has alarm widget: {validation_results['has_alarm_widget']}")
        print(f"All alarms present: {validation_results['all_alarms_present']}")
        print(f"ARN format valid: {validation_results['alarm_arn_format_valid']}")
        
        if validation_results['present_alarms']:
            print(f"Present alarms: {', '.join(sorted(validation_results['present_alarms']))}")
        
        if validation_results['missing_alarms']:
            print(f"Missing alarms: {', '.join(sorted(validation_results['missing_alarms']))}")
        
        if validation_results['extra_alarms']:
            print(f"Extra alarms: {', '.join(sorted(validation_results['extra_alarms']))}")
        
        if validation_results['issues']:
            print("\nIssues found:")
            for issue in validation_results['issues']:
                print(f"  - {issue}")
        
        # Get coverage report
        coverage_report = validator.get_alarm_coverage_report()
        
        print("\nAlarm Coverage by Function Type:")
        print("-" * 40)
        
        for function_type, coverage in coverage_report.items():
            if function_type == 'overall_complete':
                continue
                
            print(f"{function_type.replace('_', ' ').title()}:")
            print(f"  Required: {', '.join(sorted(coverage['required']))}")
            print(f"  Present: {', '.join(sorted(coverage['present']))}")
            print(f"  Complete: {coverage['complete']}")
            
            if coverage['missing']:
                print(f"  Missing: {', '.join(sorted(coverage['missing']))}")
        
        print(f"\nOverall Complete: {coverage_report['overall_complete']}")
        
        # Summary
        print("\n" + "=" * 60)
        if validation_results['all_alarms_present'] and validation_results['alarm_arn_format_valid']:
            print("✅ VALIDATION PASSED: All required alarms are present and properly formatted")
            return True
        else:
            print("❌ VALIDATION FAILED: Issues found with alarm configuration")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to validate template: {e}")
        return False


def main():
    """Main function."""
    # Default template path
    template_path = os.path.join(
        os.path.dirname(__file__), 
        '..', '..', 
        'template-dashboard.yml'
    )
    
    # Allow custom template path as command line argument
    if len(sys.argv) > 1:
        template_path = sys.argv[1]
    
    if not os.path.exists(template_path):
        print(f"❌ ERROR: Template file not found: {template_path}")
        sys.exit(1)
    
    success = validate_dashboard_template(template_path)
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()