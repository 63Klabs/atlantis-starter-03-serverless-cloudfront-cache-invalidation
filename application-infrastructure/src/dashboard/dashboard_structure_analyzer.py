"""Complete dashboard structure validation and analysis."""

import json
from typing import Dict, List, Any, Optional, Set, Tuple
from .layout_analyzer import DashboardLayoutAnalyzer, Widget


class DashboardStructureAnalyzer:
    """Analyzes complete dashboard structure for compliance with requirements."""
    
    def __init__(self, dashboard_json: str):
        """Initialize analyzer with dashboard JSON.
        
        Args:
            dashboard_json: JSON string containing dashboard configuration
        """
        self.dashboard_json = dashboard_json
        self.layout_analyzer = DashboardLayoutAnalyzer(dashboard_json)
        self.dashboard_data = json.loads(dashboard_json)
        self.widgets = self.layout_analyzer.widgets
    
    def validate_complete_structure(self) -> Dict[str, Any]:
        """Validate complete dashboard structure against all requirements.
        
        Returns:
            Dictionary containing comprehensive validation results
        """
        validation_results = {
            'overall_valid': True,
            'widget_positioning': self._validate_widget_positioning(),
            'section_headers': self._validate_section_headers(),
            'metrics_presence': self._validate_metrics_presence(),
            'alarms_configuration': self._validate_alarms_configuration(),
            'grid_compliance': self._validate_grid_compliance(),
            'issues': []
        }
        
        # Determine overall validity
        for category, results in validation_results.items():
            if isinstance(results, dict) and 'valid' in results and not results['valid']:
                validation_results['overall_valid'] = False
                if 'issues' in results:
                    validation_results['issues'].extend(results['issues'])
        
        return validation_results
    
    def _validate_widget_positioning(self) -> Dict[str, Any]:
        """Validate widget positioning requirements."""
        overlapping_pairs = self.layout_analyzer.find_overlapping_widgets()
        out_of_bounds = [w for w in self.widgets if not w.is_within_grid()]
        
        issues = []
        if overlapping_pairs:
            for w1, w2 in overlapping_pairs:
                issues.append(f"Widgets overlap: {w1} and {w2}")
        
        if out_of_bounds:
            for widget in out_of_bounds:
                issues.append(f"Widget extends beyond grid boundaries: {widget}")
        
        return {
            'valid': len(overlapping_pairs) == 0 and len(out_of_bounds) == 0,
            'overlapping_widgets': len(overlapping_pairs),
            'out_of_bounds_widgets': len(out_of_bounds),
            'issues': issues
        }
    
    def _validate_section_headers(self) -> Dict[str, Any]:
        """Validate section header presence and positioning."""
        text_widgets = [w for w in self.widgets if w.type == 'text']
        
        # Find section headers
        headers_found = {
            'title': False,
            'ingestor_header': False,
            'sqs_header': False,
            'processor_header': False
        }
        
        header_positions = {}
        issues = []
        
        for widget in text_widgets:
            markdown_content = widget.properties.get('markdown', '').lower()
            
            # Check for title (should be at y=0)
            if widget.y == 0 and widget.width == 24:
                headers_found['title'] = True
                header_positions['title'] = widget.y
            
            # Check for section headers
            if 'ingestor' in markdown_content and 'lambda' in markdown_content:
                headers_found['ingestor_header'] = True
                header_positions['ingestor_header'] = widget.y
            elif 'sqs' in markdown_content and 'queue' in markdown_content:
                headers_found['sqs_header'] = True
                header_positions['sqs_header'] = widget.y
            elif 'processor' in markdown_content and 'lambda' in markdown_content:
                headers_found['processor_header'] = True
                header_positions['processor_header'] = widget.y
        
        # Validate header requirements
        required_headers = ['title', 'ingestor_header', 'sqs_header', 'processor_header']
        missing_headers = [h for h in required_headers if not headers_found[h]]
        
        if missing_headers:
            issues.extend([f"Missing section header: {h}" for h in missing_headers])
        
        # Validate header positioning (headers should be above their sections)
        if headers_found['ingestor_header'] and headers_found['sqs_header']:
            if header_positions['ingestor_header'] >= header_positions['sqs_header']:
                issues.append("Ingestor header should be positioned before SQS header")
        
        if headers_found['sqs_header'] and headers_found['processor_header']:
            if header_positions['sqs_header'] >= header_positions['processor_header']:
                issues.append("SQS header should be positioned before Processor header")
        
        return {
            'valid': len(missing_headers) == 0 and len(issues) == len(missing_headers),
            'headers_found': headers_found,
            'header_positions': header_positions,
            'missing_headers': missing_headers,
            'issues': issues
        }
    
    def _validate_metrics_presence(self) -> Dict[str, Any]:
        """Validate presence of required metrics."""
        # Extract Ingestor metrics
        ingestor_metrics = self._extract_ingestor_metrics()
        required_ingestor_metrics = {
            'Invocations', 'Errors', 'Duration', 'ConcurrentExecutions'
        }
        missing_ingestor = required_ingestor_metrics - ingestor_metrics
        
        # Extract SQS metrics
        sqs_metrics = self._extract_sqs_metrics()
        required_event_queue_metrics = {
            'ApproximateNumberOfMessages',
            'ApproximateNumberOfMessagesVisible',
            'ApproximateAgeOfOldestMessage',
            'NumberOfMessagesSent',
            'NumberOfMessagesReceived'
        }
        required_dlq_metrics = {
            'ApproximateNumberOfMessages',
            'ApproximateNumberOfMessagesVisible'
        }
        
        missing_event_queue = required_event_queue_metrics - sqs_metrics.get('EventQueue', set())
        missing_dlq = required_dlq_metrics - sqs_metrics.get('EventQueueDLQ', set())
        
        # Extract Processor metrics (should be preserved)
        processor_metrics = self._extract_processor_metrics()
        
        issues = []
        if missing_ingestor:
            issues.extend([f"Missing Ingestor metric: {m}" for m in missing_ingestor])
        if missing_event_queue:
            issues.extend([f"Missing EventQueue metric: {m}" for m in missing_event_queue])
        if missing_dlq:
            issues.extend([f"Missing EventQueueDLQ metric: {m}" for m in missing_dlq])
        if not processor_metrics:
            issues.append("No Processor metrics found - existing widgets may have been lost")
        
        return {
            'valid': len(issues) == 0,
            'ingestor_metrics': ingestor_metrics,
            'sqs_metrics': sqs_metrics,
            'processor_metrics': processor_metrics,
            'missing_ingestor': missing_ingestor,
            'missing_event_queue': missing_event_queue,
            'missing_dlq': missing_dlq,
            'issues': issues
        }
    
    def _validate_alarms_configuration(self) -> Dict[str, Any]:
        """Validate alarms widget configuration."""
        alarms_widgets = [w for w in self.widgets if w.type == 'alarm']
        
        issues = []
        if not alarms_widgets:
            issues.append("No alarms widget found")
            return {
                'valid': False,
                'alarms_widget': None,
                'issues': issues
            }
        
        if len(alarms_widgets) > 1:
            issues.append(f"Multiple alarms widgets found: {len(alarms_widgets)}")
        
        alarms_widget = alarms_widgets[0]
        
        # Check positioning (should be at top after title)
        title_widgets = [w for w in self.widgets if w.type == 'text' and w.y == 0]
        if title_widgets:
            title_widget = title_widgets[0]
            expected_alarms_y = title_widget.y + title_widget.height
            if alarms_widget.y != expected_alarms_y:
                issues.append(f"Alarms widget not positioned at top. Expected y={expected_alarms_y}, got y={alarms_widget.y}")
        
        # Check width (should span full width)
        if alarms_widget.width != 24:
            issues.append(f"Alarms widget should span full width (24), got width={alarms_widget.width}")
        
        if alarms_widget.x != 0:
            issues.append(f"Alarms widget should start at x=0, got x={alarms_widget.x}")
        
        # Check alarm references
        alarms_list = alarms_widget.properties.get('alarms', [])
        if not alarms_list:
            issues.append("Alarms widget has no alarm references")
        
        # Check for required alarm types
        alarm_types_found = set()
        for alarm_arn in alarms_list:
            if 'IngestorFunction' in alarm_arn:
                alarm_types_found.add('ingestor')
            elif 'ProcessorFunction' in alarm_arn:
                alarm_types_found.add('processor')
            elif 'DLQ' in alarm_arn:
                alarm_types_found.add('dlq')
        
        required_alarm_types = {'ingestor', 'processor'}
        missing_alarm_types = required_alarm_types - alarm_types_found
        if missing_alarm_types:
            issues.extend([f"Missing alarm type: {t}" for t in missing_alarm_types])
        
        return {
            'valid': len(issues) == 0,
            'alarms_widget': alarms_widget,
            'alarm_count': len(alarms_list),
            'alarm_types_found': alarm_types_found,
            'missing_alarm_types': missing_alarm_types,
            'issues': issues
        }
    
    def _validate_grid_compliance(self) -> Dict[str, Any]:
        """Validate grid compliance and width consistency."""
        issues = []
        
        # Check width consistency
        standard_widths = {6, 12, 24}
        non_standard_widgets = [w for w in self.widgets if w.width not in standard_widths]
        
        if non_standard_widgets:
            for widget in non_standard_widgets:
                issues.append(f"Widget has non-standard width: {widget}")
        
        # Check grid bounds
        out_of_bounds = [w for w in self.widgets if not w.is_within_grid()]
        if out_of_bounds:
            for widget in out_of_bounds:
                issues.append(f"Widget exceeds grid bounds: {widget}")
        
        return {
            'valid': len(issues) == 0,
            'non_standard_widgets': len(non_standard_widgets),
            'out_of_bounds_widgets': len(out_of_bounds),
            'issues': issues
        }
    
    def _extract_ingestor_metrics(self) -> Set[str]:
        """Extract Ingestor Lambda metrics from dashboard."""
        ingestor_metrics = set()
        
        for widget in self.widgets:
            if widget.type == 'metric':
                properties = widget.properties
                metrics = properties.get('metrics', [])
                
                for metric in metrics:
                    if (len(metric) >= 4 and 
                        metric[0] == 'AWS/Lambda' and
                        isinstance(metric[3], str) and
                        '${IngestorFunction}' in metric[3]):
                        
                        ingestor_metrics.add(metric[1])
        
        return ingestor_metrics
    
    def _extract_sqs_metrics(self) -> Dict[str, Set[str]]:
        """Extract SQS metrics from dashboard."""
        sqs_metrics = {
            'EventQueue': set(),
            'EventQueueDLQ': set()
        }
        
        for widget in self.widgets:
            if widget.type == 'metric':
                properties = widget.properties
                metrics = properties.get('metrics', [])
                
                for metric in metrics:
                    if (len(metric) >= 4 and 
                        metric[0] == 'AWS/SQS' and
                        isinstance(metric[3], str)):
                        
                        metric_name = metric[1]
                        queue_ref = metric[3]
                        
                        if '${EventQueue' in queue_ref and '${EventQueueDLQ' not in queue_ref:
                            sqs_metrics['EventQueue'].add(metric_name)
                        elif '${EventQueueDLQ' in queue_ref:
                            sqs_metrics['EventQueueDLQ'].add(metric_name)
        
        return sqs_metrics
    
    def _extract_processor_metrics(self) -> Set[str]:
        """Extract Processor Lambda metrics from dashboard."""
        processor_metrics = set()
        
        for widget in self.widgets:
            if widget.type == 'metric':
                properties = widget.properties
                metrics = properties.get('metrics', [])
                
                for metric in metrics:
                    if (len(metric) >= 4 and 
                        metric[0] == 'AWS/Lambda' and
                        isinstance(metric[3], str) and
                        '${ProcessorFunction}' in metric[3]):
                        
                        processor_metrics.add(metric[1])
        
        return processor_metrics
    
    def get_section_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of metrics by section."""
        return {
            'ingestor_section': {
                'metrics': self._extract_ingestor_metrics(),
                'widget_count': len([w for w in self.widgets 
                                   if w.type == 'metric' and 
                                   any('${IngestorFunction}' in str(m) 
                                       for m in w.properties.get('metrics', []))])
            },
            'sqs_section': {
                'metrics': self._extract_sqs_metrics(),
                'widget_count': len([w for w in self.widgets 
                                   if w.type == 'metric' and 
                                   any('${EventQueue' in str(m) 
                                       for m in w.properties.get('metrics', []))])
            },
            'processor_section': {
                'metrics': self._extract_processor_metrics(),
                'widget_count': len([w for w in self.widgets 
                                   if w.type == 'metric' and 
                                   any('${ProcessorFunction}' in str(m) 
                                       for m in w.properties.get('metrics', []))])
            }
        }