"""
Alarm widget configuration validator for CloudWatch Dashboard enhancement.

This module implements validation and updating of the alarms widget configuration
to ensure all required alarm references are included, as specified in requirement 5.2.
"""

import json
from typing import Dict, List, Any, Optional, Set, Tuple


class AlarmValidator:
    """Validates and updates alarm widget configuration."""
    
    def __init__(self, dashboard_json: str):
        """Initialize with dashboard JSON.
        
        Args:
            dashboard_json: JSON string containing dashboard configuration
        """
        self.dashboard_data = json.loads(dashboard_json)
        self.widgets = self.dashboard_data.get('widgets', [])
    
    def validate_alarm_references(self) -> Dict[str, Any]:
        """Validate that all required alarm references are present.
        
        Returns:
            Dictionary containing validation results
        """
        required_alarms = {
            'IngestorFunctionErrorsAlarm',      # Ingestor function alarm
            'ProcessorFunctionErrorsAlarm',     # Processor function error alarm
            'ProcessorFunctionDurationAlarm',   # Processor function duration alarm
            'DLQMessageAlarm'                   # Dead Letter Queue alarm
        }
        
        validation_results = {
            'has_alarm_widget': False,
            'all_alarms_present': False,
            'missing_alarms': set(),
            'extra_alarms': set(),
            'present_alarms': set(),
            'alarm_arn_format_valid': True,
            'issues': []
        }
        
        # Find alarm widget
        alarm_widget = self._find_alarm_widget()
        
        if not alarm_widget:
            validation_results['issues'].append("No alarm widget found in dashboard")
            validation_results['missing_alarms'] = required_alarms
            return validation_results
        
        validation_results['has_alarm_widget'] = True
        
        # Extract alarm references
        actual_alarms = self._extract_alarm_references(alarm_widget)
        validation_results['present_alarms'] = actual_alarms
        
        # Check completeness
        missing_alarms = required_alarms - actual_alarms
        extra_alarms = actual_alarms - required_alarms
        
        validation_results['missing_alarms'] = missing_alarms
        validation_results['extra_alarms'] = extra_alarms
        validation_results['all_alarms_present'] = len(missing_alarms) == 0
        
        # Validate ARN format
        arn_validation = self._validate_alarm_arn_format(alarm_widget)
        validation_results['alarm_arn_format_valid'] = arn_validation['valid']
        if not arn_validation['valid']:
            validation_results['issues'].extend(arn_validation['issues'])
        
        # Add summary issues
        if missing_alarms:
            validation_results['issues'].append(f"Missing required alarms: {', '.join(missing_alarms)}")
        
        if extra_alarms:
            validation_results['issues'].append(f"Extra alarms found: {', '.join(extra_alarms)}")
        
        return validation_results
    
    def update_alarm_widget_configuration(self) -> str:
        """Update alarm widget to include all required alarm references.
        
        Returns:
            Updated dashboard JSON string with corrected alarm configuration
        """
        required_alarms = [
            'IngestorFunctionErrorsAlarm',
            'ProcessorFunctionErrorsAlarm', 
            'ProcessorFunctionDurationAlarm',
            'DLQMessageAlarm'
        ]
        
        # Find alarm widget
        alarm_widget_index = self._find_alarm_widget_index()
        
        if alarm_widget_index is None:
            raise ValueError("No alarm widget found in dashboard")
        
        # Create updated alarm widget with all required references
        updated_alarm_widget = self._create_updated_alarm_widget(required_alarms)
        
        # Update dashboard
        updated_dashboard = self.dashboard_data.copy()
        updated_dashboard['widgets'][alarm_widget_index] = updated_alarm_widget
        
        return json.dumps(updated_dashboard, indent=2)
    
    def _find_alarm_widget(self) -> Optional[Dict[str, Any]]:
        """Find the alarm widget in the dashboard."""
        for widget in self.widgets:
            if widget.get('type') == 'alarm':
                return widget
        return None
    
    def _find_alarm_widget_index(self) -> Optional[int]:
        """Find the index of the alarm widget in the dashboard."""
        for i, widget in enumerate(self.widgets):
            if widget.get('type') == 'alarm':
                return i
        return None
    
    def _extract_alarm_references(self, alarm_widget: Dict[str, Any]) -> Set[str]:
        """Extract alarm names from alarm widget ARNs."""
        alarm_references = set()
        
        properties = alarm_widget.get('properties', {})
        alarms = properties.get('alarms', [])
        
        for alarm_arn in alarms:
            if isinstance(alarm_arn, str) and ':alarm:' in alarm_arn:
                # Extract alarm name from ARN
                # Expected format: arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${AlarmName}
                alarm_name = alarm_arn.split(':alarm:')[-1]
                # Remove CloudFormation parameter syntax if present
                if alarm_name.startswith('${') and alarm_name.endswith('}'):
                    alarm_name = alarm_name[2:-1]
                alarm_references.add(alarm_name)
        
        return alarm_references
    
    def _validate_alarm_arn_format(self, alarm_widget: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that alarm ARNs follow the correct format."""
        validation = {
            'valid': True,
            'issues': []
        }
        
        properties = alarm_widget.get('properties', {})
        alarms = properties.get('alarms', [])
        
        for alarm_arn in alarms:
            if not isinstance(alarm_arn, str):
                validation['valid'] = False
                validation['issues'].append(f"Alarm ARN should be string, got {type(alarm_arn)}")
                continue
            
            if not alarm_arn.startswith('arn:aws:cloudwatch:'):
                validation['valid'] = False
                validation['issues'].append(f"Alarm ARN should start with 'arn:aws:cloudwatch:', got {alarm_arn}")
                continue
            
            if ':alarm:' not in alarm_arn:
                validation['valid'] = False
                validation['issues'].append(f"Alarm ARN should contain ':alarm:', got {alarm_arn}")
                continue
            
            # Check for CloudFormation parameter references
            if '${AWS::Region}' not in alarm_arn:
                validation['valid'] = False
                validation['issues'].append(f"Alarm ARN should reference AWS::Region parameter, got {alarm_arn}")
            
            if '${AWS::AccountId}' not in alarm_arn:
                validation['valid'] = False
                validation['issues'].append(f"Alarm ARN should reference AWS::AccountId parameter, got {alarm_arn}")
        
        return validation
    
    def _create_updated_alarm_widget(self, required_alarms: List[str]) -> Dict[str, Any]:
        """Create updated alarm widget with all required alarm references."""
        # Get existing alarm widget as base
        existing_alarm_widget = self._find_alarm_widget()
        
        if not existing_alarm_widget:
            raise ValueError("No existing alarm widget found")
        
        # Create alarm ARNs for all required alarms
        alarm_arns = []
        for alarm_name in required_alarms:
            arn = f"arn:aws:cloudwatch:${{AWS::Region}}:${{AWS::AccountId}}:alarm:${{{alarm_name}}}"
            alarm_arns.append(arn)
        
        # Create updated widget preserving existing structure
        updated_widget = existing_alarm_widget.copy()
        updated_widget['properties'] = updated_widget.get('properties', {}).copy()
        updated_widget['properties']['alarms'] = alarm_arns
        
        # Ensure title is set
        if 'title' not in updated_widget['properties']:
            updated_widget['properties']['title'] = 'Alarms'
        
        return updated_widget
    
    def get_alarm_coverage_report(self) -> Dict[str, Any]:
        """Get detailed report on alarm coverage by function type.
        
        Returns:
            Dictionary containing coverage analysis by function type
        """
        validation = self.validate_alarm_references()
        present_alarms = validation['present_alarms']
        
        # Categorize alarms by function type
        ingestor_alarms = {'IngestorFunctionErrorsAlarm'}
        processor_alarms = {'ProcessorFunctionErrorsAlarm', 'ProcessorFunctionDurationAlarm'}
        infrastructure_alarms = {'DLQMessageAlarm'}
        
        coverage_report = {
            'ingestor_coverage': {
                'required': ingestor_alarms,
                'present': present_alarms.intersection(ingestor_alarms),
                'missing': ingestor_alarms - present_alarms,
                'complete': ingestor_alarms.issubset(present_alarms)
            },
            'processor_coverage': {
                'required': processor_alarms,
                'present': present_alarms.intersection(processor_alarms),
                'missing': processor_alarms - present_alarms,
                'complete': processor_alarms.issubset(present_alarms)
            },
            'infrastructure_coverage': {
                'required': infrastructure_alarms,
                'present': present_alarms.intersection(infrastructure_alarms),
                'missing': infrastructure_alarms - present_alarms,
                'complete': infrastructure_alarms.issubset(present_alarms)
            },
            'overall_complete': validation['all_alarms_present']
        }
        
        return coverage_report


def validate_alarm_references(dashboard_json: str) -> Dict[str, Any]:
    """Convenience function to validate alarm references in dashboard.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Dictionary containing validation results
    """
    validator = AlarmValidator(dashboard_json)
    return validator.validate_alarm_references()


def update_alarm_widget_configuration(dashboard_json: str) -> str:
    """Convenience function to update alarm widget configuration.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Updated dashboard JSON string with corrected alarm configuration
    """
    validator = AlarmValidator(dashboard_json)
    return validator.update_alarm_widget_configuration()


def get_alarm_coverage_report(dashboard_json: str) -> Dict[str, Any]:
    """Convenience function to get alarm coverage report.
    
    Args:
        dashboard_json: JSON string containing dashboard configuration
        
    Returns:
        Dictionary containing coverage analysis by function type
    """
    validator = AlarmValidator(dashboard_json)
    return validator.get_alarm_coverage_report()