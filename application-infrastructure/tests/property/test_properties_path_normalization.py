"""Property-based tests for S3 path normalization."""

from hypothesis import given, settings, strategies as st
from functions.ingestor.event_parser import normalize_s3_path


# Custom strategies for generating test data

@st.composite
def s3_path_string(draw):
    """Generate S3-like path strings with various formats.
    
    Generates paths that may or may not have leading slashes,
    and may contain multiple consecutive slashes.
    """
    # Generate 0-5 path segments
    num_segments = draw(st.integers(min_value=0, max_value=5))
    
    if num_segments == 0:
        # Empty path or just slashes
        return draw(st.sampled_from(['', '/', '//', '///']))
    
    # Generate path segments
    segments = []
    for _ in range(num_segments):
        segment = draw(st.text(
            min_size=1,
            max_size=15,
            alphabet=st.characters(
                whitelist_categories=('Ll', 'Lu', 'Nd'),
                whitelist_characters='-_.'
            )
        ))
        segments.append(segment)
    
    # Join segments with various slash patterns
    slash_pattern = draw(st.sampled_from([
        '/',      # Single slash
        '//',     # Double slash
        '///',    # Triple slash
    ]))
    
    path = slash_pattern.join(segments)
    
    # Optionally add leading slash(es)
    leading = draw(st.sampled_from(['', '/', '//', '///']))
    path = leading + path
    
    # Optionally add trailing slash
    if draw(st.booleans()):
        path = path + '/'
    
    return path


# Property Tests

@settings(max_examples=20)
@given(s3_path_string())
def test_property_1_path_normalization_idempotence(path):
    """Property 1: Path Normalization Idempotence.
    
    For any S3 object key string, normalizing it once or multiple times 
    should produce the same result with exactly one leading slash 
    (unless the path is empty).
    
    **Feature: s3-path-normalization-fix, Property 1: Path Normalization Idempotence**
    **Validates: Requirements 1.1, 1.2**
    """
    # Normalize once
    normalized_once = normalize_s3_path(path)
    
    # Normalize twice
    normalized_twice = normalize_s3_path(normalized_once)
    
    # Idempotence: normalize(normalize(x)) == normalize(x)
    assert normalized_once == normalized_twice, \
        f"Normalization is not idempotent for path '{path}': " \
        f"first={normalized_once}, second={normalized_twice}"
    
    # If path is not empty, result should have exactly one leading slash
    if normalized_once:
        assert normalized_once.startswith('/'), \
            f"Normalized path '{normalized_once}' should start with '/'"
        
        # Should not have double slashes at the start
        assert not normalized_once.startswith('//'), \
            f"Normalized path '{normalized_once}' should not start with '//'"
        
        # Should not have consecutive slashes anywhere
        assert '//' not in normalized_once, \
            f"Normalized path '{normalized_once}' should not contain '//'"


@st.composite
def path_with_multiple_slashes(draw):
    """Generate paths with various patterns of multiple consecutive slashes."""
    # Generate 1-4 path segments
    num_segments = draw(st.integers(min_value=1, max_value=4))
    
    segments = []
    for _ in range(num_segments):
        segment = draw(st.text(
            min_size=1,
            max_size=10,
            alphabet=st.characters(
                whitelist_categories=('Ll', 'Lu', 'Nd'),
                whitelist_characters='-_'
            )
        ))
        segments.append(segment)
    
    # Join segments with multiple slashes (2-5 slashes)
    num_slashes = draw(st.integers(min_value=2, max_value=5))
    separator = '/' * num_slashes
    path = separator.join(segments)
    
    # Optionally add leading multiple slashes
    if draw(st.booleans()):
        leading_slashes = draw(st.integers(min_value=2, max_value=5))
        path = ('/' * leading_slashes) + path
    
    return path


@settings(max_examples=20)
@given(path_with_multiple_slashes())
def test_property_9_multiple_slash_normalization(path):
    """Property 9: Multiple Slash Normalization.
    
    For any path containing multiple consecutive slashes, normalization 
    should collapse them to single s
lashes while preserving the overall path structure.
    
    **Feature: s3-path-normalization-fix, Property 9: Multiple Slash Normalization**
    **Validates: Requirements 6.2**
    """
    # Normalize the path
    normalized = normalize_s3_path(path)
    
    # Should not contain consecutive slashes
    assert '//' not in normalized, \
        f"Normalized path '{normalized}' should not contain consecutive slashes (original: '{path}')"
    
    # Should have exactly one leading slash (if not empty)
    if normalized:
        assert normalized.startswith('/'), \
            f"Normalized path '{normalized}' should start with '/' (original: '{path}')"
        assert not normalized.startswith('//'), \
            f"Normalized path '{normalized}' should not start with '//' (original: '{path}')"
    
    # Extract segments from original and normalized paths
    original_segments = [s for s in path.split('/') if s]
    normalized_segments = [s for s in normalized.split('/') if s]
    
    # The segments should be the same (order and content preserved)
    assert original_segments == normalized_segments, \
        f"Path structure not preserved: original segments {original_segments} != normalized segments {normalized_segments}"
