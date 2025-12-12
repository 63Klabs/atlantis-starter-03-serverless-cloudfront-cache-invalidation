"""
Ingestor Metrics Manager

This module handles the creation and management of Ingestor Lambda function metrics widgets
for the CloudWatch Dashboard. It creates widgets for invocations, errors, duration,
concurrent executions, and summary metrics.
"""

import json
from typing import Dict, List, Any


class IngestorMetricsManager:
    """Manages Ingestor Lambda function metrics widgets for CloudWatch Dashboard."""
    
    def __init__(self, coordinate_mapping: Dict[str, Any]):
        """
        Initialize the Ingestor Metrics Manager.
        
        Args:
            coordinate_mapping: Dictionary containing widget positioning information
        """
        self.coordinate_mapping = coordinate_mapping
        
    def create_invocations_and_errors_widget(self) -> Dict[str, Any]:
        """
        Create a time series widget for Ingestor invocations and errors metrics.
        
        Returns:
            Dict containing the widget configuration for invocations and errors
        """
        position = self.coordinate_mapping["new_widgets"]["ingestor_invocations"]
        
        widget = {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/Lambda",
                        "Invocations",
                        "FunctionName",
                        "${IngestorFunction}",
                        {
                            "id": "m1",
                            "color": "#1f77b4",
                            "region": "${AWS::Region}"
                        }
                    ],
                    [
                        "AWS/Lambda",
                        "Errors",
                        "FunctionName",
                        "${IngestorFunction}",
                        {
                            "id": "m2",
                            "color": "#d62728",
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "Ingestor Invocations & Errors",
                "period": 300,
                "stat": "Sum"
            }
        }
        
        return widget
    
    def create_duration_metrics_widget(self) -> Dict[str, Any]:
        """
        Create a time series widget showing average, minimum, and maximum duration.
        
        Returns:
            Dict containing the widget configuration for duration metrics
        """
        position = self.coordinate_mapping["new_widgets"]["ingestor_duration"]
        
        widget = {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/Lambda",
                        "Duration",
                        "FunctionName",
                        "${IngestorFunction}",
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
                "title": "Ingestor Duration",
                "period": 300,
                "stat": "Average"
            }
        }
        
        return widget
    
    def create_concurrent_executions_widget(self) -> Dict[str, Any]:
        """
        Create a time series widget for concurrent executions metric.
        
        Returns:
            Dict containing the widget configuration for concurrent executions
        """
        position = self.coordinate_mapping["new_widgets"]["ingestor_concurrent"]
        
        widget = {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/Lambda",
                        "ConcurrentExecutions",
                        "FunctionName",
                        "${IngestorFunction}",
                        {
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "Ingestor Concurrent Executions",
                "period": 300,
                "stat": "Average"
            }
        }
        
        return widget
    
    def create_invocation_summary_widget(self) -> Dict[str, Any]:
        """
        Create a single-value widget for Ingestor invocation summaries.
        
        Returns:
            Dict containing the widget configuration for invocation summary
        """
        position = self.coordinate_mapping["new_widgets"]["ingestor_summary"]
        
        widget = {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/Lambda",
                        "Invocations",
                        "FunctionName",
                        "${IngestorFunction}",
                        {
                            "id": "m1",
                            "color": "#1f77b4",
                            "region": "${AWS::Region}"
                        }
                    ],
                    [
                        "AWS/Lambda",
                        "Errors",
                        "FunctionName",
                        "${IngestorFunction}",
                        {
                            "id": "m2",
                            "color": "#d62728",
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "singleValue",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "Ingestor Invocations Summary",
                "period": 3600,
                "stat": "Sum",
                "setPeriodToTimeRange": True,
                "sparkline": False,
                "trend": False
            }
        }
        
        return widget
    
    def create_errors_widget(self) -> Dict[str, Any]:
        """
        Create a dedicated time series widget for Ingestor errors.
        
        Returns:
            Dict containing the widget configuration for errors
        """
        position = self.coordinate_mapping["new_widgets"]["ingestor_errors"]
        
        widget = {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/Lambda",
                        "Errors",
                        "FunctionName",
                        "${IngestorFunction}",
                        {
                            "id": "m1",
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
                "title": "Ingestor Errors",
                "period": 300,
                "stat": "Sum"
            }
        }
        
        return widget
    
    def create_all_ingestor_widgets(self) -> List[Dict[str, Any]]:
        """
        Create all Ingestor metrics widgets.
        
        Returns:
            List of all Ingestor widget configurations
        """
        widgets = [
            self.create_invocations_and_errors_widget(),
            self.create_duration_metrics_widget(),
            self.create_concurrent_executions_widget(),
            self.create_invocation_summary_widget(),
            self.create_errors_widget()
        ]
        
        return widgets