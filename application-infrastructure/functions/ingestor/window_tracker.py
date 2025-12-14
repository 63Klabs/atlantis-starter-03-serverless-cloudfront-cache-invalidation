"""Window tracking functions - imports from common layer."""

import sys
import os

# Add layer paths to Python path
for path in ['/opt/python', '/opt/python/lib/python3.14/site-packages']:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

from common.window_tracker import (
    check_active_window,
    create_window,
    close_window
)