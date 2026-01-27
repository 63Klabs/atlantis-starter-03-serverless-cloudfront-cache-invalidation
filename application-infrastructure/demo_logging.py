#!/usr/bin/env python3
"""
Demonstration script showing boto3 logging configuration.
This script shows how the common logger automatically suppresses verbose boto3 logs.
"""

import sys
import os

# Add layers to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'layers', 'common', 'python'))

from common.logger import setup_logger
import boto3

# Setup logger - this automatically configures boto3 logging
logger = setup_logger(__name__)

logger.info("Logger initialized - boto3/botocore logging is now set to WARNING level")

# Create a boto3 client - this would normally produce verbose DEBUG logs
# but now they're suppressed
try:
    s3_client = boto3.client('s3', region_name='us-east-1')
    logger.info("S3 client created successfully")
    
    # This operation would normally log extensive debug info from boto3
    # but now only WARNING and above will appear
    logger.info("Attempting to list buckets (boto3 debug logs suppressed)...")
    
except Exception as e:
    logger.error(f"Error creating S3 client: {e}")

logger.info("Demo complete - check that no boto3 DEBUG logs appeared above")
