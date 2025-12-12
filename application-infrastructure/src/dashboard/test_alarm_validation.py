#!/usr/bin/env python3
"""
Test alarm validation functionality with sample dashboard JSON.
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.alarm_validator import AlarmValidator


def test_complete_alarm_dashboard():
    """Test validation with a complete alarm dashboard."""
    dashboard_json = json.dumps({
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# Test Dashboard"
                }
            },
            {
                "type": "alarm",
                "x": 0,
                "y": 2,
                "width": 24,
                "height": 4,
                "properties": {
                    "title": "Alarms",
                    "alarms": [
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${IngestorFunctionErrorsAlarm}",
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${ProcessorFunctionErrorsAlarm}",
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${ProcessorFunctionDurationAlarm}",
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${DLQMessageAlarm}"
                    ]
                }
            }
        ]
    })
    
    validator = AlarmValidator(dashboard_json)
    validation_results = validator.validate_alarm_references()
    
    print("Complete Dashboard Test:")
    print(f"  Has alarm widget: {validation_results['has_alarm_widget']}")
    print(f"  All alarms present: {validation_results['all_alarms_present']}")
    print(f"  ARN format valid: {validation_results['alarm_arn_format_valid']}")
    print(f"  Present alarms: {', '.join(sorted(validation_results['present_alarms']))}")
    
    assert validation_results['has_alarm_widget']
    assert validation_results['all_alarms_present']
    assert validation_results['alarm_arn_format_valid']
    assert len(validation_results['issues']) == 0
    
    print("  ✅ PASSED")


def test_incomplete_alarm_dashboard():
    """Test validation with an incomplete alarm dashboard."""
    dashboard_json = json.dumps({
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# Test Dashboard"
                }
            },
            {
                "type": "alarm",
                "x": 0,
                "y": 2,
                "width": 24,
                "height": 4,
                "properties": {
                    "title": "Alarms",
                    "alarms": [
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${ProcessorFunctionErrorsAlarm}",
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${ProcessorFunctionDurationAlarm}"
                    ]
                }
            }
        ]
    })
    
    validator = AlarmValidator(dashboard_json)
    validation_results = validator.validate_alarm_references()
    
    print("\nIncomplete Dashboard Test:")
    print(f"  Has alarm widget: {validation_results['has_alarm_widget']}")
    print(f"  All alarms present: {validation_results['all_alarms_present']}")
    print(f"  Present alarms: {', '.join(sorted(validation_results['present_alarms']))}")
    print(f"  Missing alarms: {', '.join(sorted(validation_results['missing_alarms']))}")
    
    assert validation_results['has_alarm_widget']
    assert not validation_results['all_alarms_present']
    assert 'IngestorFunctionErrorsAlarm' in validation_results['missing_alarms']
    assert 'DLQMessageAlarm' in validation_results['missing_alarms']
    
    print("  ✅ PASSED")


def test_alarm_update():
    """Test updating alarm configuration."""
    incomplete_dashboard_json = json.dumps({
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# Test Dashboard"
                }
            },
            {
                "type": "alarm",
                "x": 0,
                "y": 2,
                "width": 24,
                "height": 4,
                "properties": {
                    "title": "Alarms",
                    "alarms": [
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${ProcessorFunctionErrorsAlarm}"
                    ]
                }
            }
        ]
    })
    
    validator = AlarmValidator(incomplete_dashboard_json)
    
    # Verify it's incomplete
    validation_before = validator.validate_alarm_references()
    assert not validation_before['all_alarms_present']
    
    # Update configuration
    updated_dashboard_json = validator.update_alarm_widget_configuration()
    
    # Verify it's now complete
    updated_validator = AlarmValidator(updated_dashboard_json)
    validation_after = updated_validator.validate_alarm_references()
    
    print("\nAlarm Update Test:")
    print(f"  Before update - All alarms present: {validation_before['all_alarms_present']}")
    print(f"  After update - All alarms present: {validation_after['all_alarms_present']}")
    print(f"  After update - Present alarms: {', '.join(sorted(validation_after['present_alarms']))}")
    
    assert validation_after['all_alarms_present']
    assert len(validation_after['missing_alarms']) == 0
    
    print("  ✅ PASSED")


def test_coverage_report():
    """Test alarm coverage report functionality."""
    dashboard_json = json.dumps({
        "widgets": [
            {
                "type": "alarm",
                "x": 0,
                "y": 2,
                "width": 24,
                "height": 4,
                "properties": {
                    "title": "Alarms",
                    "alarms": [
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${IngestorFunctionErrorsAlarm}",
                        "arn:aws:cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:${ProcessorFunctionErrorsAlarm}"
                    ]
                }
            }
        ]
    })
    
    validator = AlarmValidator(dashboard_json)
    coverage_report = validator.get_alarm_coverage_report()
    
    print("\nCoverage Report Test:")
    print(f"  Ingestor complete: {coverage_report['ingestor_coverage']['complete']}")
    print(f"  Processor complete: {coverage_report['processor_coverage']['complete']}")
    print(f"  Infrastructure complete: {coverage_report['infrastructure_coverage']['complete']}")
    print(f"  Overall complete: {coverage_report['overall_complete']}")
    
    assert coverage_report['ingestor_coverage']['complete']
    assert not coverage_report['processor_coverage']['complete']  # Missing duration alarm
    assert not coverage_report['infrastructure_coverage']['complete']  # Missing DLQ alarm
    assert not coverage_report['overall_complete']
    
    print("  ✅ PASSED")


def main():
    """Run all tests."""
    print("Testing Alarm Validation Functionality")
    print("=" * 50)
    
    try:
        test_complete_alarm_dashboard()
        test_incomplete_alarm_dashboard()
        test_alarm_update()
        test_coverage_report()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()