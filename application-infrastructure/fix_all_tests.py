#!/usr/bin/env python3
"""Fix all handler tests to work with new _from_dict functions."""

import re

# Read the test file
with open('tests/unit/test_processor_handler.py', 'r') as f:
    content = f.read()

# Fix 1: Add get_bucket_consolidation_config_from_dict mock to tests that have consolidate_paths but not the config mock
# Find all test functions that have consolidate_paths
pattern = r"(@patch[^\n]+\n)+(\s+def (test_\w+)\([^)]+\):)"

matches = list(re.finditer(pattern, content))

for match in matches:
    decorators = match.group(1)
    func_def = match.group(2)
    test_name = match.group(3)
    
    has_consolidate = 'consolidate_paths' in decorators
    has_config_from_dict = 'get_bucket_consolidation_config_from_dict' in decorators
    has_get_tags = 'get_bucket_tags' in decorators
    has_validate_from_dict = 'validate_bucket_tags_from_dict' in decorators
    
    # If test has consolidate_paths and get_bucket_tags but not get_bucket_consolidation_config_from_dict, add it
    if has_consolidate and has_get_tags and has_validate_from_dict and not has_config_from_dict:
        print(f"Test {test_name} needs get_bucket_consolidation_config_from_dict mock")
        
        # Find the position to insert the new patch (after get_bucket_tags)
        get_tags_line = None
        for line in decorators.split('\n'):
            if 'get_bucket_tags' in line and 'get_bucket_tags_from_dict' not in line:
                get_tags_line = line
                break
        
        if get_tags_line:
            # Insert the new patch after get_bucket_tags
            new_patch = "    @patch('functions.processor.handler.get_bucket_consolidation_config_from_dict')"
            old_section = decorators + func_def
            new_decorators = decorators.replace(
                get_tags_line,
                get_tags_line + '\n' + new_patch
            )
            new_section = new_decorators + func_def
            
            # Also need to add mock_get_config parameter to function signature
            # Find the function parameters
            params_match = re.search(r'def ' + test_name + r'\(\s*self,\s*([^)]+)\):', func_def)
            if params_match:
                params = params_match.group(1)
                # Add mock_get_config after mock_get_tags
                if 'mock_get_tags' in params:
                    new_params = params.replace('mock_get_tags,', 'mock_get_config, mock_get_tags,')
                    new_func_def = func_def.replace(params, new_params)
                    new_section = new_decorators + new_func_def
                    
                    content = content.replace(old_section, new_section)
                    print(f"  Added mock to {test_name}")

# Write the updated content
with open('tests/unit/test_processor_handler.py', 'w') as f:
    f.write(content)

print("\nDone fixing tests!")
