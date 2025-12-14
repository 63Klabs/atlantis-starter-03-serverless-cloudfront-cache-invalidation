"""
Test configuration for Lambda function separation tests.
Adds the common layer to Python path for testing.
"""
import sys
import os

# Add the layer's python directory to the path for testing
layer_python_path = os.path.join(os.path.dirname(__file__), '..', 'layers', 'common', 'python')
if layer_python_path not in sys.path:
    sys.path.insert(0, layer_python_path)

# Add the functions directory to the path for testing
functions_path = os.path.join(os.path.dirname(__file__), '..', 'functions')
if functions_path not in sys.path:
    sys.path.insert(0, functions_path)