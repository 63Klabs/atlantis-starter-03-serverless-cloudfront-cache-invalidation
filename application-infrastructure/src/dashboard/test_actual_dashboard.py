#!/usr/bin/env python3
"""
Test Actual Dashboard Against Property 1

This script tests the actual dashboard template against Property 1 requirements
to ensure all Ingestor metrics are present and correctly configured.
"""

import json
import yaml
from pathlib import Path


def load_dashboard_template():
    """Load the dashboard template."""
    template_path = Path("application-infrastructure/template-dashboard.yml")
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def parse_dashboard_body(dashboard_body):
    """Parse the dashboard body from CloudFormation Fn::Sub format."""
    if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
        json_str = dashboard_body['Fn::Sub']
    else:
        json_str = dashboard_body
    
    return json.loads(json_str)


def extract_ingestor_metrics_from_dashboard(dashboard_json):
    """Extract Ingestor metrics from dashboard JSON."""
    if isinstance(dashboard_json, str):
        dashboard_data = json.loads(dashboard_json)
    else:
        dashboard_data = dashboard_json
    
    widgets = dashboard_data.get('widgets', [])
    
    ingestor_metrics = set()
    
    for widget in widgets:
        if widget.get('type') == 'metric':
            properties = widget.get('properties', {})
            metrics = properties.get('metrics', [])
            
            for metric in metrics:
                if (len(metric) >= 4 and 
                    metric[0] == 'AWS/Lambda' and
                    isinstance(metric[3], str) and
                    '${IngestorFunction}' in metric[3]):
                    
                    metric_name = metric[1]
                    ingestor_metrics.add(metric_name)
    
    return ingestor_metrics


def test_property_1_on_actual_dashboard():
    """Test Property 1: Ingestor metrics presence on actual dashboard."""
    print("Testing Property 1: Ingestor metrics presence on actual dashboard...")
    
    # Load actual dashboard
    template = load_dashboard_template()
    dashboard_body = template['Dashboard']['Properties']['DashboardBody']
    dashboard_data = parse_dashboard_body(dashboard_body)
    
    # Required metrics based on requirements
    required_metrics = {
        'Invocations',  # Requirements 1.1, 1.4, 1.5
        'Errors',       # Requirements 1.4, 1.5
        'Duration',     # Requirement 1.2
        'ConcurrentExecutions'  # Requirement 1.3
    }
    
    # Extract actual metrics
    actual_metrics = extract_ingestor_metrics_from_dashboard(dashboard_data)
    
    print(f"Required metrics: {sorted(required_metrics)}")
    print(f"Found metrics: {sorted(actual_metrics)}")
    
    # Check completeness
    missing_metrics = required_metrics - actual_metrics
    extra_metrics = actual_metrics - required_metrics
    
    print(f"Missing metrics: {sorted(missing_metrics) if missing_metrics else 'None'}")
    print(f"Extra metrics: {sorted(extra_metrics) if extra_metrics else 'None'}")
    
    # Validate Property 1
    is_complete = len(missing_metrics) == 0
    
    if is_complete:
        print("✓ Property 1 PASSED: All required Ingestor metrics are present")
        
        # Additional validation: Check function references
        print("\nValidating function references...")
        widgets = dashboard_data.get('widgets', [])
        
        ingestor_widgets = []
        for widget in widgets:
            if widget.get('type') == 'metric':
                properties = widget.get('properties', {})
                metrics = properties.get('metrics', [])
                
                has_ingestor_metric = False
                for metric in metrics:
                    if (len(metric) >= 4 and 
                        isinstance(metric[3], str) and
                        '${IngestorFunction}' in metric[3]):
                        has_ingestor_metric = True
                        break
                
                if has_ingestor_metric:
                    ingestor_widgets.append(widget)
        
        print(f"Found {len(ingestor_widgets)} Ingestor metric widgets")
        
        # Validate each widget
        all_valid = True
        for i, widget in enumerate(ingestor_widgets):
            title = widget.get('properties', {}).get('title', f'Widget {i}')
            print(f"  - {title}")
            
            properties = widget.get('properties', {})
            metrics = properties.get('metrics', [])
            
            for metric in metrics:
                if (len(metric) >= 4 and 
                    isinstance(metric[3], str) and
                    '${IngestorFunction}' in metric[3]):
                    
                    namespace = metric[0]
                    metric_name = metric[1]
                    function_ref = metric[3]
                    
                    if namespace != 'AWS/Lambda':
                        print(f"    ✗ Invalid namespace: {namespace}")
                        all_valid = False
                    
                    if metric_name not in required_metrics:
                        print(f"    ✗ Invalid metric name: {metric_name}")
                        all_valid = False
                    
                    if '${IngestorFunction}' not in function_ref:
                        print(f"    ✗ Invalid function reference: {function_ref}")
                        all_valid = False
        
        if all_valid:
            print("✓ All function references are valid")
            return True
        else:
            print("✗ Some function references are invalid")
            return False
    
    else:
        print(f"✗ Property 1 FAILED: Missing required metrics: {sorted(missing_metrics)}")
        return False


if __name__ == "__main__":
    success = test_property_1_on_actual_dashboard()
    if success:
        print("\n🎉 All Property 1 tests passed on actual dashboard!")
    else:
        print("\n❌ Property 1 tests failed on actual dashboard!")
        exit(1)