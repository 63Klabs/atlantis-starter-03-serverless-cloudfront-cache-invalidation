"""
Detailed coordinate mapping for CloudWatch Dashboard enhancement.

This module provides detailed coordinate mappings for all widgets in the enhanced dashboard layout.
"""

import json
from typing import Dict, Any
from .layout_plan import create_layout_plan


def generate_coordinate_mapping(template_path: str) -> Dict[str, Any]:
    """Generate complete coordinate mapping for dashboard enhancement.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Dictionary containing detailed coordinate mapping
    """
    plan = create_layout_plan(template_path)
    coordinate_mapping = plan.get_coordinate_mapping()
    layout_summary = plan.get_layout_summary()
    validation = plan.validate_layout_plan()
    
    # Create comprehensive mapping
    mapping = {
        'metadata': {
            'template_path': template_path,
            'total_widgets': layout_summary['total_widgets'],
            'new_widgets_count': layout_summary['new_widgets_count'],
            'moved_widgets_count': layout_summary['moved_widgets_count'],
            'max_y_coordinate': layout_summary['max_y_coordinate'],
            'validation_passed': all([
                validation['no_overlaps'],
                validation['within_grid_bounds'],
                validation['alarms_at_top'],
                validation['consistent_widths'],
                validation['has_all_sections']
            ])
        },
        'sections': layout_summary['sections_summary'],
        'y_coordinates': layout_summary['y_coordinates'],
        'current_positions': coordinate_mapping['current_positions'],
        'new_positions': coordinate_mapping['new_positions'],
        'new_widgets': coordinate_mapping['new_widgets'],
        'adjustments_summary': coordinate_mapping['adjustments_summary'],
        'validation_results': validation,
        'widget_details': _generate_widget_details(coordinate_mapping, layout_summary)
    }
    
    return mapping


def _generate_widget_details(coordinate_mapping: Dict[str, Any], 
                           layout_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Generate detailed widget information."""
    details = {
        'existing_widgets': {},
        'new_widgets': {},
        'moved_widgets': {},
        'unchanged_widgets': {}
    }
    
    current_positions = coordinate_mapping['current_positions']
    new_positions = coordinate_mapping['new_positions']
    new_widgets = coordinate_mapping['new_widgets']
    
    # Categorize widgets
    for widget_id in current_positions:
        if widget_id in new_positions:
            old_pos = current_positions[widget_id]
            new_pos = new_positions[widget_id]
            
            if (old_pos['x'] != new_pos['x'] or old_pos['y'] != new_pos['y'] or
                old_pos['width'] != new_pos['width'] or old_pos['height'] != new_pos['height']):
                details['moved_widgets'][widget_id] = {
                    'old_position': old_pos,
                    'new_position': new_pos,
                    'changes': {
                        'x_change': new_pos['x'] - old_pos['x'],
                        'y_change': new_pos['y'] - old_pos['y'],
                        'width_change': new_pos['width'] - old_pos['width'],
                        'height_change': new_pos['height'] - old_pos['height']
                    }
                }
            else:
                details['unchanged_widgets'][widget_id] = {
                    'position': old_pos
                }
        
        details['existing_widgets'][widget_id] = current_positions[widget_id]
    
    # Add new widgets
    for widget_id in new_widgets:
        details['new_widgets'][widget_id] = {
            'position': new_widgets[widget_id],
            'section': _determine_widget_section(widget_id)
        }
    
    return details


def _determine_widget_section(widget_id: str) -> str:
    """Determine which section a widget belongs to."""
    if 'ingestor' in widget_id:
        return 'ingestor'
    elif 'sqs' in widget_id:
        return 'sqs'
    elif 'processor' in widget_id:
        return 'processor'
    elif 'alarm' in widget_id:
        return 'alarms'
    elif 'title' in widget_id:
        return 'title'
    else:
        return 'logs'


def export_coordinate_mapping(template_path: str, output_path: str = None) -> str:
    """Export coordinate mapping to JSON file.
    
    Args:
        template_path: Path to the CloudFormation template file
        output_path: Path for output file (optional)
        
    Returns:
        Path to the exported file
    """
    mapping = generate_coordinate_mapping(template_path)
    
    if output_path is None:
        output_path = 'dashboard_coordinate_mapping.json'
    
    with open(output_path, 'w') as f:
        json.dump(mapping, f, indent=2)
    
    return output_path


def print_coordinate_mapping_summary(template_path: str) -> None:
    """Print a detailed summary of the coordinate mapping."""
    mapping = generate_coordinate_mapping(template_path)
    
    print("=== Coordinate Mapping Summary ===\n")
    
    # Metadata
    metadata = mapping['metadata']
    print("Metadata:")
    print(f"  Template: {metadata['template_path']}")
    print(f"  Total widgets: {metadata['total_widgets']}")
    print(f"  New widgets: {metadata['new_widgets_count']}")
    print(f"  Moved widgets: {metadata['moved_widgets_count']}")
    print(f"  Max Y coordinate: {metadata['max_y_coordinate']}")
    print(f"  Validation passed: {metadata['validation_passed']}")
    print()
    
    # Sections
    print("Sections Layout:")
    for section, data in mapping['sections'].items():
        print(f"  {section.title()}: Y {data['start_y']}-{data['start_y'] + data['height']} "
              f"(Height: {data['height']}, Widgets: {data['widget_count']})")
    print()
    
    # Widget details
    details = mapping['widget_details']
    
    print("New Widgets:")
    for widget_id, data in details['new_widgets'].items():
        pos = data['position']
        print(f"  {widget_id}: ({pos['x']}, {pos['y']}) {pos['width']}x{pos['height']} [{data['section']}]")
    print()
    
    print("Moved Widgets:")
    for widget_id, data in details['moved_widgets'].items():
        old = data['old_position']
        new = data['new_position']
        changes = data['changes']
        print(f"  {widget_id}:")
        print(f"    Old: ({old['x']}, {old['y']}) {old['width']}x{old['height']}")
        print(f"    New: ({new['x']}, {new['y']}) {new['width']}x{new['height']}")
        if changes['x_change'] != 0 or changes['y_change'] != 0:
            print(f"    Change: X{changes['x_change']:+d}, Y{changes['y_change']:+d}")
    print()
    
    print("Unchanged Widgets:")
    for widget_id, data in details['unchanged_widgets'].items():
        pos = data['position']
        print(f"  {widget_id}: ({pos['x']}, {pos['y']}) {pos['width']}x{pos['height']}")
    print()
    
    # Validation results
    validation = mapping['validation_results']
    print("Validation Results:")
    print(f"  No overlaps: {validation['no_overlaps']}")
    print(f"  Within grid bounds: {validation['within_grid_bounds']}")
    print(f"  Alarms at top: {validation['alarms_at_top']}")
    print(f"  Consistent widths: {validation['consistent_widths']}")
    print(f"  Has all sections: {validation['has_all_sections']}")
    
    if validation['issues']:
        print("  Issues:")
        for issue in validation['issues']:
            print(f"    - {issue}")
    print()


def get_widget_positioning_requirements() -> Dict[str, Any]:
    """Get the positioning requirements for all new widgets.
    
    Returns:
        Dictionary containing positioning requirements for implementation
    """
    return {
        'alarms_repositioning': {
            'description': 'Move alarms widget to top position after title',
            'requirements': ['3.3', '5.1', '5.3', '5.4', '5.5'],
            'new_position': {
                'x': 0,
                'y': 'title_height',  # After title widget
                'width': 24,  # Full width for visibility
                'height': 'current_height'  # Keep existing height
            }
        },
        'ingestor_section': {
            'description': 'Add Ingestor Lambda function monitoring section',
            'requirements': ['1.1', '1.2', '1.3', '1.4', '1.5', '4.1', '4.4', '4.5'],
            'widgets': {
                'header': {
                    'type': 'text',
                    'content': '## Lambda Functions - Ingestor',
                    'position': {'x': 0, 'y': 'after_alarms', 'width': 24, 'height': 2}
                },
                'invocations_errors': {
                    'type': 'metric',
                    'metrics': ['Invocations', 'Errors'],
                    'position': {'x': 0, 'y': 'after_header', 'width': 6, 'height': 7}
                },
                'duration': {
                    'type': 'metric',
                    'metrics': ['Duration (Avg, Min, Max)'],
                    'position': {'x': 6, 'y': 'after_header', 'width': 6, 'height': 7}
                },
                'concurrent': {
                    'type': 'metric',
                    'metrics': ['ConcurrentExecutions'],
                    'position': {'x': 12, 'y': 'after_header', 'width': 6, 'height': 7}
                },
                'summary': {
                    'type': 'metric',
                    'view': 'singleValue',
                    'metrics': ['Invocations', 'Errors'],
                    'position': {'x': 18, 'y': 'after_header', 'width': 6, 'height': 5}
                }
            }
        },
        'sqs_section': {
            'description': 'Add SQS queue monitoring section',
            'requirements': ['2.1', '2.2', '2.3', '2.4', '4.2', '4.4', '4.5'],
            'widgets': {
                'header': {
                    'type': 'text',
                    'content': '## SQS Queues',
                    'position': {'x': 0, 'y': 'after_ingestor', 'width': 24, 'height': 2}
                },
                'message_counts': {
                    'type': 'metric',
                    'metrics': ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesVisible'],
                    'position': {'x': 0, 'y': 'after_header', 'width': 6, 'height': 7}
                },
                'message_age': {
                    'type': 'metric',
                    'metrics': ['ApproximateAgeOfOldestMessage'],
                    'position': {'x': 6, 'y': 'after_header', 'width': 6, 'height': 7}
                },
                'dlq_monitoring': {
                    'type': 'metric',
                    'metrics': ['DLQ ApproximateNumberOfMessages'],
                    'position': {'x': 12, 'y': 'after_header', 'width': 6, 'height': 7}
                },
                'send_receive_rates': {
                    'type': 'metric',
                    'metrics': ['NumberOfMessagesSent', 'NumberOfMessagesReceived'],
                    'position': {'x': 18, 'y': 'after_header', 'width': 6, 'height': 7}
                }
            }
        },
        'processor_section': {
            'description': 'Add header for existing Processor section',
            'requirements': ['3.5', '4.3', '4.4', '4.5'],
            'widgets': {
                'header': {
                    'type': 'text',
                    'content': '## Lambda Functions - Processor',
                    'position': {'x': 0, 'y': 'after_sqs', 'width': 24, 'height': 2}
                }
            }
        },
        'coordinate_adjustments': {
            'description': 'Adjust existing widget coordinates',
            'requirements': ['3.1', '3.4', '3.5', '5.4'],
            'adjustments': {
                'all_non_title_widgets': 'Shift Y coordinates to accommodate alarms at top',
                'processor_widgets': 'Shift Y coordinates to accommodate new sections above',
                'log_widgets': 'Shift Y coordinates to accommodate all new sections above'
            }
        }
    }


if __name__ == "__main__":
    # Example usage
    template_path = "../template-dashboard.yml"
    try:
        print_coordinate_mapping_summary(template_path)
        
        # Export to file
        output_file = export_coordinate_mapping(template_path, "coordinate_mapping.json")
        print(f"\nCoordinate mapping exported to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()