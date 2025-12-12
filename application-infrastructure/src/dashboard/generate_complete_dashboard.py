#!/usr/bin/env python3
"""
Generate Complete Dashboard

This script generates the complete CloudWatch Dashboard with all Ingestor and SQS widgets
and updates the template-dashboard.yml file with the proper JSON structure.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any

from ingestor_metrics_manager import IngestorMetricsManager
from sqs_metrics_manager import SQSMetricsManager


def load_coordinate_mapping(mapping_path: str) -> Dict[str, Any]:
    """Load coordinate mapping from JSON file."""
    with open(mapping_path, 'r') as f:
        return json.load(f)


def load_template(template_path: str) -> Dict[str, Any]:
    """Load CloudFormation template."""
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def save_template(template: Dict[str, Any], template_path: str) -> None:
    """Save CloudFormation template with proper JSON formatting."""
    
    # Custom representer for multiline strings
    def represent_literal_str(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
    
    # Add the custom representer
    yaml.add_representer(str, represent_literal_str)
    
    with open(template_path, 'w') as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def parse_dashboard_body(dashboard_body: Any) -> Dict[str, Any]:
    """Parse the dashboard body JSON string."""
    if isinstance(dashboard_body, dict) and 'Fn::Sub' in dashboard_body:
        dashboard_json_str = dashboard_body['Fn::Sub']
    else:
        dashboard_json_str = dashboard_body
    
    return json.loads(dashboard_json_str)


def format_dashboard_body(dashboard_data: Dict[str, Any]) -> str:
    """Format dashboard data back to CloudFormation Fn::Sub format with readable JSON."""
    # Create properly formatted JSON with real line breaks
    dashboard_json_str = json.dumps(dashboard_data, indent=2)
    
    # Return as a multi-line string for YAML (using | for literal block scalar)
    return dashboard_json_str


def create_section_header(title: str, position: Dict[str, int]) -> Dict[str, Any]:
    """Create a section header widget."""
    return {
        "type": "text",
        "x": position["x"],
        "y": position["y"],
        "width": position["width"],
        "height": position["height"],
        "properties": {
            "markdown": f"## {title}"
        }
    }


def update_alarms_widget_position(widgets: List[Dict[str, Any]], coordinate_mapping: Dict[str, Any]) -> None:
    """Update the alarms widget to be positioned at the top."""
    alarms_position = coordinate_mapping["new_positions"]["alarms"]
    
    for widget in widgets:
        if widget.get("type") == "alarm":
            widget["x"] = alarms_position["x"]
            widget["y"] = alarms_position["y"]
            widget["width"] = alarms_position["width"]
            widget["height"] = alarms_position["height"]
            break


def update_existing_widget_positions(widgets: List[Dict[str, Any]], coordinate_mapping: Dict[str, Any]) -> None:
    """Update positions of existing widgets based on coordinate mapping."""
    moved_widgets = coordinate_mapping["widget_details"]["moved_widgets"]
    
    for i, widget in enumerate(widgets):
        widget_key = f"widget_{i}_{widget.get('type', 'unknown')}"
        if widget_key in moved_widgets:
            new_position = moved_widgets[widget_key]["new_position"]
            widget["x"] = new_position["x"]
            widget["y"] = new_position["y"]
            widget["width"] = new_position["width"]
            widget["height"] = new_position["height"]


def generate_complete_dashboard():
    """Generate the complete dashboard with all widgets from scratch."""
    # Define paths
    template_path = "../../template-dashboard.yml"
    coordinate_mapping_path = "../../coordinate_mapping.json"
    
    # Load coordinate mapping
    coordinate_mapping = load_coordinate_mapping(coordinate_mapping_path)
    
    # Create managers for widgets
    ingestor_manager = IngestorMetricsManager(coordinate_mapping)
    sqs_manager = SQSMetricsManager(coordinate_mapping)
    
    # Create all widgets from scratch based on coordinate mapping
    all_widgets = []
    
    # 1. Title widget
    title_pos = coordinate_mapping["new_positions"]["title"]
    title_widget = {
        "type": "text",
        "x": title_pos["x"],
        "y": title_pos["y"],
        "width": title_pos["width"],
        "height": title_pos["height"],
        "properties": {
            "markdown": "# ${Prefix}-${ProjectId}-${StageId}-Dashboard"
        }
    }
    all_widgets.append(title_widget)
    
    # 2. Alarms widget (repositioned to top)
    alarms_pos = coordinate_mapping["new_positions"]["alarms"]
    alarms_widget = {
        "type": "alarm",
        "x": alarms_pos["x"],
        "y": alarms_pos["y"],
        "width": alarms_pos["width"],
        "height": alarms_pos["height"],
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
    all_widgets.append(alarms_widget)
    
    # 3. Ingestor section header
    ingestor_header_pos = coordinate_mapping["new_widgets"]["ingestor_header"]
    ingestor_header = create_section_header("Lambda Functions - Ingestor", ingestor_header_pos)
    all_widgets.append(ingestor_header)
    
    # 4. Ingestor metrics widgets
    ingestor_widgets = ingestor_manager.create_all_ingestor_widgets()
    all_widgets.extend(ingestor_widgets)
    
    # 5. SQS section header
    sqs_header_pos = coordinate_mapping["new_widgets"]["sqs_header"]
    sqs_header = create_section_header("SQS Queues", sqs_header_pos)
    all_widgets.append(sqs_header)
    
    # 6. SQS metrics widgets
    sqs_widgets = sqs_manager.create_all_sqs_widgets()
    all_widgets.extend(sqs_widgets)
    
    # 7. Processor section header
    processor_header_pos = coordinate_mapping["new_widgets"]["processor_header"]
    processor_header = create_section_header("Lambda Functions - Processor", processor_header_pos)
    all_widgets.append(processor_header)
    
    # 8. Processor metrics widgets (recreated with new positions)
    processor_widgets = create_processor_widgets(coordinate_mapping)
    all_widgets.extend(processor_widgets)
    
    # 9. Log widgets (recreated with new positions)
    log_widgets = create_log_widgets(coordinate_mapping)
    all_widgets.extend(log_widgets)
    
    # Sort widgets by position
    all_widgets.sort(key=lambda w: (w.get('y', 0), w.get('x', 0)))
    
    # Create dashboard data
    dashboard_data = {"widgets": all_widgets}
    
    # Create template structure
    template = {
        "Dashboard": {
            "Type": "AWS::CloudWatch::Dashboard",
            "Condition": "CreateProdResources",
            "Properties": {
                "DashboardName": {
                    "Fn::Sub": "${Prefix}-${ProjectId}-${StageId}-Dashboard"
                },
                "DashboardBody": {
                    "Fn::Sub": format_dashboard_body(dashboard_data)
                }
            }
        }
    }
    
    # Save template
    save_template(template, template_path)
    
    print(f"Successfully generated complete dashboard with {len(all_widgets)} widgets")
    print(f"- Template updated: {template_path}")


def create_processor_widgets(coordinate_mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create Processor function widgets with updated positions."""
    widgets = []
    
    # Processor Invocations widget
    pos = coordinate_mapping["new_positions"]["widget_1_metric"]
    widgets.append({
        "type": "metric",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Invocations",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "id": "m2",
                        "color": "#1f77b4",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "AWS/Lambda",
                    "Errors",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "id": "m4",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Invocations",
            "period": 300,
            "stat": "Sum"
        }
    })
    
    # Processor Concurrent Executions widget
    pos = coordinate_mapping["new_positions"]["widget_3_metric"]
    widgets.append({
        "type": "metric",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "ConcurrentExecutions",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Concurrent Executions",
            "period": 300,
            "stat": "Average"
        }
    })
    
    # Processor Duration widget
    pos = coordinate_mapping["new_positions"]["widget_2_metric"]
    widgets.append({
        "type": "metric",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Duration",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "id": "m1",
                        "color": "#ff7f0e",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "...",
                    {
                        "id": "m2",
                        "stat": "Maximum",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "...",
                    {
                        "id": "m3",
                        "stat": "Minimum",
                        "color": "#2ca02c",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Avg Duration",
            "period": 300,
            "stat": "Average"
        }
    })
    
    # Processor Summary widget
    pos = coordinate_mapping["new_positions"]["widget_5_metric"]
    widgets.append({
        "type": "metric",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Invocations",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "id": "m2",
                        "color": "#1f77b4",
                        "region": "${AWS::Region}"
                    }
                ],
                [
                    "AWS/Lambda",
                    "Errors",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "id": "m4",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "singleValue",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Lambda Invocations",
            "period": 3600,
            "stat": "Sum",
            "setPeriodToTimeRange": True,
            "sparkline": False,
            "trend": False
        }
    })
    
    # Processor Errors widget
    pos = coordinate_mapping["new_positions"]["widget_4_metric"]
    widgets.append({
        "type": "metric",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "metrics": [
                [
                    "AWS/Lambda",
                    "Errors",
                    "FunctionName",
                    "${ProcessorFunction}",
                    {
                        "id": "m4",
                        "visible": True,
                        "stat": "Sum",
                        "color": "#d62728",
                        "region": "${AWS::Region}"
                    }
                ]
            ],
            "view": "timeSeries",
            "stacked": False,
            "region": "${AWS::Region}",
            "title": "Lambda Errors",
            "period": 300,
            "stat": "Average"
        }
    })
    
    return widgets


def create_log_widgets(coordinate_mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create log widgets with updated positions."""
    widgets = []
    
    # Error and Warning Log
    pos = coordinate_mapping["new_positions"]["widget_7_log"]
    widgets.append({
        "type": "log",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "query": "SOURCE '/aws/lambda/${ProcessorFunction}' | fields @timestamp as ts, @requestId, @message, @logStream as logStream\\n| sort ts desc\\n| limit 500\\n| PARSE @message \\\"[*] *\\\" as loggingType, loggingMessage\\n| FILTER (loggingType = \\\"ERROR\\\" or loggingType = \\\"WARN\\\" or @message like \\\"Task timed out\\\")\\n| DISPLAY ts, logStream, loggingType, loggingMessage",
            "region": "${AWS::Region}",
            "stacked": False,
            "title": "Error and Warning Log",
            "view": "table"
        }
    })
    
    # Memory Log
    pos = coordinate_mapping["new_positions"]["widget_8_log"]
    widgets.append({
        "type": "log",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "query": "SOURCE '/aws/lambda/${ProcessorFunction}' | filter @type = \\\"REPORT\\\"\\n| stats max(@memorySize / 1024 / 1024) as provisonedMemoryMB,\\n    min(@maxMemoryUsed / 1024 / 1024) as smallestMemoryRequestMB,\\n    avg(@maxMemoryUsed / 1024 / 1024) as avgMemoryUsedMB,\\n    max(@maxMemoryUsed / 1024 / 1024) as maxMemoryUsedMB,\\n    provisonedMemoryMB - maxMemoryUsedMB as overProvisionedMB",
            "region": "${AWS::Region}",
            "title": "Memory",
            "view": "table"
        }
    })
    
    # Durations Log
    pos = coordinate_mapping["new_positions"]["widget_9_log"]
    widgets.append({
        "type": "log",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "query": "SOURCE '/aws/lambda/${ProcessorFunction}' | filter @type=\\\"REPORT\\\"\\n| fields (@duration<50) as R50,\\n  (@duration>=50 and @duration<100) as R50_100,\\n  (@duration>=100 and @duration<250) as R100_250,\\n  (@duration>=250 and @duration<500) as R250_500,\\n  (@duration>=500 and @duration<750) as R500_750,\\n  (@duration>=750 and @duration<1000) as R750_1000,\\n  (@duration>=1000 and @duration<=2000) as R1000_2000,\\n  (@duration>=2000 and @duration<=3000) as R2000_3000,\\n  (@duration>=3000 and @duration<=4000) as R3000_4000,\\n  (@duration>=4000 and @duration<=5000) as R4000_5000,\\n  (@duration>=5000 and @duration<=6000) as R5000_6000,\\n  (@duration>=6000 and @duration<=7000) as R6000_7000,\\n  (@duration>=7000 and @duration<=8000) as R7000_8000,\\n  (@duration>=8000 and @duration<=9000) as R8000_9000,\\n  (@duration>=9000 and @duration<=10000) as R9000_10000,\\n  (@duration>10000) as R10000\\n| stats min(@duration) as minDur,\\n  avg(@duration) as avgDur,\\n  max(@duration) as maxDur,\\n  sum(R50) as D50ms,\\n  sum(R50_100) as D50_100ms,\\n  sum(R100_250) as D100_250ms,\\n  sum(R250_500) as D250_500ms,\\n  sum(R500_750) as D500_750ms,\\n  sum(R750_1000) as D750_1000ms,\\n  sum(R1000_2000) as D1_2s,\\n  sum(R2000_3000) as D2_3s,\\n  sum(R3000_4000) as D3_4s,\\n  sum(R4000_5000) as D4_5s,\\n  sum(R5000_6000) as D5_6s,\\n  sum(R6000_7000) as D6_7s,\\n  sum(R7000_8000) as D7_8s,\\n  sum(R8000_9000) as D8_9s,\\n  sum(R9000_10000) as D9_10s,\\n  sum(R10000) as D10s",
            "region": "${AWS::Region}",
            "title": "Durations",
            "view": "table"
        }
    })
    
    # Response Log
    pos = coordinate_mapping["new_positions"]["widget_10_log"]
    widgets.append({
        "type": "log",
        "x": pos["x"],
        "y": pos["y"],
        "width": pos["width"],
        "height": pos["height"],
        "properties": {
            "query": "SOURCE '/aws/lambda/${ProcessorFunction}' | fields @timestamp as ts, @message\\n| sort ts desc\\n| limit 500\\n| PARSE @message \\\"[*] * | * | * | * | * | * | * | * | * | * | * | * | *\\\" as loggingType, statusCode, bytes, contentType, execTime, clientIP, userAgent, origin, referrer, resource, queryKeys, pathLog, queryLog, key\\n| FILTER loggingType = \\\"RESPONSE\\\"\\n| DISPLAY ts, statusCode, bytes, execTime, clientIP, userAgent, origin, referrer, resource, queryKeys, pathLog, queryLog, key",
            "region": "${AWS::Region}",
            "stacked": False,
            "view": "table",
            "title": "Response Log"
        }
    })
    
    # Cold Starts text
    widgets.append({
        "height": 2,
        "width": 24,
        "y": 59,
        "x": 0,
        "type": "text",
        "properties": {
            "markdown": "## Cold Starts\\n\\n\\nA cold start is when a Lambda function is loaded for execution. After execution, the Lambda function will reside in memory for up to 45 minutes waiting for additional executions.\\n\\n\\nCold starts will occur for each new concurrent execution and after a Lambda function has been dormant for a period of time."
        }
    })
    
    # Cold Starts log
    pos = coordinate_mapping["new_positions"]["widget_12_log"]
    widgets.append({
        "height": pos["height"],
        "width": pos["width"],
        "y": pos["y"],
        "x": pos["x"],
        "type": "log",
        "properties": {
            "query": "SOURCE '/aws/lambda/${ProcessorFunction}' | filter @type=\\\"REPORT\\\"\\n| fields @initDuration\\n| stats min(@duration) as minDur,\\n  avg(@initDuration) as avgDur,\\n  max(@initDuration) as maxDur,\\n  count(@initDuration) as num",
            "region": "${AWS::Region}",
            "stacked": False,
            "title": "Cold Starts",
            "view": "table"
        }
    })
    
    return widgets


if __name__ == "__main__":
    try:
        generate_complete_dashboard()
    except Exception as e:
        print(f"Error generating dashboard: {e}")
        import traceback
        traceback.print_exc()