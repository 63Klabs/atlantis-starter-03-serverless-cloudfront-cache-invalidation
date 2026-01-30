#!/usr/bin/env python3
"""Fix handler tests to use new _from_dict functions."""

import re

# Read the test file
with open('tests/unit/test_processor_handler.py', 'r') as f:
    content = f.read()

# Find all test functions that mock validate_bucket_tags_from_dict but not get_bucket_consolidation_config_from_dict
# These need to add the mock for get_bucket_consolidation_config_from_dict

# Pattern to find test functions
test_pattern = r'(@patch[^\n]+\n)+\s+def (test_\w+)\('

# Find all tests
tests = list(re.finditer(test_pattern, content))

print(f"Found {len(tests)} test functions")

# For each test, check if it has validate_bucket_tags_from_dict but not get_bucket_consolidation_config_from_dict
for match in tests:
    test_start = match.start()
    test_name = match.group(2)
    
    # Get the decorators for this test
    decorators_start = test_start
    decorators_end = match.end()
    decorators = content[decorators_start:decorators_end]
    
    has_validate_from_dict = 'validate_bucket_tags_from_dict' in decorators
    has_config_from_dict = 'get_bucket_consolidation_config_from_dict' in decorators
    has_get_tags = 'get_bucket_tags' in decorators
    
    if has_validate_from_dict and has_get_tags and not has_config_from_dict:
        print(f"Test {test_name} needs get_bucket_consolidation_config_from_dict mock")

print("\nDone analyzing tests")
