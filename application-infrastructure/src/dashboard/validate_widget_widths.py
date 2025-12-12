#!/usr/bin/env python3
"""
Script to validate and adjust widget widths in the CloudWatch Dashboard.
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.widget_width_validator import WidgetWidthValidator


def main():
    """Main function to validate and adjust widget widths."""
    template_path = os.path.join(os.path.dirname(__file__), '../../template-dashboard.yml')
    
    validator = WidgetWidthValidator(template_path)
    
    print("=== Widget Width Validation Report ===")
    
    # Get current state
    report = validator.get_width_consistency_report()
    
    print(f"Total widgets: {report['total_widgets']}")
    print(f"Compliant widgets: {report['compliant_widgets']}")
    print(f"Non-compliant widgets: {report['non_compliant_widgets']}")
    print(f"Compliance rate: {report['compliance_rate']:.2%}")
    print(f"Standard widths: {report['standard_widths']}")
    
    print("\n=== Width Distribution ===")
    for width, counts in sorted(report['width_distribution'].items()):
        total = counts['compliant'] + counts['non_compliant']
        print(f"Width {width}: {total} widgets ({counts['compliant']} compliant, {counts['non_compliant']} non-compliant)")
    
    if report['non_compliant_widgets'] > 0:
        print("\n=== Non-Compliant Widgets ===")
        for widget in report['non_compliant_details']:
            print(f"Widget {widget['index']} ({widget['type']}): x={widget['x']}, "
                  f"current_width={widget['current_width']}, suggested_width={widget['suggested_width']}")
        
        print("\n=== Adjusting Widget Widths ===")
        adjustments = validator.adjust_widget_widths()
        
        print(f"Total adjustments made: {adjustments['total_adjustments']}")
        for adjustment in adjustments['adjustments_made']:
            print(f"Widget {adjustment['index']} ({adjustment['type']}): "
                  f"{adjustment['old_width']} -> {adjustment['new_width']}")
        
        print("\n=== Post-Adjustment Report ===")
        final_report = validator.get_width_consistency_report()
        print(f"Final compliance rate: {final_report['compliance_rate']:.2%}")
    else:
        print("\n✅ All widgets already have consistent widths!")


if __name__ == "__main__":
    main()