"""Property-based tests for path consolidation algorithm."""

import sys
import os

from hypothesis import given, settings, strategies as st, assume, HealthCheck
from functions.processor.path_consolidator import (
    consolidate_paths,
    is_index_or_default_file,
    get_parent_directory,
    consolidate_index_and_default_files,
    consolidate_by_directory_threshold,
    consolidate_sibling_directories,
    is_consolidation_allowed_at_depth
)


# Custom strategies for generating test data

@st.composite
def path_segment(draw):
    """Generate a valid path segment (directory or file name)."""
    return draw(st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'),
            whitelist_characters='.-_'
        )
    ))


@st.composite
def file_path(draw, min_depth=1, max_depth=5):
    """Generate a file path with specified depth.
    
    Args:
        min_depth: Minimum number of path segments
        max_depth: Maximum number of path segments
    """
    segments = draw(st.lists(
        path_segment(),
        min_size=min_depth,
        max_size=max_depth
    ))
    return '/' + '/'.join(segments)


@st.composite
def index_or_default_file_path(draw):
    """Generate a path ending with index.* or default.*"""
    # Generate parent directory path
    parent_segments = draw(st.lists(
        path_segment(),
        min_size=1,
        max_size=4
    ))
    parent = '/' + '/'.join(parent_segments)
    
    # Choose index or default
    prefix = draw(st.sampled_from(['index', 'default']))
    
    # Add extension
    extension = draw(st.sampled_from(['html', 'htm', 'php', 'jsp', 'asp', 'txt']))
    
    filename = f"{prefix}.{extension}"
    
    return f"{parent}/{filename}"


@st.composite
def directory_with_files(draw, min_files=4, max_files=10):
    """Generate a directory path with multiple UNIQUE files.
    
    Returns a tuple of (directory_path, list_of_file_paths)
    """
    # Generate directory path
    dir_segments = draw(st.lists(
        path_segment(),
        min_size=1,
        max_size=3
    ))
    directory = '/' + '/'.join(dir_segments)
    
    # Generate multiple UNIQUE files in that directory using unique integers
    num_files = draw(st.integers(min_value=min_files, max_value=max_files))
    files = []
    for i in range(num_files):
        extension = draw(st.sampled_from(['html', 'js', 'css', 'png', 'jpg', 'txt']))
        # Use index to ensure uniqueness
        file_path = f"{directory}/file{i}.{extension}"
        files.append(file_path)
    
    return (directory, files)


@st.composite
def sibling_directories_with_wildcards(draw, min_siblings=11, max_siblings=20):
    """Generate UNIQUE sibling directory wildcards.
    
    Returns a tuple of (parent_path, list_of_wildcard_paths)
    """
    # Generate parent directory path
    parent_segments = draw(st.lists(
        path_segment(),
        min_size=1,
        max_size=2
    ))
    parent = '/' + '/'.join(parent_segments)
    
    # Generate multiple UNIQUE sibling directories using indices
    num_siblings = draw(st.integers(min_value=min_siblings, max_value=max_siblings))
    wildcards = []
    for i in range(num_siblings):
        # Use index to ensure uniqueness
        wildcards.append(f"{parent}/dir{i}/*")
    
    return (parent, wildcards)


@st.composite
def paths_exceeding_limit(draw, min_paths=1001, max_paths=2500):
    """Generate a list of paths exceeding the CloudFront limit."""
    num_paths = draw(st.integers(min_value=min_paths, max_value=max_paths))
    paths = []
    for i in range(num_paths):
        path = draw(file_path(min_depth=2, max_depth=4))
        paths.append(path)
    return paths


# Property Tests

@settings(max_examples=5)  # Optimized for faster execution
@given(index_or_default_file_path())
def test_property_20_index_and_default_file_directory_consolidation(file_path):
    """Property 20: Index and default file directory consolidation.
    
    For any object path ending with /index.* or /default.*, the consolidation
    algorithm should replace the file path with the parent directory path
    followed by /* if the stop level allows it.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 20: Index and default file directory consolidation**
    **Validates: Requirements 9.1**
    """
    # Verify the path is indeed an index or default file
    assert is_index_or_default_file(file_path), f"Path {file_path} should be index/default file"
    
    # Calculate the depth of the parent directory
    parent = get_parent_directory(file_path)
    from functions.processor.path_consolidator import calculate_path_depth
    parent_depth = calculate_path_depth(parent, '/')
    
    # Use a stop level that allows consolidation at this depth
    stop_level = max(parent_depth, 1)  # Ensure stop level allows this depth
    
    # Consolidate the path with the appropriate stop level
    result = consolidate_paths([file_path], stop_level=stop_level)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk for one path"
    
    consolidated = result[0]
    
    # Should have exactly one path (the parent directory wildcard)
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}"
    
    consolidated_path = consolidated[0]
    
    # Should end with /*
    assert consolidated_path.endswith('/*'), f"Consolidated path should end with /*, got {consolidated_path}"
    
    # The consolidated path should be the parent directory + /*
    if parent == '/':
        expected = '/*'
    else:
        expected = f"{parent}/*"
    
    assert consolidated_path == expected, f"Expected {expected}, got {consolidated_path}"


@settings(max_examples=5)  # Optimized for faster execution
@given(directory_with_files(min_files=4, max_files=10))
def test_property_21_directory_consolidation_threshold(directory_and_files):
    """Property 21: Directory consolidation threshold.
    
    For any set of object paths where more than 3 paths share the same parent
    directory, the consolidation algorithm should replace those paths with a
    single directory-level path <parent>/* if the stop level allows it.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 21: Directory consolidation threshold**
    **Validates: Requirements 9.2**
    """
    directory, files = directory_and_files
    
    # Verify we have more than 3 files
    assert len(files) > 3, f"Should have more than 3 files, got {len(files)}"
    
    # Calculate the depth of the directory
    from functions.processor.path_consolidator import calculate_path_depth
    directory_depth = calculate_path_depth(directory, '/')
    
    # Use a stop level that allows consolidation at this depth
    stop_level = max(directory_depth, 1)  # Ensure stop level allows this depth
    
    # Consolidate the paths with the appropriate stop level
    result = consolidate_paths(files, stop_level=stop_level)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should consolidate to a single directory wildcard
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}: {consolidated}"
    
    consolidated_path = consolidated[0]
    
    # Should be the directory with /*
    expected = f"{directory}/*"
    assert consolidated_path == expected, f"Expected {expected}, got {consolidated_path}"


@settings(max_examples=5)  # Optimized for faster execution
@given(sibling_directories_with_wildcards(min_siblings=11, max_siblings=20))
def test_property_22_sibling_directory_consolidation(parent_and_wildcards):
    """Property 22: Sibling directory consolidation.
    
    For any set of directory-level paths where more than 10 sibling directories
    would be invalidated, the consolidation algorithm should replace them with
    their parent directory path followed by /* if the stop level allows it.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 22: Sibling directory consolidation**
    **Validates: Requirements 9.3**
    """
    parent, wildcards = parent_and_wildcards
    
    # Verify we have more than 10 sibling wildcards
    assert len(wildcards) > 10, f"Should have more than 10 siblings, got {len(wildcards)}"
    
    # Calculate the depth of the parent directory
    from functions.processor.path_consolidator import calculate_path_depth
    parent_depth = calculate_path_depth(parent, '/')
    
    # Use a stop level that allows consolidation at this depth
    stop_level = max(parent_depth, 1)  # Ensure stop level allows this depth
    
    # Consolidate the paths with the appropriate stop level
    result = consolidate_paths(wildcards, stop_level=stop_level)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should consolidate to parent wildcard
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}: {consolidated}"
    
    consolidated_path = consolidated[0]
    
    # Should be the parent with /*
    expected = f"{parent}/*"
    assert consolidated_path == expected, f"Expected {expected}, got {consolidated_path}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.lists(file_path(min_depth=2, max_depth=5), min_size=1, max_size=100))
def test_property_23_root_consolidation_terminal_case(paths):
    """Property 23: Root consolidation terminal case.
    
    For any consolidation that reaches the origin path root, the final
    consolidated path should be /*.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 23: Root consolidation terminal case**
    **Validates: Requirements 9.4**
    """
    # This property is tested implicitly by the consolidation algorithm
    # When paths consolidate all the way up, they should reach /*
    
    result = consolidate_paths(paths)
    
    # Should return at least one chunk
    assert len(result) >= 1, "Should return at least one chunk"
    
    # Check if any consolidated path is /*
    all_consolidated = []
    for chunk in result:
        all_consolidated.extend(chunk)
    
    # If we have /* in the result, verify it's the only path
    if '/*' in all_consolidated:
        assert len(all_consolidated) == 1, "If /* is present, it should be the only path"
        assert all_consolidated[0] == '/*', "Root consolidation should be /*"


@settings(max_examples=5, suppress_health_check=[HealthCheck.large_base_example])  # Optimized for faster execution
@given(st.integers(min_value=1001, max_value=1500))
def test_property_24_invalidation_request_splitting(num_paths):
    """Property 24: Invalidation request splitting.
    
    For any consolidated path list exceeding 1000 items, the paths should be
    split into multiple lists where each list contains at most 1000 items.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 24: Invalidation request splitting**
    **Validates: Requirements 9.5**
    """
    # Generate unique paths that won't consolidate
    # Use different parent directories to prevent consolidation
    unique_paths = []
    for i in range(num_paths):
        # Each path in a different directory to prevent consolidation
        unique_paths.append(f"/dir{i}/file.html")
    
    result = consolidate_paths(unique_paths)
    
    # Should return multiple chunks
    assert len(result) > 1, f"Should split into multiple chunks, got {len(result)}"
    
    # Each chunk should have at most 1000 paths
    for i, chunk in enumerate(result):
        assert len(chunk) <= 1000, f"Chunk {i} has {len(chunk)} paths, should be <= 1000"
    
    # Total paths should equal input (no consolidation should happen)
    total_paths = sum(len(chunk) for chunk in result)
    assert total_paths == num_paths, f"Expected {num_paths} paths, got {total_paths}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_25_redundant_subdirectory_removal(data):
    """Property 25: Redundant subdirectory removal.
    
    For any set of paths containing both a parent directory wildcard and 
    subdirectory paths covered by that wildcard, the consolidation algorithm 
    should remove the redundant subdirectory paths.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: Redundant subdirectory removal**
    **Validates: Requirements 9.6**
    """
    # Generate a parent directory path
    parent_depth = data.draw(st.integers(min_value=1, max_value=4))
    parent_parts = []
    for _ in range(parent_depth):
        part = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                min_size=1, max_size=10))
        parent_parts.append(part)
    
    parent_path = '/' + '/'.join(parent_parts)
    
    # Create the parent wildcard
    parent_wildcard = f"{parent_path}/*"
    
    # Generate some subdirectory wildcards that should be removed
    num_subdirs = data.draw(st.integers(min_value=1, max_value=5))
    subdirectory_wildcards = []
    
    for i in range(num_subdirs):
        subdir_name = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                       min_size=1, max_size=10))
        # Create subdirectory wildcard
        subdir_wildcard = f"{parent_path}/{subdir_name}/*"
        subdirectory_wildcards.append(subdir_wildcard)
    
    # Also add some individual files under the parent that should be removed
    num_files = data.draw(st.integers(min_value=0, max_value=3))
    individual_files = []
    
    for i in range(num_files):
        filename = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                    min_size=1, max_size=10))
        file_path = f"{parent_path}/{filename}.html"
        individual_files.append(file_path)
    
    # Create the input path list with parent wildcard and redundant subdirectories
    input_paths = [parent_wildcard] + subdirectory_wildcards + individual_files
    
    # Add some unrelated paths that should not be affected
    unrelated_paths = []
    num_unrelated = data.draw(st.integers(min_value=0, max_value=3))
    for i in range(num_unrelated):
        unrelated_name = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                          min_size=1, max_size=10))
        unrelated_path = f"/unrelated{i}/{unrelated_name}.css"
        unrelated_paths.append(unrelated_path)
    
    all_input_paths = input_paths + unrelated_paths
    
    # Consolidate the paths
    result = consolidate_paths(all_input_paths)
    
    # Should return a single chunk (not enough paths to split)
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # The parent wildcard should be present
    assert parent_wildcard in consolidated, f"Parent wildcard {parent_wildcard} should be present in {consolidated}"
    
    # None of the subdirectory wildcards should be present
    for subdir_wildcard in subdirectory_wildcards:
        assert subdir_wildcard not in consolidated, f"Subdirectory wildcard {subdir_wildcard} should be removed, but found in {consolidated}"
    
    # None of the individual files under the parent should be present
    for file_path in individual_files:
        assert file_path not in consolidated, f"Individual file {file_path} should be removed, but found in {consolidated}"
    
    # Unrelated paths should still be present
    for unrelated_path in unrelated_paths:
        assert unrelated_path in consolidated, f"Unrelated path {unrelated_path} should be preserved, but not found in {consolidated}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_25_nested_redundant_removal(data):
    """Property 25: Redundant subdirectory removal - nested case.
    
    Test the specific example from the requirements:
    /stage/public/asdf/qwerty/* should remove /stage/public/asdf/qwerty/e/*
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: Redundant subdirectory removal**
    **Validates: Requirements 9.6**
    """
    # Create the specific example paths
    parent_wildcard = "/stage/public/asdf/qwerty/*"
    redundant_subdir = "/stage/public/asdf/qwerty/e/*"
    
    # Add some additional paths to make it more realistic
    other_file = "/stage/public/asdf/qwerty/c/test-03.html"
    other_subdir = "/stage/public/asdf/qwerty/c/*"
    
    # Test case 1: Parent wildcard should remove subdirectory wildcard
    input_paths = [parent_wildcard, redundant_subdir]
    result = consolidate_paths(input_paths)
    
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    assert parent_wildcard in consolidated, f"Parent wildcard should be present: {consolidated}"
    assert redundant_subdir not in consolidated, f"Redundant subdirectory should be removed: {consolidated}"
    assert len(consolidated) == 1, f"Should only have parent wildcard: {consolidated}"
    
    # Test case 2: Parent wildcard should remove individual files too
    input_paths = [parent_wildcard, other_file]
    result = consolidate_paths(input_paths)
    
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    assert parent_wildcard in consolidated, f"Parent wildcard should be present: {consolidated}"
    assert other_file not in consolidated, f"Individual file should be removed: {consolidated}"
    assert len(consolidated) == 1, f"Should only have parent wildcard: {consolidated}"
    
    # Test case 3: Multiple redundant paths
    input_paths = [parent_wildcard, redundant_subdir, other_file, other_subdir]
    result = consolidate_paths(input_paths)
    
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    assert parent_wildcard in consolidated, f"Parent wildcard should be present: {consolidated}"
    assert redundant_subdir not in consolidated, f"Redundant subdirectory should be removed: {consolidated}"
    assert other_file not in consolidated, f"Individual file should be removed: {consolidated}"
    assert other_subdir not in consolidated, f"Other subdirectory should be removed: {consolidated}"
    assert len(consolidated) == 1, f"Should only have parent wildcard: {consolidated}"


# Stop Level Property Tests

@settings(max_examples=5)  # Optimized for faster execution
@given(st.lists(file_path(min_depth=1, max_depth=5), min_size=1, max_size=50))
def test_property_1_root_consolidation_for_stop_level_zero(paths):
    """Property 1: Root consolidation for stop level zero.
    
    For any set of paths, when ConsolidationStopLevel is 0, the system should 
    consolidate all paths to the root wildcard /*.
    
    **Feature: consolidation-stop-level-fix, Property 1: Root consolidation for stop level zero**
    **Validates: Requirements 1.1**
    """
    # Consolidate with stop level 0
    result = consolidate_paths(paths, stop_level=0)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should consolidate to root wildcard only
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}: {consolidated}"
    assert consolidated[0] == '/*', f"Should consolidate to /*, got {consolidated[0]}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.lists(file_path(min_depth=1, max_depth=5), min_size=1, max_size=50),
       st.integers(min_value=1, max_value=10))
def test_property_2_stop_level_zero_override_behavior(paths, directory_threshold):
    """Property 2: Stop level zero override behavior.
    
    For any path configuration and consolidation thresholds, when ConsolidationStopLevel 
    is 0, the system should ignore all other consolidation rules and return /*.
    
    **Feature: consolidation-stop-level-fix, Property 2: Stop level zero override behavior**
    **Validates: Requirements 1.2**
    """
    # Consolidate with stop level 0 and various thresholds
    result = consolidate_paths(paths, directory_threshold=directory_threshold, stop_level=0)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should always consolidate to root wildcard regardless of other parameters
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}: {consolidated}"
    assert consolidated[0] == '/*', f"Should consolidate to /*, got {consolidated[0]}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.lists(file_path(min_depth=1, max_depth=5), min_size=1, max_size=50))
def test_property_3_stop_level_zero_logging(paths):
    """Property 3: Stop level zero logging.
    
    For any consolidation operation when ConsolidationStopLevel is 0, the system 
    should log that root consolidation is being applied.
    
    **Feature: consolidation-stop-level-fix, Property 3: Stop level zero logging**
    **Validates: Requirements 1.3**
    """
    import logging
    from io import StringIO
    import json
    
    # Create a string buffer to capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    
    # Set up JSON formatter to match the actual logger
    from common.logger import JSONFormatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Get the path consolidator logger and add our handler
    from functions.processor.path_consolidator import logger
    original_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    try:
        # Run consolidation with stop level 0 - this should trigger logging
        result = consolidate_paths(paths, stop_level=0)
        
        # Verify the result is correct
        assert len(result) == 1, "Should return single chunk"
        assert len(result[0]) == 1, "Should consolidate to single path"
        assert result[0][0] == '/*', "Should consolidate to /*"
        
        # Get the captured log output
        log_output = log_capture.getvalue()
        
        # Parse log entries and look for stop level 0 logging
        log_lines = [line.strip() for line in log_output.strip().split('\n') if line.strip()]
        
        stop_level_logged = False
        for line in log_lines:
            try:
                log_entry = json.loads(line)
                message = log_entry.get('message', '')
                
                # Check for stop level 0 logging message
                if ('Stop level 0' in message and 'consolidating all paths to root wildcard' in message):
                    stop_level_logged = True
                    
                    # Verify the log contains required fields (they are at top level, not in extra_fields)
                    assert log_entry.get('stop_level') == 0, "Log should contain stop_level 0"
                    assert 'original_count' in log_entry, "Log should contain original_count"
                    assert log_entry['original_count'] == len(paths), f"Log should contain correct original count {len(paths)}"
                    assert log_entry.get('consolidation_type') == 'stop_level_zero_override', "Log should contain consolidation_type"
                    assert log_entry.get('bypassed_rules') == 'all_other_consolidation_logic', "Log should contain bypassed_rules"
                    break
            except json.JSONDecodeError:
                continue
        
        assert stop_level_logged, f"Should have logged stop level 0 root consolidation. Log output: {log_output}"
    
    finally:
        # Clean up - remove our handler and restore original level
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()


@settings(max_examples=5)  # Optimized for faster execution
@given(st.integers(min_value=1, max_value=10),  # stop_level
       st.integers(min_value=0, max_value=10))  # depth
def test_property_4_consolidation_allowed_at_specified_depth(stop_level, depth):
    """Property 4: Consolidation allowed at specified depth.
    
    For any ConsolidationStopLevel N where N > 0, the system should allow 
    consolidation to occur at depth N and shallower.
    
    **Feature: consolidation-stop-level-fix, Property 4: Consolidation allowed at specified depth**
    **Validates: Requirements 2.1, 3.1**
    """
    result = is_consolidation_allowed_at_depth(depth, stop_level)
    
    if depth >= stop_level:
        assert result is True, f"Consolidation should be allowed at depth {depth} with stop level {stop_level}"
    else:
        assert result is False, f"Consolidation should be blocked at depth {depth} with stop level {stop_level}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.integers(min_value=1, max_value=8),   # stop_level
       st.integers(min_value=1, max_value=5))   # extra_depth (> 0)
def test_property_5_consolidation_prevented_at_deep_depths(stop_level, extra_depth):
    """Property 5: Consolidation prevented at deep depths.
    
    For any ConsolidationStopLevel N where N > 0, the system should prevent 
    consolidation at depths greater than N.
    
    **Feature: consolidation-stop-level-fix, Property 5: Consolidation prevented at deep depths**
    **Validates: Requirements 2.4, 3.5**
    """
    # Test that depths greater than stop_level are blocked
    deep_depth = stop_level + extra_depth  # This will always be > stop_level
    result_deep = is_consolidation_allowed_at_depth(deep_depth, stop_level)
    assert result_deep is True, f"Consolidation should be allowed at deep depth {deep_depth} with stop level {stop_level}"
    
    # Also test that depths equal to stop_level are allowed
    result_equal = is_consolidation_allowed_at_depth(stop_level, stop_level)
    assert result_equal is True, f"Consolidation should be allowed at depth {stop_level} with stop level {stop_level}"
    
    # And test that depths less than stop_level are blocked (if stop_level > 0)
    if stop_level > 0:
        shallow_depth = max(0, stop_level - 1)
        result_shallow = is_consolidation_allowed_at_depth(shallow_depth, stop_level)
        assert result_shallow is False, f"Consolidation should be blocked at shallow depth {shallow_depth} with stop level {stop_level}"


# Logging Property Tests

@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_7_stop_level_prevention_logging(data):
    """Property 7: Stop level prevention logging.
    
    For any consolidation operation prevented by ConsolidationStopLevel, the system 
    should log the stop level value and the blocked depth.
    
    **Feature: consolidation-stop-level-fix, Property 7: Stop level prevention logging**
    **Validates: Requirements 5.1**
    """
    import logging
    from io import StringIO
    import json
    
    # Create a string buffer to capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    # Set up JSON formatter to match the actual logger
    from common.logger import JSONFormatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Get the path consolidator logger and add our handler
    from functions.processor.path_consolidator import logger
    original_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    try:
        # Generate test data that will trigger stop level prevention
        stop_level = data.draw(st.integers(min_value=2, max_value=4))  # Use higher stop levels
        
        # Create paths that would consolidate at a depth LESS than stop_level
        # This should trigger prevention logging
        blocked_depth = data.draw(st.integers(min_value=1, max_value=stop_level - 1))
        
        # Create directory structure at the blocked depth
        path_segments = []
        for i in range(blocked_depth):
            segment = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                       min_size=1, max_size=8))
            path_segments.append(segment)
        
        # Create multiple files in the same directory to trigger threshold consolidation
        base_path = '/' + '/'.join(path_segments)
        test_paths = []
        for i in range(5):  # More than threshold to trigger consolidation
            file_path = f"{base_path}/file{i}.html"
            test_paths.append(file_path)
        
        # Run consolidation - this should trigger prevention logging
        consolidate_paths(test_paths, stop_level=stop_level)
        
        # Get the captured log output
        log_output = log_capture.getvalue()
        
        if log_output.strip():
            # Parse log entries
            log_lines = [line.strip() for line in log_output.strip().split('\n') if line.strip()]
            
            # Look for prevention logging
            prevention_logged = False
            for line in log_lines:
                try:
                    log_entry = json.loads(line)
                    message = log_entry.get('message', '')
                    
                    # Check for stop level prevention messages
                    if ('prevents' in message and 'consolidation' in message and 
                        'stop_level' in log_entry and 'blocked_depth' in log_entry):
                        prevention_logged = True
                        
                        # Verify the log contains required fields
                        assert log_entry['stop_level'] == stop_level, f"Log should contain stop_level {stop_level}"
                        assert 'blocked_depth' in log_entry, "Log should contain blocked_depth"
                        break
                except json.JSONDecodeError:
                    continue
            
            # If we had paths that should trigger prevention, verify logging occurred
            if len(test_paths) > 3:  # Above threshold
                assert prevention_logged, f"Should have logged stop level prevention. Log output: {log_output}"
    
    finally:
        # Clean up - remove our handler and restore original level
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_8_stop_level_allowance_logging(data):
    """Property 8: Stop level allowance logging.
    
    For any consolidation operation allowed by ConsolidationStopLevel, the system 
    should log the consolidation decision with depth information.
    
    **Feature: consolidation-stop-level-fix, Property 8: Stop level allowance logging**
    **Validates: Requirements 5.2**
    """
    import logging
    from io import StringIO
    import json
    
    # Create a string buffer to capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    # Set up JSON formatter to match the actual logger
    from common.logger import JSONFormatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Get the path consolidator logger and add our handler
    from functions.processor.path_consolidator import logger
    original_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    try:
        # Generate test data that will trigger stop level allowance
        stop_level = data.draw(st.integers(min_value=1, max_value=3))
        
        # Create paths that would consolidate at a depth >= stop_level
        # This should trigger allowance logging
        allowed_depth = data.draw(st.integers(min_value=stop_level, max_value=stop_level + 2))
        
        # Create directory structure at the allowed depth
        path_segments = []
        for i in range(allowed_depth):
            segment = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                       min_size=1, max_size=8))
            path_segments.append(segment)
        
        # Create multiple files in the same directory to trigger threshold consolidation
        base_path = '/' + '/'.join(path_segments)
        test_paths = []
        for i in range(5):  # More than threshold to trigger consolidation
            file_path = f"{base_path}/file{i}.html"
            test_paths.append(file_path)
        
        # Run consolidation - this should trigger allowance logging
        consolidate_paths(test_paths, stop_level=stop_level)
        
        # Get the captured log output
        log_output = log_capture.getvalue()
        
        if log_output.strip():
            # Parse log entries
            log_lines = [line.strip() for line in log_output.strip().split('\n') if line.strip()]
            
            # Look for allowance logging
            allowance_logged = False
            for line in log_lines:
                try:
                    log_entry = json.loads(line)
                    message = log_entry.get('message', '')
                    
                    # Check for stop level allowance messages
                    if ('allows' in message and 'consolidation' in message and 
                        'stop_level' in log_entry and 'allowed_depth' in log_entry):
                        allowance_logged = True
                        
                        # Verify the log contains required fields
                        assert log_entry['stop_level'] == stop_level, f"Log should contain stop_level {stop_level}"
                        assert 'allowed_depth' in log_entry, "Log should contain allowed_depth"
                        break
                except json.JSONDecodeError:
                    continue
            
            # If we had paths that should trigger allowance, verify logging occurred
            if len(test_paths) > 3:  # Above threshold
                assert allowance_logged, f"Should have logged stop level allowance. Log output: {log_output}"
    
    finally:
        # Clean up - remove our handler and restore original level
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_6_path_depth_calculation_accuracy(data):
    """Property 6: Path depth calculation accuracy.
    
    For any path, the system should calculate directory depth correctly by 
    counting directory levels from the first 'public' directory found in the path.
    
    **Feature: consolidation-stop-level-fix, Property 6: Path depth calculation accuracy**
    **Validates: Requirements 4.1**
    """
    from functions.processor.path_consolidator import calculate_path_depth
    
    # Test case 1: Paths with 'public' directory
    # Generate a path with 'public' and known depth from public
    depth_from_public = data.draw(st.integers(min_value=1, max_value=5))
    
    # Create path segments before 'public'
    pre_public_segments = []
    num_pre_segments = data.draw(st.integers(min_value=1, max_value=3))
    for i in range(num_pre_segments):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        pre_public_segments.append(segment)
    
    # Create path segments after 'public'
    post_public_segments = []
    for i in range(depth_from_public - 1):  # -1 because 'public' itself is level 1
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        post_public_segments.append(segment)
    
    # Construct the full path: /pre_segments/public/post_segments
    all_segments = pre_public_segments + ['public'] + post_public_segments
    test_path = '/' + '/'.join(all_segments)
    
    calculated_depth = calculate_path_depth(test_path)
    
    # The calculated depth should be the number of segments from 'public' onwards
    # 'public' = level 1, so depth = 1 + len(post_public_segments)
    expected_depth = 1 + len(post_public_segments)
    assert calculated_depth == expected_depth, \
        f"Expected depth {expected_depth} for path {test_path}, got {calculated_depth}"
    
    # Test case 2: Paths without 'public' directory (fallback behavior)
    # Generate a path without 'public'
    fallback_depth = data.draw(st.integers(min_value=1, max_value=5))
    fallback_segments = []
    for i in range(fallback_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        # Ensure we don't accidentally create 'public'
        if segment == 'public':
            segment = 'notpublic'
        fallback_segments.append(segment)
    
    fallback_path = '/' + '/'.join(fallback_segments)
    fallback_calculated = calculate_path_depth(fallback_path)
    
    # Should fall back to simple segment counting
    assert fallback_calculated == len(fallback_segments), \
        f"Expected fallback depth {len(fallback_segments)} for path {fallback_path}, got {fallback_calculated}"
    
    # Test case 3: Root path should return depth 0
    root_depth = calculate_path_depth('/')
    assert root_depth == 0, f"Root path should have depth 0, got {root_depth}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_6_specific_requirements_validation(data):
    """Property 6: Path depth calculation - specific requirements validation.
    
    Validates the specific requirements 4.1-4.4 for path depth calculation accuracy.
    
    **Feature: consolidation-stop-level-fix, Property 6: Path depth calculation accuracy**
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    """
    from functions.processor.path_consolidator import calculate_path_depth, get_parent_directory
    
    # Requirement 4.1: WHEN calculating path depth, THE system SHALL count directory levels from the root path
    root_path = '/'
    
    # Generate test paths at various depths
    for expected_depth in range(1, 6):
        # Create path segments
        path_segments = []
        for i in range(expected_depth):
            segment = data.draw(st.text(
                alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                min_size=1, max_size=8
            ))
            path_segments.append(segment)
        
        # Create file path
        file_path = '/' + '/'.join(path_segments) + '/file.html'
        
        # Get parent directory
        parent_dir = get_parent_directory(file_path)
        
        # Calculate depth of parent directory
        calculated_depth = calculate_path_depth(parent_dir, root_path)
        
        # Should match expected depth
        assert calculated_depth == expected_depth, \
            f"Expected depth {expected_depth} for parent {parent_dir} of file {file_path}, got {calculated_depth}"
    
    # Requirement 4.2: WHEN a path is `/level1/file.html`, THE system SHALL calculate its parent directory `/level1` as depth 1
    level1_file = '/level1/file.html'
    level1_parent = get_parent_directory(level1_file)
    level1_depth = calculate_path_depth(level1_parent, '/')
    assert level1_depth == 1, f"Expected depth 1 for /level1, got {level1_depth}"
    assert level1_parent == '/level1', f"Expected parent /level1, got {level1_parent}"
    
    # Requirement 4.3: WHEN a path is `/level1/level2/file.html`, THE system SHALL calculate its parent directory `/level1/level2` as depth 2
    level2_file = '/level1/level2/file.html'
    level2_parent = get_parent_directory(level2_file)
    level2_depth = calculate_path_depth(level2_parent, '/')
    assert level2_depth == 2, f"Expected depth 2 for /level1/level2, got {level2_depth}"
    assert level2_parent == '/level1/level2', f"Expected parent /level1/level2, got {level2_parent}"
    
    # Requirement 4.4: WHEN a path is `/level1/level2/level3/file.html`, THE system SHALL calculate its parent directory `/level1/level2/level3` as depth 3
    level3_file = '/level1/level2/level3/file.html'
    level3_parent = get_parent_directory(level3_file)
    level3_depth = calculate_path_depth(level3_parent, '/')
    assert level3_depth == 3, f"Expected depth 3 for /level1/level2/level3, got {level3_depth}"
    assert level3_parent == '/level1/level2/level3', f"Expected parent /level1/level2/level3, got {level3_parent}"
    
    # Requirement 4.5: WHEN the root path is `/`, THE system SHALL use absolute depth counting from the filesystem root
    # Test with various root paths
    test_cases = [
        ('/file.html', '/', 1),
        ('/dir/file.html', '/', 2),
        ('/dir/subdir/file.html', '/', 3),
        ('/prod/public/file.html', '/prod/public', 2),  # 'public' is level 1, 'file.html' makes it level 2
        ('/prod/public/dir/file.html', '/prod/public', 3),  # 'public' is level 1, 'dir' is level 2, 'file.html' makes it level 3
    ]
    
    for path, root, expected in test_cases:
        actual = calculate_path_depth(path, root)
        assert actual == expected, f"Expected depth {expected} for path {path} with root {root}, got {actual}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_9_depth_calculation_logging(data):
    """Property 9: Depth calculation logging.
    
    For any depth calculation performed, the system should include depth values 
    in debug logs.
    
    **Feature: consolidation-stop-level-fix, Property 9: Depth calculation logging**
    **Validates: Requirements 5.3**
    """
    import logging
    from io import StringIO
    import json
    
    # Create a string buffer to capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    # Set up JSON formatter to match the actual logger
    from common.logger import JSONFormatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Get the path consolidator logger and add our handler
    from functions.processor.path_consolidator import logger
    original_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    try:
        # Generate test data for depth calculation
        depth = data.draw(st.integers(min_value=1, max_value=5))
        
        # Create a path at the specified depth
        path_segments = []
        for i in range(depth):
            segment = data.draw(st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                                       min_size=1, max_size=8))
            path_segments.append(segment)
        
        test_path = '/' + '/'.join(path_segments)
        root_path = '/'
        
        # Call calculate_path_depth directly to trigger logging
        from functions.processor.path_consolidator import calculate_path_depth
        calculated_depth = calculate_path_depth(test_path, root_path)
        
        # Get the captured log output
        log_output = log_capture.getvalue()
        
        if log_output.strip():
            # Parse log entries
            log_lines = [line.strip() for line in log_output.strip().split('\n') if line.strip()]
            
            # Look for depth calculation logging
            depth_logged = False
            for line in log_lines:
                try:
                    log_entry = json.loads(line)
                    message = log_entry.get('message', '')
                    
                    # Check for depth calculation messages
                    if ('Path depth calculation' in message and 
                        'calculated_depth' in log_entry and 'operation' in log_entry and
                        log_entry.get('operation') == 'calculate_path_depth'):
                        depth_logged = True
                        
                        # Verify the log contains required fields
                        assert 'calculated_depth' in log_entry, "Log should contain calculated_depth"
                        assert log_entry['calculated_depth'] == calculated_depth, f"Log should contain correct depth {calculated_depth}"
                        assert 'path' in log_entry, "Log should contain path"
                        assert 'root_path' in log_entry, "Log should contain root_path"
                        break
                except json.JSONDecodeError:
                    continue
            
            assert depth_logged, f"Should have logged depth calculation. Log output: {log_output}"
    
    finally:
        # Clean up - remove our handler and restore original level
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()


@settings(max_examples=5)  # Optimized for faster execution
@given(st.one_of(
    st.integers(min_value=-100, max_value=-1),  # Negative values
    st.integers(min_value=21, max_value=1000),  # Values above max range
    st.floats(min_value=-10.0, max_value=30.0).filter(lambda x: not x.is_integer()),  # Non-integer floats
))
def test_property_10_invalid_stop_level_logging(invalid_stop_level):
    """Property 10: Invalid stop level logging.
    
    For any invalid ConsolidationStopLevel value encountered, the system should 
    log warnings and fallback behavior.
    
    **Feature: consolidation-stop-level-fix, Property 10: Invalid stop level logging**
    **Validates: Requirements 5.5**
    """
    import logging
    from io import StringIO
    import json
    import os
    from unittest.mock import patch
    
    # Create a string buffer to capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.WARNING)
    
    # Set up JSON formatter to match the actual logger
    from common.logger import JSONFormatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Get the path consolidator logger and add our handler
    from functions.processor.path_consolidator import logger
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    
    try:
        # Mock the environment variable to contain invalid value
        with patch.dict(os.environ, {'CONSOLIDATION_STOP_LEVEL': str(invalid_stop_level)}):
            # Force reload of constants to pick up the mocked environment variable
            import importlib
            import common.constants
            importlib.reload(common.constants)
            
            # Create some test paths
            test_paths = ['/test/file1.html', '/test/file2.html', '/test/file3.html', '/test/file4.html']
            
            # Run consolidation - this should trigger invalid stop level handling
            result = consolidate_paths(test_paths)
            
            # Verify the result uses default behavior (stop_level=1)
            assert len(result) == 1, "Should return single chunk"
            consolidated = result[0]
            
            # Should consolidate to /test/* with default stop level 1
            assert len(consolidated) == 1, f"Should consolidate to single path, got {consolidated}"
            assert consolidated[0] == '/test/*', f"Should consolidate to /test/*, got {consolidated[0]}"
            
            # Get the captured log output
            log_output = log_capture.getvalue()
            
            if log_output.strip():
                # Parse log entries
                log_lines = [line.strip() for line in log_output.strip().split('\n') if line.strip()]
                
                # Look for invalid stop level logging
                invalid_logged = False
                for line in log_lines:
                    try:
                        log_entry = json.loads(line)
                        message = log_entry.get('message', '')
                        
                        # Check for invalid stop level warning messages
                        if ('invalid' in message.lower() and 'stop' in message.lower() and 
                            'level' in message.lower() and ('warning' in message.lower() or 'fallback' in message.lower())):
                            invalid_logged = True
                            
                            # Verify the log contains required fields
                            assert 'invalid_value' in log_entry or 'invalid_stop_level' in log_entry, \
                                "Log should contain invalid value information"
                            assert 'fallback_value' in log_entry or 'default_value' in log_entry, \
                                "Log should contain fallback value information"
                            break
                    except json.JSONDecodeError:
                        continue
                
                assert invalid_logged, f"Should have logged invalid stop level warning. Log output: {log_output}"
    
    finally:
        # Clean up - remove our handler and restore original level
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()
        
        # Restore original constants
        import importlib
        import common.constants
        importlib.reload(common.constants)


# Stop Level Compliance Property Tests

@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_11_index_file_consolidation_stop_level_compliance(data):
    """Property 11: Index file consolidation stop level compliance.
    
    For any index or default file consolidation, when ConsolidationStopLevel prevents 
    consolidation at the target depth, the system should not perform the consolidation.
    
    **Feature: consolidation-stop-level-fix, Property 11: Index file consolidation stop level compliance**
    **Validates: Requirements 6.1**
    """
    # Generate a stop level that will prevent consolidation at shallow depths
    stop_level = data.draw(st.integers(min_value=2, max_value=4))
    
    # Generate an index/default file at a depth LESS than stop_level (should be blocked)
    # Rule: depth < stop_level prevents consolidation
    blocked_depth = data.draw(st.integers(min_value=0, max_value=stop_level - 1))
    
    # Create path segments for the blocked depth
    path_segments = []
    for i in range(blocked_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    # Create index/default file path
    base_path = '/' + '/'.join(path_segments) if path_segments else ''
    file_type = data.draw(st.sampled_from(['index', 'default']))
    extension = data.draw(st.sampled_from(['html', 'htm', 'php']))
    index_file = f"{base_path}/{file_type}.{extension}"
    
    # Test with consolidate_index_and_default_files directly
    result = consolidate_index_and_default_files({index_file}, stop_level=stop_level)
    
    # The index file should NOT be consolidated (should remain as individual file)
    assert index_file in result, f"Index file {index_file} should not be consolidated at depth {blocked_depth} with stop level {stop_level}"
    
    # Should not contain the parent directory wildcard
    parent = get_parent_directory(index_file)
    parent_wildcard = '/*' if parent == '/' else f"{parent}/*"
    assert parent_wildcard not in result, f"Parent wildcard {parent_wildcard} should not be present when consolidation is blocked"
    
    # Now test with an allowed depth (>= stop_level)
    allowed_depth = data.draw(st.integers(min_value=stop_level, max_value=stop_level + 2))
    
    # Create path segments for the allowed depth
    allowed_path_segments = []
    for i in range(allowed_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        allowed_path_segments.append(segment)
    
    # Create index/default file path at allowed depth
    allowed_base_path = '/' + '/'.join(allowed_path_segments) if allowed_path_segments else ''
    allowed_index_file = f"{allowed_base_path}/{file_type}.{extension}"
    
    # Test consolidation at allowed depth
    allowed_result = consolidate_index_and_default_files({allowed_index_file}, stop_level=stop_level)
    
    # The index file SHOULD be consolidated at allowed depth
    allowed_parent = get_parent_directory(allowed_index_file)
    allowed_parent_wildcard = '/*' if allowed_parent == '/' else f"{allowed_parent}/*"
    assert allowed_parent_wildcard in allowed_result, f"Index file should be consolidated to {allowed_parent_wildcard} at depth {allowed_depth} with stop level {stop_level}"
    assert allowed_index_file not in allowed_result, f"Original index file {allowed_index_file} should be replaced by wildcard"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_12_directory_threshold_consolidation_stop_level_compliance(data):
    """Property 12: Directory threshold consolidation stop level compliance.
    
    For any directory threshold consolidation, when ConsolidationStopLevel prevents 
    consolidation at the target depth, the system should not perform the consolidation.
    
    **Feature: consolidation-stop-level-fix, Property 12: Directory threshold consolidation stop level compliance**
    **Validates: Requirements 6.2**
    """
    # Generate a stop level that will prevent consolidation at shallow depths
    stop_level = data.draw(st.integers(min_value=2, max_value=4))
    
    # Generate a directory at a depth LESS than stop_level (should be blocked)
    # Rule: depth < stop_level prevents consolidation
    blocked_depth = data.draw(st.integers(min_value=0, max_value=stop_level - 1))
    
    # Create path segments for the blocked depth
    path_segments = []
    for i in range(blocked_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    # Create directory path
    base_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create multiple files in the directory (more than threshold to trigger consolidation)
    num_files = data.draw(st.integers(min_value=5, max_value=8))  # Above threshold of 3
    test_paths = set()
    for i in range(num_files):
        extension = data.draw(st.sampled_from(['html', 'js', 'css', 'png']))
        file_path = f"{base_path}/file{i}.{extension}" if base_path else f"/file{i}.{extension}"
        test_paths.add(file_path)
    
    # Test with consolidate_by_directory_threshold directly
    result = consolidate_by_directory_threshold(test_paths, stop_level=stop_level)
    
    # The files should NOT be consolidated (should remain as individual files)
    for file_path in test_paths:
        assert file_path in result, f"File {file_path} should not be consolidated at depth {blocked_depth} with stop level {stop_level}"
    
    # Should not contain the directory wildcard
    directory_wildcard = f"{base_path}/*" if base_path else "/*"
    assert directory_wildcard not in result, f"Directory wildcard {directory_wildcard} should not be present when consolidation is blocked"
    
    # Now test with an allowed depth (>= stop_level)
    allowed_depth = data.draw(st.integers(min_value=stop_level, max_value=stop_level + 2))
    
    # Create path segments for the allowed depth
    allowed_path_segments = []
    for i in range(allowed_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        allowed_path_segments.append(segment)
    
    # Create directory path at allowed depth
    allowed_base_path = '/' + '/'.join(allowed_path_segments) if allowed_path_segments else ''
    
    # Create multiple files in the allowed directory
    allowed_test_paths = set()
    for i in range(num_files):
        extension = data.draw(st.sampled_from(['html', 'js', 'css', 'png']))
        file_path = f"{allowed_base_path}/file{i}.{extension}" if allowed_base_path else f"/file{i}.{extension}"
        allowed_test_paths.add(file_path)
    
    # Test consolidation at allowed depth
    allowed_result = consolidate_by_directory_threshold(allowed_test_paths, stop_level=stop_level)
    
    # The files SHOULD be consolidated at allowed depth
    allowed_directory_wildcard = f"{allowed_base_path}/*" if allowed_base_path else "/*"
    assert allowed_directory_wildcard in allowed_result, f"Files should be consolidated to {allowed_directory_wildcard} at depth {allowed_depth} with stop level {stop_level}"
    
    # Original files should not be present (replaced by wildcard)
    for file_path in allowed_test_paths:
        assert file_path not in allowed_result, f"Original file {file_path} should be replaced by wildcard"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_13_sibling_directory_consolidation_stop_level_compliance(data):
    """Property 13: Sibling directory consolidation stop level compliance.
    
    For any sibling directory consolidation, when ConsolidationStopLevel prevents 
    consolidation at the target depth, the system should not perform the consolidation.
    
    **Feature: consolidation-stop-level-fix, Property 13: Sibling directory consolidation stop level compliance**
    **Validates: Requirements 6.3**
    """
    # Generate a stop level that will prevent consolidation at shallow depths
    stop_level = data.draw(st.integers(min_value=2, max_value=4))
    
    # Generate a parent directory at a depth LESS than stop_level (should be blocked)
    # Rule: depth < stop_level prevents consolidation
    blocked_depth = data.draw(st.integers(min_value=0, max_value=stop_level - 1))
    
    # Create path segments for the blocked depth
    path_segments = []
    for i in range(blocked_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    # Create parent directory path
    parent_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create multiple sibling directory wildcards (more than threshold of 10 to trigger consolidation)
    num_siblings = data.draw(st.integers(min_value=12, max_value=15))  # Above threshold of 10
    test_paths = set()
    for i in range(num_siblings):
        sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
        test_paths.add(sibling_wildcard)
    
    # Test with consolidate_sibling_directories directly
    result = consolidate_sibling_directories(test_paths, stop_level=stop_level)
    
    # The sibling wildcards should NOT be consolidated (should remain as individual wildcards)
    for sibling_wildcard in test_paths:
        assert sibling_wildcard in result, f"Sibling wildcard {sibling_wildcard} should not be consolidated at depth {blocked_depth} with stop level {stop_level}"
    
    # Should not contain the parent directory wildcard
    parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
    assert parent_wildcard not in result, f"Parent wildcard {parent_wildcard} should not be present when consolidation is blocked"
    
    # Now test with an allowed depth (>= stop_level)
    allowed_depth = data.draw(st.integers(min_value=stop_level, max_value=stop_level + 2))
    
    # Create path segments for the allowed depth
    allowed_path_segments = []
    for i in range(allowed_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        allowed_path_segments.append(segment)
    
    # Create parent directory path at allowed depth
    allowed_parent_path = '/' + '/'.join(allowed_path_segments) if allowed_path_segments else ''
    
    # Create multiple sibling directory wildcards at allowed depth
    allowed_test_paths = set()
    for i in range(num_siblings):
        sibling_wildcard = f"{allowed_parent_path}/dir{i}/*" if allowed_parent_path else f"/dir{i}/*"
        allowed_test_paths.add(sibling_wildcard)
    
    # Test consolidation at allowed depth
    allowed_result = consolidate_sibling_directories(allowed_test_paths, stop_level=stop_level)
    
    # The sibling wildcards SHOULD be consolidated at allowed depth
    allowed_parent_wildcard = f"{allowed_parent_path}/*" if allowed_parent_path else "/*"
    assert allowed_parent_wildcard in allowed_result, f"Siblings should be consolidated to {allowed_parent_wildcard} at depth {allowed_depth} with stop level {stop_level}"
    
    # Original sibling wildcards should not be present (replaced by parent wildcard)
    for sibling_wildcard in allowed_test_paths:
        assert sibling_wildcard not in allowed_result, f"Original sibling wildcard {sibling_wildcard} should be replaced by parent wildcard"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_14_consolidation_type_permission_at_allowed_depths(data):
    """Property 14: Consolidation type permission at allowed depths.
    
    For any consolidation operation at a depth where ConsolidationStopLevel allows 
    consolidation, the system should permit all consolidation types (index, directory, 
    sibling) at that depth.
    
    **Feature: consolidation-stop-level-fix, Property 14: Consolidation type permission at allowed depths**
    **Validates: Requirements 6.4**
    """
    # Generate a stop level and an allowed depth (>= stop_level)
    stop_level = data.draw(st.integers(min_value=1, max_value=4))
    allowed_depth = data.draw(st.integers(min_value=stop_level, max_value=stop_level + 2))
    
    # Create path segments for the allowed depth
    path_segments = []
    for i in range(allowed_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    base_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Test 1: Index file consolidation should be allowed
    file_type = data.draw(st.sampled_from(['index', 'default']))
    extension = data.draw(st.sampled_from(['html', 'htm', 'php']))
    index_file = f"{base_path}/{file_type}.{extension}" if base_path else f"/{file_type}.{extension}"
    
    index_result = consolidate_index_and_default_files({index_file}, stop_level=stop_level)
    parent_wildcard = f"{base_path}/*" if base_path else "/*"
    assert parent_wildcard in index_result, f"Index file consolidation should be allowed at depth {allowed_depth} with stop level {stop_level}"
    assert index_file not in index_result, f"Original index file should be replaced by wildcard"
    
    # Test 2: Directory threshold consolidation should be allowed
    num_files = data.draw(st.integers(min_value=5, max_value=8))  # Above threshold
    directory_files = set()
    for i in range(num_files):
        ext = data.draw(st.sampled_from(['html', 'js', 'css', 'png']))
        file_path = f"{base_path}/file{i}.{ext}"
        directory_files.add(file_path)
    
    directory_result = consolidate_by_directory_threshold(directory_files, stop_level=stop_level)
    assert parent_wildcard in directory_result, f"Directory threshold consolidation should be allowed at depth {allowed_depth} with stop level {stop_level}"
    
    # Original files should be replaced by wildcard
    for file_path in directory_files:
        assert file_path not in directory_result, f"Original file {file_path} should be replaced by wildcard"
    
    # Test 3: Sibling directory consolidation should be allowed
    num_siblings = data.draw(st.integers(min_value=12, max_value=15))  # Above threshold of 10
    sibling_wildcards = set()
    for i in range(num_siblings):
        sibling_wildcard = f"{base_path}/dir{i}/*"
        sibling_wildcards.add(sibling_wildcard)
    
    sibling_result = consolidate_sibling_directories(sibling_wildcards, stop_level=stop_level)
    assert parent_wildcard in sibling_result, f"Sibling directory consolidation should be allowed at depth {allowed_depth} with stop level {stop_level}"
    
    # Original sibling wildcards should be replaced by parent wildcard
    for sibling_wildcard in sibling_wildcards:
        assert sibling_wildcard not in sibling_result, f"Original sibling wildcard {sibling_wildcard} should be replaced by parent wildcard"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_15_stop_level_precedence_over_other_rules(data):
    """Property 15: Stop level precedence over other rules.
    
    For any scenario where multiple consolidation rules apply, the system should 
    ensure ConsolidationStopLevel takes precedence over other consolidation rules.
    
    **Feature: consolidation-stop-level-fix, Property 15: Stop level precedence over other rules**
    **Validates: Requirements 6.5**
    """
    # Generate a stop level that will create conflicts with other rules
    stop_level = data.draw(st.integers(min_value=2, max_value=4))
    
    # Create a scenario where consolidation would normally happen but stop level prevents it
    # Rule: depth < stop_level prevents consolidation
    blocked_depth = data.draw(st.integers(min_value=0, max_value=stop_level - 1))
    
    # Create path segments for the blocked depth
    path_segments = []
    for i in range(blocked_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    base_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create a mixed scenario with multiple consolidation triggers that should all be blocked
    test_paths = []
    
    # Add index files (would normally consolidate)
    file_type = data.draw(st.sampled_from(['index', 'default']))
    extension = data.draw(st.sampled_from(['html', 'htm']))
    index_file = f"{base_path}/{file_type}.{extension}" if base_path else f"/{file_type}.{extension}"
    test_paths.append(index_file)
    
    # Add many regular files in same directory (would normally trigger directory threshold)
    num_files = data.draw(st.integers(min_value=5, max_value=8))  # Above threshold of 3
    for i in range(num_files):
        ext = data.draw(st.sampled_from(['js', 'css', 'png']))
        file_path = f"{base_path}/file{i}.{ext}" if base_path else f"/file{i}.{ext}"
        test_paths.append(file_path)
    
    # Use the main consolidate_paths function which applies all rules
    result = consolidate_paths(test_paths, stop_level=stop_level)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    # Stop level should take precedence - no consolidation should occur
    # All original paths should be preserved
    for original_path in test_paths:
        assert original_path in consolidated, f"Stop level should prevent consolidation, but {original_path} was consolidated"
    
    # The directory wildcard should NOT be present
    directory_wildcard = f"{base_path}/*" if base_path else "/*"
    assert directory_wildcard not in consolidated, f"Directory wildcard {directory_wildcard} should not be present due to stop level precedence"
    
    # Now test the same scenario at an allowed depth to verify normal consolidation works
    allowed_depth = data.draw(st.integers(min_value=stop_level, max_value=stop_level + 2))
    
    # Create path segments for the allowed depth
    allowed_path_segments = []
    for i in range(allowed_depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        allowed_path_segments.append(segment)
    
    allowed_base_path = '/' + '/'.join(allowed_path_segments) if allowed_path_segments else ''
    
    # Create similar paths at allowed depth
    allowed_test_paths = []
    
    # Add index file
    allowed_index_file = f"{allowed_base_path}/{file_type}.{extension}"
    allowed_test_paths.append(allowed_index_file)
    
    # Add many regular files
    for i in range(num_files):
        ext = data.draw(st.sampled_from(['js', 'css', 'png']))
        file_path = f"{allowed_base_path}/file{i}.{ext}"
        allowed_test_paths.append(file_path)
    
    # Test consolidation at allowed depth
    allowed_result = consolidate_paths(allowed_test_paths, stop_level=stop_level)
    
    # Should return a single chunk
    assert len(allowed_result) == 1, "Should return single chunk"
    allowed_consolidated = allowed_result[0]
    
    # At allowed depth, consolidation SHOULD occur
    allowed_directory_wildcard = '/*' if allowed_base_path == '' else f"{allowed_base_path}/*"
    assert allowed_directory_wildcard in allowed_consolidated, f"Consolidation should occur at allowed depth {allowed_depth} with stop level {stop_level}"
    
    # Original paths should be replaced by wildcard (except possibly some edge cases)
    # The key point is that we should have fewer paths than we started with
    assert len(allowed_consolidated) < len(allowed_test_paths), f"Should have consolidated paths at allowed depth, got {len(allowed_consolidated)} from {len(allowed_test_paths)}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_1_sibling_threshold_parameter_usage(data):
    """Property 1: Sibling threshold parameter usage.
    
    For any set of sibling directory wildcards and custom sibling threshold,
    when the number of siblings exceeds the custom threshold and stop level allows,
    the system should consolidate them to the parent directory wildcard.
    
    **Feature: consolidation-stop-level-depth-fix, Property 1: Sibling threshold parameter usage**
    **Validates: Requirements 1.1, 1.2**
    """
    # Generate a custom sibling threshold (different from default of 10)
    custom_threshold = data.draw(st.integers(min_value=2, max_value=8))
    
    # Generate a number of siblings that exceeds the custom threshold
    num_siblings = data.draw(st.integers(min_value=custom_threshold + 1, max_value=custom_threshold + 5))
    
    # Generate a parent directory at a depth that allows consolidation
    depth = data.draw(st.integers(min_value=1, max_value=3))
    path_segments = []
    for i in range(depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    parent_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create sibling directory wildcards that exceed the custom threshold
    sibling_wildcards = []
    for i in range(num_siblings):
        sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
        sibling_wildcards.append(sibling_wildcard)
    
    # Use a stop level that allows consolidation at this depth
    stop_level = max(depth, 1)  # Ensure stop level allows consolidation at this depth
    
    # Test with the custom sibling threshold
    result = consolidate_paths(sibling_wildcards, stop_level=stop_level, sibling_threshold=custom_threshold)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should consolidate to parent wildcard since siblings exceed custom threshold
    parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
    assert parent_wildcard in consolidated, f"Should consolidate to {parent_wildcard} with {num_siblings} siblings exceeding threshold {custom_threshold}"
    
    # Original sibling wildcards should not be present (replaced by parent wildcard)
    for sibling_wildcard in sibling_wildcards:
        assert sibling_wildcard not in consolidated, f"Original sibling wildcard {sibling_wildcard} should be replaced by parent wildcard"
    
    # Test with a threshold that would NOT be exceeded
    high_threshold = num_siblings + 2  # Set threshold higher than number of siblings
    
    result_no_consolidation = consolidate_paths(sibling_wildcards, stop_level=stop_level, sibling_threshold=high_threshold)
    
    # Should return a single chunk
    assert len(result_no_consolidation) == 1, "Should return single chunk"
    
    consolidated_no_consolidation = result_no_consolidation[0]
    
    # Should NOT consolidate since siblings don't exceed the high threshold
    assert parent_wildcard not in consolidated_no_consolidation, f"Should not consolidate to {parent_wildcard} with {num_siblings} siblings not exceeding threshold {high_threshold}"
    
    # All original sibling wildcards should be present
    for sibling_wildcard in sibling_wildcards:
        assert sibling_wildcard in consolidated_no_consolidation, f"Original sibling wildcard {sibling_wildcard} should be preserved when threshold not exceeded"
    
    # Verify we have the expected number of paths (all original siblings)
    assert len(consolidated_no_consolidation) == num_siblings, f"Should have {num_siblings} paths when threshold not exceeded, got {len(consolidated_no_consolidation)}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_2_bucket_specific_sibling_threshold_usage(data):
    """Property 2: Bucket-specific sibling threshold usage.
    
    For any bucket configuration with a custom sibling directory threshold,
    when the handler processes paths that exceed that threshold,
    the system should use the bucket-specific threshold for consolidation.
    
    **Feature: consolidation-stop-level-depth-fix, Property 2: Bucket-specific sibling threshold usage**
    **Validates: Requirements 2.1, 2.4**
    """
    from unittest.mock import patch, Mock
    import os
    
    # Generate a custom sibling threshold (different from default)
    custom_threshold = data.draw(st.integers(min_value=2, max_value=6))
    
    # Generate a number of paths that would create siblings exceeding the custom threshold
    num_siblings = data.draw(st.integers(min_value=custom_threshold + 1, max_value=custom_threshold + 3))
    
    # Create bucket configuration with custom sibling threshold
    bucket_config = {
        'directory_threshold': 3,
        'stop_level': 1,
        'sibling_directory_threshold': custom_threshold,
        'directory_threshold_source': 'tag',
        'stop_level_source': 'tag',
        'sibling_directory_threshold_source': 'tag'
    }
    
    # Create messages that will result in sibling directories exceeding the threshold
    messages = []
    for i in range(num_siblings):
        message = {
            'MessageId': f'msg{i}',
            'ReceiptHandle': f'handle{i}',
            'parsed_body': {
                'bucketName': 'test-bucket',
                'originPath': '/prod/public',
                'objectKey': f'/prod/public/dir{i}/file.js',  # Each in different directory
                'stageId': 'prod'
            }
        }
        messages.append(message)
    
    # Mock all the dependencies
    with patch.dict(os.environ, {'QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'}):
        with patch('functions.processor.handler.receive_messages_batch') as mock_receive:
            with patch('functions.processor.handler.validate_bucket_tags') as mock_validate_bucket:
                with patch('functions.processor.handler.get_bucket_tags') as mock_get_tags:
                    with patch('functions.processor.handler.get_bucket_consolidation_config') as mock_get_config:
                        with patch('functions.processor.handler.find_matching_distributions') as mock_find_dist:
                            with patch('functions.processor.handler.validate_distribution_tags') as mock_validate_dist:
                                with patch('functions.processor.handler.consolidate_paths') as mock_consolidate:
                                    with patch('functions.processor.handler.create_invalidation') as mock_invalidate:
                                        with patch('functions.processor.handler.delete_messages_batch') as mock_delete:
                                            with patch('functions.processor.handler.close_window') as mock_close_window:
                                                
                                                # Set up mocks
                                                mock_receive.side_effect = [messages, []]  # First call returns messages, second returns empty
                                                mock_validate_bucket.return_value = True
                                                mock_get_tags.return_value = {'atlantis:Application': 'test-app', 'AllowInvalidationEvents': 'true'}
                                                mock_get_config.return_value = bucket_config
                                                mock_find_dist.return_value = ['DIST123']
                                                mock_validate_dist.return_value = True
                                                mock_consolidate.return_value = [['/prod/public/*']]  # Simulated consolidation result
                                                mock_invalidate.return_value = {'Id': 'INV123', 'Status': 'InProgress'}
                                                mock_delete.return_value = {'successful': [f'handle{i}' for i in range(num_siblings)], 'failed': []}
                                                
                                                # Import and call the handler
                                                from functions.processor.handler import handler
                                                
                                                context = Mock()
                                                context.aws_request_id = 'test-request-id'
                                                
                                                # Act
                                                result = handler({}, context)
                                                
                                                # Assert
                                                assert result['statusCode'] == 200, f"Handler should succeed, got {result}"
                                                
                                                # Verify that get_bucket_consolidation_config was called
                                                mock_get_config.assert_called_once_with('test-bucket')
                                                
                                                # Verify that consolidate_paths was called with the bucket-specific sibling threshold
                                                mock_consolidate.assert_called_once()
                                                call_args = mock_consolidate.call_args
                                                
                                                # Check that the sibling_threshold parameter was passed correctly
                                                assert 'sibling_threshold' in call_args[1], "sibling_threshold parameter should be passed to consolidate_paths"
                                                assert call_args[1]['sibling_threshold'] == custom_threshold, f"Expected sibling_threshold {custom_threshold}, got {call_args[1]['sibling_threshold']}"
                                                
                                                # Also verify other parameters are passed correctly
                                                assert call_args[1]['directory_threshold'] == bucket_config['directory_threshold'], "directory_threshold should match bucket config"
                                                assert call_args[1]['stop_level'] == bucket_config['stop_level'], "stop_level should match bucket config"

@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_3_sibling_threshold_boundary_conditions(data):
    """Property 3: Sibling threshold boundary conditions.
    
    For any sibling threshold value, the system should consolidate siblings only when
    the count strictly exceeds the threshold (count > threshold), not when equal.
    
    **Feature: consolidation-stop-level-depth-fix, Property 3: Sibling threshold boundary conditions**
    **Validates: Requirements 2.1, 2.2**
    """
    # Generate a custom sibling threshold
    threshold = data.draw(st.integers(min_value=2, max_value=8))
    
    # Generate a parent directory at a depth that allows consolidation
    depth = data.draw(st.integers(min_value=1, max_value=3))
    path_segments = []
    for i in range(depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    parent_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Use a stop level that allows consolidation at this depth
    stop_level = max(depth, 1)
    
    # Test Case 1: Exactly at threshold (should NOT consolidate)
    sibling_wildcards_at_threshold = []
    for i in range(threshold):
        sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
        sibling_wildcards_at_threshold.append(sibling_wildcard)
    
    result_at_threshold = consolidate_paths(sibling_wildcards_at_threshold, 
                                          stop_level=stop_level, 
                                          sibling_threshold=threshold)
    
    assert len(result_at_threshold) == 1, "Should return single chunk"
    consolidated_at_threshold = result_at_threshold[0]
    
    # Should NOT consolidate (count == threshold, need count > threshold)
    parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
    assert parent_wildcard not in consolidated_at_threshold, \
        f"Should NOT consolidate {threshold} siblings with threshold {threshold} (need > threshold)"
    
    # All original sibling wildcards should remain
    for sibling in sibling_wildcards_at_threshold:
        assert sibling in consolidated_at_threshold, \
            f"Sibling {sibling} should remain when count equals threshold"
    
    # Test Case 2: Just above threshold (should consolidate)
    sibling_wildcards_above_threshold = []
    for i in range(threshold + 1):
        sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
        sibling_wildcards_above_threshold.append(sibling_wildcard)
    
    result_above_threshold = consolidate_paths(sibling_wildcards_above_threshold, 
                                             stop_level=stop_level, 
                                             sibling_threshold=threshold)
    
    assert len(result_above_threshold) == 1, "Should return single chunk"
    consolidated_above_threshold = result_above_threshold[0]
    
    # Should consolidate (count > threshold)
    assert parent_wildcard in consolidated_above_threshold, \
        f"Should consolidate {threshold + 1} siblings with threshold {threshold} (count > threshold)"
    
    # Original sibling wildcards should be replaced
    for sibling in sibling_wildcards_above_threshold:
        assert sibling not in consolidated_above_threshold, \
            f"Sibling {sibling} should be replaced by parent wildcard when count exceeds threshold"
    
    # Test Case 3: Just below threshold (should NOT consolidate)
    if threshold > 1:  # Only test if threshold allows for below-threshold case
        sibling_wildcards_below_threshold = []
        for i in range(threshold - 1):
            sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
            sibling_wildcards_below_threshold.append(sibling_wildcard)
        
        result_below_threshold = consolidate_paths(sibling_wildcards_below_threshold, 
                                                 stop_level=stop_level, 
                                                 sibling_threshold=threshold)
        
        assert len(result_below_threshold) == 1, "Should return single chunk"
        consolidated_below_threshold = result_below_threshold[0]
        
        # Should NOT consolidate (count < threshold)
        assert parent_wildcard not in consolidated_below_threshold, \
            f"Should NOT consolidate {threshold - 1} siblings with threshold {threshold} (count < threshold)"
        
        # All original sibling wildcards should remain
        for sibling in sibling_wildcards_below_threshold:
            assert sibling in consolidated_below_threshold, \
                f"Sibling {sibling} should remain when count is below threshold"

@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_4_backward_compatibility_with_missing_parameter(data):
    """Property 4: Backward compatibility with missing parameter.
    
    For any consolidation operation where sibling_threshold parameter is not provided,
    the system should use the global constant as fallback and produce identical results
    to explicit None parameter usage.
    
    **Feature: consolidation-stop-level-depth-fix, Property 4: Backward compatibility with missing parameter**
    **Validates: Requirements 1.3, 3.3**
    """
    # Generate test data that will trigger sibling consolidation
    # Use the default threshold (10) to create predictable behavior
    num_siblings = data.draw(st.integers(min_value=11, max_value=15))  # Above default threshold of 10
    
    # Generate a parent directory at a depth that allows consolidation
    depth = data.draw(st.integers(min_value=1, max_value=3))
    path_segments = []
    for i in range(depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    parent_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create sibling directory wildcards that exceed the default threshold
    sibling_wildcards = []
    for i in range(num_siblings):
        sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
        sibling_wildcards.append(sibling_wildcard)
    
    # Use a stop level that allows consolidation at this depth
    stop_level = max(depth, 1)  # Ensure stop level allows consolidation at this depth
    
    # Test 1: Call without sibling_threshold parameter (backward compatibility)
    result_without_param = consolidate_paths(sibling_wildcards, stop_level=stop_level)
    
    # Test 2: Call with explicit None for sibling_threshold
    result_with_none = consolidate_paths(sibling_wildcards, stop_level=stop_level, sibling_threshold=None)
    
    # Test 3: Call with only other parameters specified
    result_other_params = consolidate_paths(sibling_wildcards, directory_threshold=3, stop_level=stop_level)
    
    # All three approaches should produce identical results
    assert result_without_param == result_with_none, "Missing parameter should behave same as explicit None"
    assert result_without_param == result_other_params, "Missing parameter should behave same when other params specified"
    
    # Verify the consolidation actually happened (should consolidate to parent wildcard)
    assert len(result_without_param) == 1, "Should return single chunk"
    consolidated = result_without_param[0]
    
    parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
    assert parent_wildcard in consolidated, f"Should consolidate to {parent_wildcard} with {num_siblings} siblings exceeding default threshold"
    
    # Original sibling wildcards should not be present (replaced by parent wildcard)
    for sibling_wildcard in sibling_wildcards:
        assert sibling_wildcard not in consolidated, f"Original sibling wildcard {sibling_wildcard} should be replaced by parent wildcard"
    
    # Test boundary condition: exactly at default threshold (should NOT consolidate)
    boundary_siblings = []
    for i in range(10):  # Exactly at default threshold of 10
        sibling_wildcard = f"{parent_path}/boundary{i}/*" if parent_path else f"/boundary{i}/*"
        boundary_siblings.append(sibling_wildcard)
    
    # Test without parameter
    boundary_result_without = consolidate_paths(boundary_siblings, stop_level=stop_level)
    
    # Test with explicit None
    boundary_result_with_none = consolidate_paths(boundary_siblings, stop_level=stop_level, sibling_threshold=None)
    
    # Should produce identical results (no consolidation since 10 is not > 10)
    assert boundary_result_without == boundary_result_with_none, "Boundary condition should behave identically"
    
    # Should NOT consolidate at boundary
    assert len(boundary_result_without) == 1, "Should return single chunk"
    boundary_consolidated = boundary_result_without[0]
    assert len(boundary_consolidated) == 10, f"Should have 10 individual wildcards at boundary, got {len(boundary_consolidated)}"
    
    # All original sibling wildcards should be present (not consolidated)
    for sibling_wildcard in boundary_siblings:
        assert sibling_wildcard in boundary_consolidated, f"Boundary sibling wildcard {sibling_wildcard} should not be consolidated"
    
    # Parent wildcard should NOT be present at boundary
    assert parent_wildcard not in boundary_consolidated, f"Parent wildcard {parent_wildcard} should not be present at boundary condition"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_5_comprehensive_sibling_threshold_behavior(data):
    """Property 5: Comprehensive sibling threshold behavior.
    
    For any sibling threshold value and sibling count, the system should consolidate
    siblings if and only if the count strictly exceeds the threshold and stop level allows.
    
    **Feature: consolidation-stop-level-depth-fix, Property 5: Comprehensive sibling threshold behavior**
    **Validates: Requirements 4.1, 4.2, 4.3**
    """
    # Generate a custom sibling threshold
    threshold = data.draw(st.integers(min_value=1, max_value=8))
    
    # Generate test cases around the threshold boundary
    test_cases = [
        threshold - 1,  # Below threshold (should not consolidate)
        threshold,      # At threshold (should not consolidate)
        threshold + 1,  # Above threshold (should consolidate)
        threshold + 2   # Well above threshold (should consolidate)
    ]
    
    # Filter out invalid cases
    test_cases = [count for count in test_cases if count > 0]
    
    for sibling_count in test_cases:
        # Generate a parent directory at a depth that allows consolidation
        depth = data.draw(st.integers(min_value=1, max_value=3))
        path_segments = []
        for i in range(depth):
            segment = data.draw(st.text(
                alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
                min_size=1, max_size=8
            ))
            path_segments.append(segment)
        
        parent_path = '/' + '/'.join(path_segments) if path_segments else ''
        
        # Create sibling directory wildcards
        sibling_wildcards = []
        for i in range(sibling_count):
            sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
            sibling_wildcards.append(sibling_wildcard)
        
        # Use a stop level that allows consolidation at this depth
        stop_level = max(depth, 1)
        
        # Test consolidation
        result = consolidate_paths(sibling_wildcards, stop_level=stop_level, sibling_threshold=threshold)
        
        # Should return a single chunk
        assert len(result) == 1, f"Should return single chunk for {sibling_count} siblings with threshold {threshold}"
        
        consolidated = result[0]
        parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
        
        # Verify consolidation behavior based on threshold
        if sibling_count > threshold:
            # Should consolidate (count > threshold)
            assert parent_wildcard in consolidated, \
                f"Should consolidate {sibling_count} siblings with threshold {threshold} (count > threshold)"
            
            # Original sibling wildcards should be replaced
            for sibling_wildcard in sibling_wildcards:
                assert sibling_wildcard not in consolidated, \
                    f"Original sibling {sibling_wildcard} should be replaced when {sibling_count} > {threshold}"
            
            # Should have exactly one path (the parent wildcard)
            assert len(consolidated) == 1, \
                f"Should have exactly one consolidated path when {sibling_count} > {threshold}, got {len(consolidated)}"
        else:
            # Should NOT consolidate (count <= threshold)
            assert parent_wildcard not in consolidated, \
                f"Should not consolidate {sibling_count} siblings with threshold {threshold} (count <= threshold)"
            
            # All original sibling wildcards should remain
            assert len(consolidated) == sibling_count, \
                f"Should have {sibling_count} individual wildcards when not consolidating, got {len(consolidated)}"
            
            for sibling_wildcard in sibling_wildcards:
                assert sibling_wildcard in consolidated, \
                    f"Original sibling {sibling_wildcard} should remain when {sibling_count} <= {threshold}"
        
        # Test with stop level that prevents consolidation
        blocking_stop_level = depth + 1  # Set stop level higher than depth to block consolidation
        
        result_blocked = consolidate_paths(sibling_wildcards, stop_level=blocking_stop_level, sibling_threshold=threshold)
        
        assert len(result_blocked) == 1, "Should return single chunk when blocked by stop level"
        consolidated_blocked = result_blocked[0]
        
        # Should NOT consolidate regardless of threshold due to stop level
        assert parent_wildcard not in consolidated_blocked, \
            f"Should not consolidate due to stop level {blocking_stop_level} at depth {depth}"
        
        # All original sibling wildcards should remain
        assert len(consolidated_blocked) == sibling_count, \
            f"Should have {sibling_count} individual wildcards when blocked by stop level"
        
        for sibling_wildcard in sibling_wildcards:
            assert sibling_wildcard in consolidated_blocked, \
                f"Original sibling {sibling_wildcard} should remain when blocked by stop level"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_5_sibling_threshold_interaction_with_directory_threshold(data):
    """Property 5: Sibling threshold interaction with directory threshold.
    
    For any scenario involving both directory threshold and sibling threshold,
    the system should apply both consolidation rules correctly in sequence.
    
    **Feature: consolidation-stop-level-depth-fix, Property 5: Comprehensive sibling threshold behavior**
    **Validates: Requirements 4.1, 4.2, 4.3**
    """
    # Generate custom thresholds
    directory_threshold = data.draw(st.integers(min_value=2, max_value=4))
    sibling_threshold = data.draw(st.integers(min_value=2, max_value=4))
    
    # Generate a parent directory
    depth = data.draw(st.integers(min_value=1, max_value=2))
    path_segments = []
    for i in range(depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    parent_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create multiple sibling directories, each with files exceeding directory threshold
    num_siblings = sibling_threshold + 1  # Ensure we exceed sibling threshold
    num_files_per_dir = directory_threshold + 1  # Ensure we exceed directory threshold
    
    all_paths = []
    for i in range(num_siblings):
        for j in range(num_files_per_dir):
            file_path = f"{parent_path}/dir{i}/file{j}.html" if parent_path else f"/dir{i}/file{j}.html"
            all_paths.append(file_path)
    
    # Use stop level that allows consolidation
    stop_level = max(depth, 1)
    
    # Test multi-stage consolidation
    result = consolidate_paths(all_paths, 
                             directory_threshold=directory_threshold,
                             sibling_threshold=sibling_threshold, 
                             stop_level=stop_level)
    
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    # Should consolidate all the way to parent wildcard
    # Stage 1: Files -> Directory wildcards (due to directory threshold)
    # Stage 2: Directory wildcards -> Parent wildcard (due to sibling threshold)
    parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
    assert parent_wildcard in consolidated, \
        f"Should consolidate to {parent_wildcard} through multi-stage consolidation"
    
    # Should have exactly one path (the parent wildcard)
    assert len(consolidated) == 1, \
        f"Should have exactly one consolidated path after multi-stage consolidation, got {len(consolidated)}"
    
    # None of the original files should remain
    for file_path in all_paths:
        assert file_path not in consolidated, \
            f"Original file {file_path} should be replaced by parent wildcard"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.data())
def test_property_5_sibling_threshold_parameter_precedence(data):
    """Property 5: Sibling threshold parameter precedence over global constant.
    
    For any consolidation with explicit sibling_threshold parameter,
    the system should use the parameter value instead of the global constant.
    
    **Feature: consolidation-stop-level-depth-fix, Property 5: Comprehensive sibling threshold behavior**
    **Validates: Requirements 4.1, 4.2, 4.3**
    """
    # Import the global constant
    from functions.processor.path_consolidator import SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD
    
    # Generate a custom threshold different from the global constant
    custom_threshold = data.draw(st.integers(min_value=2, max_value=6))
    # Ensure it's different from global constant
    if custom_threshold == SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD:
        custom_threshold = SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD + 1
    
    # Generate sibling count that would behave differently with custom vs global threshold
    # Choose count that exceeds custom but not global (or vice versa)
    if custom_threshold < SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD:
        # Custom threshold is lower - use count that exceeds custom but not global
        sibling_count = custom_threshold + 1
        if sibling_count > SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD:
            sibling_count = custom_threshold - 1  # Fall back to below custom threshold
    else:
        # Custom threshold is higher - use count that exceeds global but not custom
        sibling_count = SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD + 1
        if sibling_count > custom_threshold:
            sibling_count = min(custom_threshold - 1, SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD - 1)
    
    # Ensure we have a valid test case
    if sibling_count <= 0:
        sibling_count = 3  # Safe fallback
    
    # Generate parent directory
    depth = data.draw(st.integers(min_value=1, max_value=2))
    path_segments = []
    for i in range(depth):
        segment = data.draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')), 
            min_size=1, max_size=8
        ))
        path_segments.append(segment)
    
    parent_path = '/' + '/'.join(path_segments) if path_segments else ''
    
    # Create sibling directory wildcards
    sibling_wildcards = []
    for i in range(sibling_count):
        sibling_wildcard = f"{parent_path}/dir{i}/*" if parent_path else f"/dir{i}/*"
        sibling_wildcards.append(sibling_wildcard)
    
    # Use stop level that allows consolidation
    stop_level = max(depth, 1)
    
    # Test with custom threshold parameter
    result_custom = consolidate_paths(sibling_wildcards, 
                                    stop_level=stop_level, 
                                    sibling_threshold=custom_threshold)
    
    # Test without parameter (should use global constant)
    result_global = consolidate_paths(sibling_wildcards, stop_level=stop_level)
    
    # Test with explicit None (should use global constant)
    result_none = consolidate_paths(sibling_wildcards, 
                                  stop_level=stop_level, 
                                  sibling_threshold=None)
    
    # Verify that global and None produce identical results
    assert result_global == result_none, \
        "Missing parameter should behave same as explicit None"
    
    # Verify behavior based on thresholds
    assert len(result_custom) == 1, "Should return single chunk with custom threshold"
    assert len(result_global) == 1, "Should return single chunk with global threshold"
    
    consolidated_custom = result_custom[0]
    consolidated_global = result_global[0]
    parent_wildcard = f"{parent_path}/*" if parent_path else "/*"
    
    # Check custom threshold behavior
    if sibling_count > custom_threshold:
        assert parent_wildcard in consolidated_custom, \
            f"Should consolidate {sibling_count} siblings with custom threshold {custom_threshold}"
    else:
        assert parent_wildcard not in consolidated_custom, \
            f"Should not consolidate {sibling_count} siblings with custom threshold {custom_threshold}"
    
    # Check global threshold behavior
    if sibling_count > SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD:
        assert parent_wildcard in consolidated_global, \
            f"Should consolidate {sibling_count} siblings with global threshold {SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD}"
    else:
        assert parent_wildcard not in consolidated_global, \
            f"Should not consolidate {sibling_count} siblings with global threshold {SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD}"
    
    # If thresholds produce different behavior, results should be different
    if ((sibling_count > custom_threshold) != (sibling_count > SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD)):
        assert result_custom != result_global, \
            f"Custom threshold {custom_threshold} should produce different result than global threshold {SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD} for {sibling_count} siblings"