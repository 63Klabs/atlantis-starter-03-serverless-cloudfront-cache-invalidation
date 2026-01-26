"""Property-based tests for path utility functions."""

import sys
import os

from hypothesis import given, settings, strategies as st
from common.path_utils import (
    calculate_path_depth,
    matches_pattern,
    derive_pattern_from_path,
    extract_stage_from_path
)


# Custom strategies for generating test data

@st.composite
def path_with_known_depth(draw):
    """Generate a path with a known depth.
    
    Returns a tuple of (path, expected_depth)
    """
    # Generate depth between 0 and 10
    depth = draw(st.integers(min_value=0, max_value=10))
    
    if depth == 0:
        return ('/', 0)
    
    # Generate path segments
    segments = []
    for _ in range(depth):
        segment = draw(st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=('Ll', 'Lu', 'Nd'),
                whitelist_characters='-_'
            )
        ))
        segments.append(segment)
    
    # Create path with various leading/trailing slash combinations
    slash_style = draw(st.sampled_from([
        'both',      # /segment1/segment2/
        'leading',   # /segment1/segment2
        'trailing',  # segment1/segment2/
        'none'       # segment1/segment2
    ]))
    
    path = '/'.join(segments)
    
    if slash_style == 'both':
        path = '/' + path + '/'
    elif slash_style == 'leading':
        path = '/' + path
    elif slash_style == 'trailing':
        path = path + '/'
    # else: no slashes
    
    return (path, depth)


# Property Tests

@settings(max_examples=20)
@given(path_with_known_depth())
def test_property_3_path_depth_calculation(path_and_depth):
    """Property 3: Path Depth Calculation.
    
    For any path string, the depth calculation function should return a count 
    equal to the number of non-empty segments when split by /.
    
    **Feature: origin-path-pattern, Property 3: Path Depth Calculation**
    **Validates: Requirements 3.6, 9.2**
    """
    path, expected_depth = path_and_depth
    
    # Calculate depth using the function
    actual_depth = calculate_path_depth(path)
    
    # Verify the depth matches expected
    assert actual_depth == expected_depth, \
        f"Path '{path}' should have depth {expected_depth}, got {actual_depth}"
    
    # Also verify by manually counting segments
    manual_count = len([s for s in path.strip('/').split('/') if s])
    assert actual_depth == manual_count, \
        f"Calculated depth {actual_depth} doesn't match manual count {manual_count} for path '{path}'"
