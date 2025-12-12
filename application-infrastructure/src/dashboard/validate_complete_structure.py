#!/usr/bin/env python3
"""Validate complete dashboard structure against all requirements."""

import sys
import os
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.dashboard_structure_analyzer import DashboardStructureAnalyzer
from dashboard.layout_analyzer import parse_dashboard_from_cloudformation_template


def load_dashboard_json() -> str:
    """Load dashboard JSON from CloudFormation template."""
    template_path = Path(__file__).parent.parent.parent / 'template-dashboard.yml'
    
    if not template_path.exists():
        raise FileNotFoundError(f"Dashboard template not found: {template_path}")
    
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    dashboard_json = parse_dashboard_from_cloudformation_template(template_content)
    
    if not dashboard_json:
        raise ValueError("Could not extract dashboard JSON from template")
    
    return dashboard_json


def validate_dashboard_structure() -> dict:
    """Validate complete dashboard structure and return results."""
    try:
        # Load dashboard JSON
        dashboard_json = load_dashboard_json()
        
        # Create analyzer
        analyzer = DashboardStructureAnalyzer(dashboard_json)
        
        # Perform validation
        validation_results = analyzer.validate_complete_structure()
        
        # Add section summary
        validation_results['section_summary'] = analyzer.get_section_metrics_summary()
        
        return validation_results
        
    except Exception as e:
        return {
            'overall_valid': False,
            'error': str(e),
            'issues': [f"Validation failed: {str(e)}"]
        }


def print_validation_results(results: dict):
    """Print validation results in a readable format."""
    print("=" * 60)
    print("DASHBOARD STRUCTURE VALIDATION RESULTS")
    print("=" * 60)
    
    # Overall status
    status = "✅ VALID" if results.get('overall_valid', False) else "❌ INVALID"
    print(f"\nOverall Status: {status}")
    
    if 'error' in results:
        print(f"\nError: {results['error']}")
        return
    
    # Widget positioning
    print(f"\n📍 Widget Positioning:")
    positioning = results.get('widget_positioning', {})
    if positioning.get('valid', False):
        print("  ✅ All widgets properly positioned")
    else:
        print(f"  ❌ Issues found:")
        print(f"    - Overlapping widgets: {positioning.get('overlapping_widgets', 0)}")
        print(f"    - Out of bounds widgets: {positioning.get('out_of_bounds_widgets', 0)}")
    
    # Section headers
    print(f"\n📋 Section Headers:")
    headers = results.get('section_headers', {})
    if headers.get('valid', False):
        print("  ✅ All required section headers present")
    else:
        missing = headers.get('missing_headers', [])
        print(f"  ❌ Missing headers: {', '.join(missing)}")
    
    headers_found = headers.get('headers_found', {})
    for header_name, found in headers_found.items():
        status_icon = "✅" if found else "❌"
        print(f"    {status_icon} {header_name.replace('_', ' ').title()}")
    
    # Metrics presence
    print(f"\n📊 Metrics Presence:")
    metrics = results.get('metrics_presence', {})
    if metrics.get('valid', False):
        print("  ✅ All required metrics present")
    else:
        print("  ❌ Missing metrics:")
        for missing_type in ['missing_ingestor', 'missing_event_queue', 'missing_dlq']:
            missing_list = metrics.get(missing_type, [])
            if missing_list:
                section_name = missing_type.replace('missing_', '').replace('_', ' ').title()
                print(f"    - {section_name}: {', '.join(missing_list)}")
    
    # Section summary
    print(f"\n📈 Section Summary:")
    section_summary = results.get('section_summary', {})
    for section_name, section_data in section_summary.items():
        metrics_count = len(section_data.get('metrics', set()))
        widget_count = section_data.get('widget_count', 0)
        section_display = section_name.replace('_', ' ').title()
        print(f"  {section_display}: {metrics_count} metrics, {widget_count} widgets")
    
    # Alarms configuration
    print(f"\n🚨 Alarms Configuration:")
    alarms = results.get('alarms_configuration', {})
    if alarms.get('valid', False):
        alarm_count = alarms.get('alarm_count', 0)
        print(f"  ✅ Alarms properly configured ({alarm_count} alarms)")
    else:
        print("  ❌ Alarms configuration issues found")
    
    # Grid compliance
    print(f"\n🔲 Grid Compliance:")
    grid = results.get('grid_compliance', {})
    if grid.get('valid', False):
        print("  ✅ All widgets comply with grid standards")
    else:
        non_standard = grid.get('non_standard_widgets', 0)
        out_of_bounds = grid.get('out_of_bounds_widgets', 0)
        print(f"  ❌ Grid compliance issues:")
        print(f"    - Non-standard width widgets: {non_standard}")
        print(f"    - Out of bounds widgets: {out_of_bounds}")
    
    # Issues summary
    all_issues = results.get('issues', [])
    if all_issues:
        print(f"\n⚠️  Issues Found ({len(all_issues)}):")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
    
    print("\n" + "=" * 60)


def main():
    """Main validation function."""
    print("Validating complete dashboard structure...")
    
    results = validate_dashboard_structure()
    print_validation_results(results)
    
    # Exit with appropriate code
    exit_code = 0 if results.get('overall_valid', False) else 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()