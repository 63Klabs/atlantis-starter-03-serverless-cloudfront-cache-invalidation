"""
Test configuration for simplified import structure.
Adds the layer path once for all tests to mirror Lambda runtime behavior.
"""
import sys
from pathlib import Path

print(f"🔧 conftest.py loading from: {__file__}")

# Add layer path once for all tests - mirrors Lambda's /opt/python
layer_path = Path(__file__).parent.parent / "layers" / "common" / "python"
if str(layer_path) not in sys.path:
    sys.path.insert(0, str(layer_path))
    print(f"✅ Added layer path to sys.path: {layer_path}")
else:
    print(f"ℹ️  Layer path already in sys.path: {layer_path}")

# Add functions directory to path for function-specific imports
functions_path = Path(__file__).parent.parent / "functions"
if str(functions_path) not in sys.path:
    sys.path.insert(0, str(functions_path))
    print(f"✅ Added functions path to sys.path: {functions_path}")
else:
    print(f"ℹ️  Functions path already in sys.path: {functions_path}")

print(f"🔍 Current sys.path after conftest.py setup:")
for i, path in enumerate(sys.path[:10]):  # Show first 10 paths
    print(f"  {i}: {path}")

# Note: Individual function directories are not added to avoid module name conflicts.
# Each function's internal imports should work when the function is imported via its full path.