#!/usr/bin/env python3
"""
Update Dashboard with Ingestor Metrics

This script adds Ingestor Lambda function metrics widgets to the CloudWatch Dashboard
template based on the coordinate mapping.
"""

import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from dashboard.dashboard_updater import DashboardUpdater


def main():
    """Main function to update dashboard with Ingestor metrics."""
    # Define paths
    template_path = "application-infrastructure/template-dashboard.yml"
    coordinate_mapping_path = "application-infrastructure/coordinate_mapping.json"
    
    try:
        # Create dashboard updater
        updater = DashboardUpdater(template_path, coordinate_mapping_path)
        
        # Add Ingestor widgets
        print("Adding Ingestor metrics widgets to dashboard...")
        updater.add_ingestor_widgets()
        
        print("Successfully added Ingestor metrics widgets to dashboard template.")
        
    except Exception as e:
        print(f"Error updating dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()