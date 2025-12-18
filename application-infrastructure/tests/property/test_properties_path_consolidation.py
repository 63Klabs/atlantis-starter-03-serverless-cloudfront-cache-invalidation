"""Property-based tests for path consolidation algorithm."""

import sys
import os

from hypothesis import given, settings, strategies as st, assume, HealthCheck
from functions.processor.path_consolidator import (
    consolidate_paths,
    is_index_or_default_file,
    get_parent_directory,
    consolidate_index_and_default_files
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

@settings(max_examples=100)
@given(index_or_default_file_path())
def test_property_20_index_and_default_file_directory_consolidation(file_path):
    """Property 20: Index and default file directory consolidation.
    
    For any object path ending with /index.* or /default.*, the consolidation
    algorithm should replace the file path with the parent directory path
    followed by /*.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 20: Index and default file directory consolidation**
    **Validates: Requirements 9.1**
    """
    # Verify the path is indeed an index or default file
    assert is_index_or_default_file(file_path), f"Path {file_path} should be index/default file"
    
    # Consolidate the path
    result = consolidate_paths([file_path])
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk for one path"
    
    consolidated = result[0]
    
    # Should have exactly one path (the parent directory wildcard)
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}"
    
    consolidated_path = consolidated[0]
    
    # Should end with /*
    assert consolidated_path.endswith('/*'), f"Consolidated path should end with /*, got {consolidated_path}"
    
    # The consolidated path should be the parent directory + /*
    parent = get_parent_directory(file_path)
    if parent == '/':
        expected = '/*'
    else:
        expected = f"{parent}/*"
    
    assert consolidated_path == expected, f"Expected {expected}, got {consolidated_path}"


@settings(max_examples=100)
@given(directory_with_files(min_files=4, max_files=10))
def test_property_21_directory_consolidation_threshold(directory_and_files):
    """Property 21: Directory consolidation threshold.
    
    For any set of object paths where more than 3 paths share the same parent
    directory, the consolidation algorithm should replace those paths with a
    single directory-level path <parent>/*.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 21: Directory consolidation threshold**
    **Validates: Requirements 9.2**
    """
    directory, files = directory_and_files
    
    # Verify we have more than 3 files
    assert len(files) > 3, f"Should have more than 3 files, got {len(files)}"
    
    # Consolidate the paths
    result = consolidate_paths(files)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should consolidate to a single directory wildcard
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}: {consolidated}"
    
    consolidated_path = consolidated[0]
    
    # Should be the directory with /*
    expected = f"{directory}/*"
    assert consolidated_path == expected, f"Expected {expected}, got {consolidated_path}"


@settings(max_examples=100)
@given(sibling_directories_with_wildcards(min_siblings=11, max_siblings=20))
def test_property_22_sibling_directory_consolidation(parent_and_wildcards):
    """Property 22: Sibling directory consolidation.
    
    For any set of directory-level paths where more than 10 sibling directories
    would be invalidated, the consolidation algorithm should replace them with
    their parent directory path followed by /*.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 22: Sibling directory consolidation**
    **Validates: Requirements 9.3**
    """
    parent, wildcards = parent_and_wildcards
    
    # Verify we have more than 10 sibling wildcards
    assert len(wildcards) > 10, f"Should have more than 10 siblings, got {len(wildcards)}"
    
    # Consolidate the paths
    result = consolidate_paths(wildcards)
    
    # Should return a single chunk
    assert len(result) == 1, "Should return single chunk"
    
    consolidated = result[0]
    
    # Should consolidate to parent wildcard
    assert len(consolidated) == 1, f"Should consolidate to single path, got {len(consolidated)}: {consolidated}"
    
    consolidated_path = consolidated[0]
    
    # Should be the parent with /*
    expected = f"{parent}/*"
    assert consolidated_path == expected, f"Expected {expected}, got {consolidated_path}"


@settings(max_examples=100)
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


@settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
@given(st.integers(min_value=1001, max_value=2000))
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


@settings(max_examples=100)
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


@settings(max_examples=100)
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