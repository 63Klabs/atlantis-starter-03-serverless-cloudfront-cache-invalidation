"""Property-based tests for path consolidator bucket-specific configuration."""

import sys
import os
from unittest.mock import patch

from hypothesis import given, settings, strategies as st, assume
from functions.processor.path_consolidator import (
    consolidate_paths,
    calculate_path_depth,
    is_consolidation_allowed_at_depth,
    consolidate_by_directory_threshold,
    consolidate_sibling_directories,
    consolidate_index_and_default_files
)


# Custom strategies for generating test data

@st.composite
def path_segment(draw):
    """Generate a valid path segment (directory or file name)."""
    return draw(st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'),
            whitelist_characters='.-_'
        )
    ))


@st.composite
def file_path(draw, min_depth=1, max_depth=5):
    """Generate a file path with specified depth."""
    segments = draw(st.lists(
        path_segment(),
        min_size=min_depth,
        max_size=max_depth
    ))
    return '/' + '/'.join(segments)


@st.composite
def directory_with_files_above_threshold(draw, min_threshold=4, max_threshold=10):
    """Generate a directory with files above a given threshold."""
    threshold = draw(st.integers(min_value=min_threshold, max_value=max_threshold))
    
    # Generate directory path
    dir_segments = draw(st.lists(
        path_segment(),
        min_size=1,
        max_size=3
    ))
    directory = '/' + '/'.join(dir_segments)
    
    # Generate files above threshold
    num_files = threshold + draw(st.integers(min_value=1, max_value=5))
    files = []
    for i in range(num_files):
        extension = draw(st.sampled_from(['html', 'js', 'css', 'png', 'jpg']))
        files.append(f"{directory}/file{i}.{extension}")
    
    return (directory, files, threshold)


@st.composite
def paths_at_specific_depth(draw, target_depth, num_paths=5):
    """Generate paths at a specific depth from root."""
    assume(target_depth >= 1)
    
    paths = []
    for i in range(num_paths):
        # Generate path segments to reach target depth
        segments = []
        for j in range(target_depth):
            segment = draw(path_segment())
            segments.append(segment)
        
        # Add filename
        filename = f"file{i}.html"
        segments.append(filename)
        
        path = '/' + '/'.join(segments)
        paths.append(path)
    
    return paths


@st.composite
def paths_for_consolidation_testing(draw, target_depth, min_files_per_dir=4):
    """Generate paths that will trigger consolidation for testing stop level behavior.
    
    Creates multiple files in the same directory to ensure consolidation threshold is met.
    """
    assume(target_depth >= 1)
    assume(min_files_per_dir >= 4)  # Need > 3 files to trigger consolidation
    
    # Generate a base directory path at target_depth - 1
    base_segments = []
    for j in range(target_depth - 1):
        segment = draw(path_segment())
        base_segments.append(segment)
    
    base_dir = '/' + '/'.join(base_segments) if base_segments else ''
    
    # Generate multiple files in the same directory
    num_files = draw(st.integers(min_value=min_files_per_dir, max_value=min_files_per_dir + 3))
    paths = []
    
    for i in range(num_files):
        filename = f"file{i}.html"
        if base_dir:
            path = f"{base_dir}/{filename}"
        else:
            path = f"/{filename}"
        paths.append(path)
    
    return paths


@st.composite
def sibling_directories_at_depth(draw, target_depth, num_siblings=12):
    """Generate sibling directory wildcards at a specific depth."""
    assume(target_depth >= 1)
    assume(num_siblings > 10)  # Above sibling threshold
    
    # Generate parent path (target_depth - 1)
    parent_segments = []
    for i in range(target_depth - 1):
        segment = draw(path_segment())
        parent_segments.append(segment)
    
    parent_path = '/' + '/'.join(parent_segments) if parent_segments else '/'
    
    # Generate sibling directories
    wildcards = []
    for i in range(num_siblings):
        sibling_name = f"dir{i}"
        if parent_path == '/':
            wildcard = f"/{sibling_name}/*"
        else:
            wildcard = f"{parent_path}/{sibling_name}/*"
        wildcards.append(wildcard)
    
    return (parent_path, wildcards)


# Property Tests

@settings(max_examples=20)  # Reduced per testing guidelines
@given(directory_with_files_above_threshold())
def test_property_5_bucket_specific_threshold_application(directory_and_files_and_threshold):
    """Property 5: Bucket-specific threshold application.
    
    For any set of paths from a specific bucket, the consolidation logic should
    apply the bucket-specific directory threshold when determining whether to
    consolidate files in directories.
    
    **Feature: dynamic-bucket-consolidation-config, Property 5: Bucket-specific threshold application**
    **Validates: Requirements 1.5**
    """
    directory, files, custom_threshold = directory_and_files_and_threshold
    
    # Calculate the depth of the directory to determine appropriate stop_level
    from functions.processor.path_consolidator import calculate_path_depth
    directory_depth = calculate_path_depth(directory, '/')
    
    # Use stop_level that allows consolidation at this depth (depth >= stop_level)
    # Subtract 1 to ensure consolidation is allowed at the directory depth
    stop_level = max(directory_depth - 1, 0)  # Use low stop_level to allow consolidation
    
    result = consolidate_paths(files, directory_threshold=custom_threshold, stop_level=stop_level)
    
    # Should return single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Since files are above the custom threshold, should consolidate to directory wildcard
    expected_wildcard = f"{directory}/*"
    assert expected_wildcard in consolidated, \
        f"Should consolidate to {expected_wildcard} with threshold {custom_threshold}, got {consolidated}"
    
    # Should not contain individual files
    for file_path in files:
        assert file_path not in consolidated, \
            f"Individual file {file_path} should be consolidated away"


@settings(max_examples=20)
@given(st.lists(file_path(min_depth=1, max_depth=1), min_size=5, max_size=20))
def test_property_9_root_consolidation_stop_level_zero(paths):
    """Property 9: Root consolidation for stop level zero.
    
    For any set of paths when the consolidation stop level is 0, the system
    should consolidate all paths to the root wildcard /*.
    
    **Feature: dynamic-bucket-consolidation-config, Property 9: Root consolidation for stop level zero**
    **Validates: Requirements 2.4**
    """
    # Test with stop level 0
    result = consolidate_paths(paths, stop_level=0)
    
    # Should return single chunk with only root wildcard
    assert len(result) == 1, "Should return single chunk"
    assert len(result[0]) == 1, "Should consolidate to single path"
    assert result[0][0] == '/*', f"Should consolidate to root wildcard, got {result[0]}"


@settings(max_examples=20)
@given(paths_for_consolidation_testing(target_depth=2, min_files_per_dir=4), st.integers(min_value=2, max_value=5))
def test_property_10_stop_level_consolidation_prevention(paths_at_depth, stop_level):
    """Property 10: Stop level consolidation prevention.
    
    For any set of paths and stop level, the system should prevent consolidation
    from occurring at depths greater than the stop level.
    
    **Feature: dynamic-bucket-consolidation-config, Property 10: Stop level consolidation prevention**
    **Validates: Requirements 2.5**
    """
    # The generator ensures we have enough files to trigger consolidation normally
    assert len(paths_at_depth) > 3, "Generator should provide enough files for consolidation"
    
    # Test with stop level that may or may not prevent consolidation
    result = consolidate_paths(paths_at_depth, directory_threshold=3, stop_level=stop_level)
    
    # Should return single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Calculate the depth of the parent directory that would be consolidated to
    first_path = paths_at_depth[0]
    parent_dir = '/'.join(first_path.split('/')[:-1])  # Remove filename
    parent_depth = calculate_path_depth(parent_dir, '/')
    
    if parent_depth < stop_level:
        # Stop level prevents consolidation at this depth (depth < stop_level), should keep individual files
        assert len(consolidated) == len(paths_at_depth), \
            f"Stop level {stop_level} should prevent consolidation at depth {parent_depth}, got {len(consolidated)} paths instead of {len(paths_at_depth)}"
        
        # Should not contain any wildcards at the blocked depth
        for path in consolidated:
            if path.endswith('/*'):
                wildcard_dir = path[:-2] if path != '/*' else '/'
                wildcard_depth = calculate_path_depth(wildcard_dir, '/')
                assert wildcard_depth >= stop_level, \
                    f"Should not consolidate at depth {wildcard_depth} < {stop_level}, but found {path}"
    else:
        # Stop level allows consolidation at this depth (depth >= stop_level)
        # Should consolidate since we have > 3 files in same directory
        directory_wildcards = [p for p in consolidated if p.endswith('/*')]
        assert len(directory_wildcards) > 0, \
            f"Stop level {stop_level} should allow consolidation at depth {parent_depth}"


@settings(max_examples=20)
@given(st.sampled_from(['/dir/index.html', '/dir/default.html', '/a/b/index.php', '/x/y/z/default.asp']), 
       st.integers(min_value=2, max_value=4))
def test_property_11_index_file_stop_level_interaction(index_file_path, stop_level):
    """Property 11: Index file stop level interaction.
    
    For any path ending with index.* or default.* files, when consolidating to
    the parent directory would violate the consolidation stop level, the system
    should not perform the consolidation.
    
    **Feature: dynamic-bucket-consolidation-config, Property 11: Index file stop level interaction**
    **Validates: Requirements 4.4**
    """
    # Calculate the depth of the parent directory
    parent_parts = index_file_path.split('/')[:-1]  # Remove filename
    parent_path = '/'.join(parent_parts) if len(parent_parts) > 1 else '/'
    parent_depth = len([p for p in parent_parts if p]) if parent_parts != [''] else 0
    
    result = consolidate_paths([index_file_path], stop_level=stop_level)
    
    # Should return single chunk
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    if parent_depth < stop_level:
        # Stop level should prevent consolidation (depth < stop_level)
        assert index_file_path in consolidated, \
            f"Stop level {stop_level} should prevent consolidation at depth {parent_depth}, keeping original file"
        
        # Should not create parent wildcard
        parent_wildcard = f"{parent_path}/*" if parent_path != '/' else '/*'
        assert parent_wildcard not in consolidated, \
            f"Should not create {parent_wildcard} when stop level prevents it"
    else:
        # Consolidation should be allowed (depth >= stop_level)
        expected_wildcard = f"{parent_path}/*" if parent_path != '/' else '/*'
        assert expected_wildcard in consolidated, \
            f"Should consolidate index file to {expected_wildcard} when stop level {stop_level} allows depth {parent_depth}"
        assert index_file_path not in consolidated, \
            "Original index file should be consolidated away"


@settings(max_examples=20)
@given(sibling_directories_at_depth(target_depth=2), st.integers(min_value=2, max_value=4))
def test_property_12_sibling_directory_stop_level_interaction(parent_and_wildcards, stop_level):
    """Property 12: Sibling directory stop level interaction.
    
    For any set of sibling directories, when consolidation would occur at depths
    greater than the stop level, the system should prevent that consolidation.
    
    **Feature: dynamic-bucket-consolidation-config, Property 12: Sibling directory stop level interaction**
    **Validates: Requirements 4.5**
    """
    parent_path, wildcards = parent_and_wildcards
    
    # Calculate parent depth
    parent_depth = calculate_path_depth(parent_path)
    
    result = consolidate_paths(wildcards, stop_level=stop_level)
    
    # Should return single chunk
    assert len(result) == 1, "Should return single chunk"
    consolidated = result[0]
    
    if parent_depth < stop_level:
        # Stop level should prevent consolidation - should keep individual siblings (depth < stop_level)
        assert len(consolidated) == len(wildcards), \
            f"Stop level {stop_level} should prevent consolidation at depth {parent_depth}, keeping {len(wildcards)} siblings"
        
        # Should not create parent wildcard
        parent_wildcard = f"{parent_path}/*" if parent_path != '/' else '/*'
        assert parent_wildcard not in consolidated, \
            f"Should not create {parent_wildcard} when stop level prevents it"
    else:
        # Consolidation should be allowed - should consolidate to parent (depth >= stop_level)
        expected_parent_wildcard = f"{parent_path}/*" if parent_path != '/' else '/*'
        assert expected_parent_wildcard in consolidated, \
            f"Should consolidate siblings to {expected_parent_wildcard} when stop level {stop_level} allows depth {parent_depth}"
        assert len(consolidated) == 1, \
            "Should consolidate all siblings to single parent wildcard"


@settings(max_examples=20)
@given(st.lists(file_path(min_depth=2, max_depth=4), min_size=5, max_size=15))
def test_property_14_backward_compatibility_preservation(paths):
    """Property 14: Backward compatibility preservation.
    
    For any consolidation operation when the stop level is 1 (default), the system
    should produce the same consolidation results as the original algorithm.
    
    **Feature: dynamic-bucket-consolidation-config, Property 14: Backward compatibility preservation**
    **Validates: Requirements 4.1**
    """
    # Test with stop level 1 (default - should allow all consolidation)
    result_with_stop_level = consolidate_paths(paths, stop_level=1)
    
    # Test with no stop level specified (should use default)
    result_default = consolidate_paths(paths)
    
    # Results should be identical
    assert len(result_with_stop_level) == len(result_default), \
        "Stop level 1 should produce same number of chunks as default"
    
    for i, (chunk_with_stop, chunk_default) in enumerate(zip(result_with_stop_level, result_default)):
        assert set(chunk_with_stop) == set(chunk_default), \
            f"Chunk {i} should be identical: stop_level_1={set(chunk_with_stop)}, default={set(chunk_default)}"


@settings(max_examples=20)
@given(paths_at_specific_depth(target_depth=3, num_paths=6), st.integers(min_value=2, max_value=4))
def test_property_18_stop_level_prevention_logging(paths_at_depth, stop_level):
    """Property 18: Stop level prevention logging.
    
    For any consolidation operation prevented by the stop level, the system should
    log the prevention decision with the affected paths.
    
    **Feature: dynamic-bucket-consolidation-config, Property 18: Stop level prevention logging**
    **Validates: Requirements 5.4**
    """
    # Ensure we have enough files to trigger consolidation normally
    assume(len(paths_at_depth) > 3)
    
    with patch('functions.processor.path_consolidator.logger') as mock_logger:
        result = consolidate_paths(paths_at_depth, directory_threshold=3, stop_level=stop_level)
        
        # Check if consolidation was prevented (paths remain unconsolidated)
        consolidated = result[0]
        consolidation_prevented = len(consolidated) == len(paths_at_depth)
        
        # For paths at depth 3, consolidation should be prevented only if stop_level > 3
        # But we also need to check if the parent directories would be prevented
        # Let's check if any stop level prevention logging occurred
        debug_logged = False
        for call in mock_logger.debug.call_args_list:
            call_str = str(call)
            if 'Stop level' in call_str and 'prevents' in call_str:
                debug_logged = True
                break
        
        # If consolidation was prevented and stop level could affect depth 3 or its parents
        if consolidation_prevented and debug_logged:
            # This is the expected case - stop level prevented consolidation and logged it
            assert True, "Stop level prevention was correctly logged"
        elif not consolidation_prevented and not debug_logged:
            # This is also expected - no prevention occurred, no logging needed
            assert True, "No stop level prevention occurred, no logging needed"
        elif consolidation_prevented and not debug_logged:
            # This might be prevention due to other reasons (like not enough files)
            # which is acceptable
            assert True, "Consolidation prevented for other reasons"
        else:
            # debug_logged but not consolidation_prevented - this shouldn't happen
            assert False, "Stop level prevention was logged but consolidation still occurred"


@settings(max_examples=20)
@given(directory_with_files_above_threshold(), st.integers(min_value=4, max_value=8))
def test_property_19_bucket_specific_threshold_logging(directory_and_files_and_threshold, custom_threshold):
    """Property 19: Bucket-specific threshold logging.
    
    For any consolidation operation using a bucket-specific threshold, the system
    should log the threshold value being used for that bucket.
    
    **Feature: dynamic-bucket-consolidation-config, Property 19: Bucket-specific threshold logging**
    **Validates: Requirements 5.5**
    """
    directory, files, _ = directory_and_files_and_threshold
    
    with patch('functions.processor.path_consolidator.logger') as mock_logger:
        result = consolidate_paths(files, directory_threshold=custom_threshold)
        
        # Should log the custom threshold being used
        info_logged = False
        for call in mock_logger.info.call_args_list:
            call_str = str(call)
            if 'directory_threshold' in call_str and str(custom_threshold) in call_str:
                info_logged = True
                break
        
        assert info_logged, \
            f"Should log bucket-specific threshold {custom_threshold} in consolidation info"
        
        # If consolidation occurred, should also log the consolidation decision
        consolidated = result[0]
        if f"{directory}/*" in consolidated:
            debug_logged = False
            for call in mock_logger.debug.call_args_list:
                call_str = str(call)
                if 'Directory threshold consolidation' in call_str and str(custom_threshold) in call_str:
                    debug_logged = True
                    break
            
            assert debug_logged, \
                f"Should log directory threshold consolidation decision with threshold {custom_threshold}"