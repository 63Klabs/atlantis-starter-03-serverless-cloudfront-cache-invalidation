"""
SQS Metrics Manager

This module handles creating SQS queue metrics widgets for the CloudWatch Dashboard.
"""

from typing import Dict, List, Any


class SQSMetricsManager:
    """Manages SQS metrics widgets for the dashboard."""
    
    def __init__(self, coordinate_mapping: Dict[str, Any]):
        """
        Initialize the SQS Metrics Manager.
        
        Args:
            coordinate_mapping: Dictionary containing widget positioning information
        """
        self.coordinate_mapping = coordinate_mapping
    
    def create_event_queue_message_count_widget(self) -> Dict[str, Any]:
        """
        Create Event Queue message count widget for ApproximateNumberOfMessages 
        and ApproximateNumberOfMessagesVisible.
        
        Returns:
            Widget configuration dictionary
        """
        position = self.coordinate_mapping["new_widgets"]["sqs_message_count"]
        
        return {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/SQS",
                        "ApproximateNumberOfMessages",
                        "QueueName",
                        "${EventQueue.QueueName}",
                        {
                            "id": "m1",
                            "color": "#1f77b4",
                            "region": "${AWS::Region}"
                        }
                    ],
                    [
                        "AWS/SQS",
                        "ApproximateNumberOfMessagesVisible",
                        "QueueName",
                        "${EventQueue.QueueName}",
                        {
                            "id": "m2",
                            "color": "#ff7f0e",
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "Event Queue Message Count",
                "period": 300,
                "stat": "Average"
            }
        }
    
    def create_event_queue_age_widget(self) -> Dict[str, Any]:
        """
        Create Event Queue age metrics widget for ApproximateAgeOfOldestMessage.
        
        Returns:
            Widget configuration dictionary
        """
        position = self.coordinate_mapping["new_widgets"]["sqs_age"]
        
        return {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/SQS",
                        "ApproximateAgeOfOldestMessage",
                        "QueueName",
                        "${EventQueue.QueueName}",
                        {
                            "id": "m1",
                            "color": "#d62728",
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "Event Queue Age of Oldest Message",
                "period": 300,
                "stat": "Maximum",
                "yAxis": {
                    "left": {
                        "min": 0
                    }
                }
            }
        }
    
    def create_dlq_monitoring_widget(self) -> Dict[str, Any]:
        """
        Create Dead Letter Queue monitoring widget for DLQ message count metrics.
        
        Returns:
            Widget configuration dictionary
        """
        position = self.coordinate_mapping["new_widgets"]["sqs_dlq"]
        
        return {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/SQS",
                        "ApproximateNumberOfMessages",
                        "QueueName",
                        "${EventQueueDLQ.QueueName}",
                        {
                            "id": "m1",
                            "color": "#d62728",
                            "region": "${AWS::Region}"
                        }
                    ],
                    [
                        "AWS/SQS",
                        "ApproximateNumberOfMessagesVisible",
                        "QueueName",
                        "${EventQueueDLQ.QueueName}",
                        {
                            "id": "m2",
                            "color": "#ff7f0e",
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "Dead Letter Queue Messages",
                "period": 300,
                "stat": "Average",
                "annotations": {
                    "horizontal": [
                        {
                            "label": "Alert Threshold",
                            "value": 1
                        }
                    ]
                }
            }
        }
    
    def create_sqs_send_receive_rates_widget(self) -> Dict[str, Any]:
        """
        Create SQS send and receive rate widgets for NumberOfMessagesSent 
        and NumberOfMessagesReceived.
        
        Returns:
            Widget configuration dictionary
        """
        position = self.coordinate_mapping["new_widgets"]["sqs_rates"]
        
        return {
            "type": "metric",
            "x": position["x"],
            "y": position["y"],
            "width": position["width"],
            "height": position["height"],
            "properties": {
                "metrics": [
                    [
                        "AWS/SQS",
                        "NumberOfMessagesSent",
                        "QueueName",
                        "${EventQueue.QueueName}",
                        {
                            "id": "m1",
                            "color": "#2ca02c",
                            "region": "${AWS::Region}"
                        }
                    ],
                    [
                        "AWS/SQS",
                        "NumberOfMessagesReceived",
                        "QueueName",
                        "${EventQueue.QueueName}",
                        {
                            "id": "m2",
                            "color": "#1f77b4",
                            "region": "${AWS::Region}"
                        }
                    ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "${AWS::Region}",
                "title": "SQS Message Send/Receive Rates",
                "period": 300,
                "stat": "Sum"
            }
        }
    
    def create_all_sqs_widgets(self) -> List[Dict[str, Any]]:
        """
        Create all SQS metrics widgets.
        
        Returns:
            List of widget configuration dictionaries
        """
        return [
            self.create_event_queue_message_count_widget(),
            self.create_event_queue_age_widget(),
            self.create_dlq_monitoring_widget(),
            self.create_sqs_send_receive_rates_widget()
        ]