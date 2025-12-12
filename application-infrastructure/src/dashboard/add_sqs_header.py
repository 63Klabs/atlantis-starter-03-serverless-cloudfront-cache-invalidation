#!/usr/bin/env python3
"""
Script to add SQS queues section header to CloudWatch Dashboard.

This script implements task 5 from the implementation plan:
- Create "SQS Queues" text header widget
- Position header widget above SQS metrics section  
- Ensure consistent formatting and positioning
- Requirements: 4.2, 4.4, 4.5
"""

import json
import yaml
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from dashboard.section_header_manager import SectionHeaderManager


def extract_dashboard_json_from_template(template_path: str) -> str:
    """Extract dashboard JSON from CloudFormation template.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Dashboard JSON string
    """
    with open(template_path, 'r') as f:
        template_data = yaml.safe_load(f)
    
    # Navigate to dashboard body
    dashboard_body = template_data['Dashboard']['Properties']['DashboardBody']['Fn::Sub']
    
    # The dashboard body is a JSON string with CloudFormation substitutions
    # For processing, we need to handle the substitution variables
    return dashboard_body


def update_template_with_dashboard(template_path: str, updated_dashboard_json: str) -> None:
    """Update CloudFormation template with modified dashboard JSON.
    
    Args:
        template_path: Path to the CloudFormation template file
        updated_dashboard_json: Updated dashboard JSON string
    """
    with open(template_path, 'r') as f:
        template_data = yaml.safe_load(f)
    
    # Update dashboard body
    template_data['Dashboard']['Properties']['DashboardBody']['Fn::Sub'] = updated_dashboard_json
    
    # Write back to template
    with open(template_path, 'w') as f:
        yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)


def add_sqs_header_to_template(template_path: str) -> Dict[str, Any]:
    """Add SQS section header to dashboard template.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Dictionary with operation results and validation
    """
    print(f"Processing template: {template_path}")
    
    # Extract current dashboard JSON
    dashboard_json = extract_dashboard_json_from_template(template_path)
    print("Extracted dashboard JSON from template")
    
    # Create section header manager
    manager = SectionHeaderManager(dashboard_json)
    
    # Add SQS section header
    updated_dashboard_json = manager.add_sqs_section_header()
    print("Added SQS section header")
    
    # Validate the changes
    validation_results = manager.validate_sqs_header()
    print("Validated header addition")
    
    # Update template file
    update_template_with_dashboard(template_path, updated_dashboard_json)
    print("Updated template file")
    
    return {
        'success': True,
        'validation': validation_results,
        'template_updated': True
    }


def main():
    """Main function to add SQS section header."""
    template_path = "application-infrastructure/template-dashboard.yml"
    
    try:
        # Check if template exists
        if not Path(template_path).exists():
            print(f"Error: Template file not found: {template_path}")
            sys.exit(1)
        
        # Add SQS header
        results = add_sqs_header_to_template(template_path)
        
        # Print results
        print("\n=== SQS Section Header Addition Results ===")
        print(f"Success: {results['success']}")
        print(f"Template updated: {results['template_updated']}")
        
        validation = results['validation']
        print("\nValidation Results:")
        print(f"  Header exists: {validation['header_exists']}")
        print(f"  Correct formatting: {validation['correct_formatting']}")
        print(f"  Proper positioning: {validation['proper_positioning']}")
        print(f"  Consistent with design: {validation['consistent_with_design']}")
        print(f"  No overlaps: {validation['no_overlaps']}")
        
        if validation['issues']:
            print("\nIssues found:")
            for issue in validation['issues']:
                print(f"  - {issue}")
        else:
            print("\nNo issues found - header successfully added!")
        
        # Summary
        all_checks_passed = all([
            validation['header_exists'],
            validation['correct_formatting'],
            validation['proper_positioning'],
            validation['consistent_with_design'],
            validation['no_overlaps']
        ])
        
        if all_checks_passed:
            print("\n✅ Task 5 completed successfully!")
            print("SQS queues section header has been added with:")
            print("- Correct 'SQS Queues' text")
            print("- Proper positioning above SQS metrics section (y=22)")
            print("- Consistent formatting (24 width, 2 height, H2 markdown)")
            print("- No widget overlaps")
        else:
            print("\n❌ Task 5 completed with issues - see validation results above")
        
    except Exception as e:
        print(f"Error adding SQS section header: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()