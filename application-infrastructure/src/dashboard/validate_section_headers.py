#!/usr/bin/env python3
"""
Script to validate and adjust section header formatting in the CloudWatch Dashboard.
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.section_header_validator import SectionHeaderValidator


def main():
    """Main function to validate and adjust section header formatting."""
    template_path = os.path.join(os.path.dirname(__file__), '../../template-dashboard.yml')
    
    validator = SectionHeaderValidator(template_path)
    
    print("=== Section Header Formatting Report ===")
    
    # Get current state
    report = validator.get_header_formatting_report()
    
    print(f"Total text headers: {report['total_headers']}")
    print(f"Compliant headers: {report['compliant_headers']}")
    print(f"Non-compliant headers: {report['non_compliant_headers']}")
    print(f"Compliance rate: {report['compliance_rate']:.2%}")
    
    print(f"\nStandard requirements:")
    print(f"  Width: {report['standard_requirements']['width']}")
    print(f"  Height: {report['standard_requirements']['height']} (for section headers)")
    print(f"  X position: {report['standard_requirements']['x']}")
    
    print("\n=== Header Type Distribution ===")
    for header_type, counts in report['header_type_distribution'].items():
        total = counts['compliant'] + counts['non_compliant']
        print(f"{header_type}: {total} headers ({counts['compliant']} compliant, {counts['non_compliant']} non-compliant)")
    
    if report['compliant_headers'] > 0:
        print("\n=== Compliant Headers ===")
        for header in report['compliant_details']:
            print(f"Header {header['index']} ({header['type']}): "
                  f"x={header['x']}, y={header['y']}, w={header['width']}, h={header['height']} - "
                  f"'{header['markdown']}'")
    
    if report['non_compliant_headers'] > 0:
        print("\n=== Non-Compliant Headers ===")
        for header in report['non_compliant_details']:
            print(f"Header {header['index']} ({header['type']}): "
                  f"x={header['x']}, y={header['y']}, w={header['width']}, h={header['height']} - "
                  f"'{header['markdown']}'")
            for issue in header['issues']:
                print(f"  Issue: {issue}")
        
        print("\n=== Adjusting Header Formatting ===")
        adjustments = validator.adjust_section_headers()
        
        print(f"Total adjustments made: {adjustments['total_adjustments']}")
        for adjustment in adjustments['adjustments_made']:
            print(f"Header {adjustment['index']} ({adjustment['type']}): '{adjustment['markdown']}'")
            for change in adjustment['changes']:
                print(f"  Changed: {change}")
        
        print("\n=== Post-Adjustment Report ===")
        final_report = validator.get_header_formatting_report()
        print(f"Final compliance rate: {final_report['compliance_rate']:.2%}")
    else:
        print("\n✅ All headers already have consistent formatting!")
    
    print("\n=== Section Structure Analysis ===")
    sections = validator.find_section_headers_and_metrics()
    
    for section_name, section_data in sections.items():
        header_y = section_data['header']['y']
        metrics_count = len(section_data['metrics'])
        print(f"Section '{section_name}' at y={header_y}: {metrics_count} metric/log widgets")
        
        # Check if metrics are positioned correctly relative to header
        for metric in section_data['metrics']:
            metric_y = metric['y']
            if metric_y <= header_y:
                print(f"  ⚠️  Metric {metric['index']} at y={metric_y} is above or at header level")
            else:
                print(f"  ✅ Metric {metric['index']} at y={metric_y} is correctly positioned below header")


if __name__ == "__main__":
    main()