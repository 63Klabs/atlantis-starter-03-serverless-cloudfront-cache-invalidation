"""Property-based tests for OriginPathPattern validation."""

import re
from pathlib import Path

from hypothesis import given, settings, strategies as st


def get_pattern_regex():
    """Extract the AllowedPattern regex from CloudFormation template."""
    template_path = Path(__file__).parent.parent.parent / "template.yml"
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Extract the AllowedPattern regex
    pattern_match = re.search(
        r'OriginPathPattern:\s*\n.*?AllowedPattern:\s*"([^"]*)"',
        template_content,
        re.DOTALL
    )
    
    if not pattern_match:
        raise ValueError("Could not find OriginPathPattern AllowedPattern in template")
    
    # Convert CloudFormation regex to Python regex (remove extra escaping)
    cf_regex = pattern_match.group(1)
    python_regex = cf_regex.replace('\\\\', '\\')
    
    return python_regex


@settings(max_examples=20)  # Minimal iterations per testing guidelines
@given(st.text(
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),  # Uppercase, lowercase, digits
        whitelist_characters='-_/{}'
    ),
    min_size=1,
    max_size=50
))
def test_property_1_pattern_validation_completeness(pattern_string):
    """Property 1: Pattern Validation Completeness.
    
    For any origin path pattern string, the CloudFormation parameter validation should
    accept it if and only if it: starts with /, does not end with /, contains only
    valid path characters (a-z, A-Z, 0-9, -, _, {, }), and any curly braces only wrap
    the literal text 'stageId'.
    
    **Feature: origin-path-pattern, Property 1: Pattern Validation Completeness**
    **Validates: Requirements 1.3, 1.4, 1.5, 1.6, 11.1, 11.2, 11.3, 11.4**
    """
    pattern_regex = get_pattern_regex()
    
    # Determine if pattern should be valid based on requirements
    should_be_valid = (
        pattern_string == '' or  # Empty is allowed (uses default)
        (
            pattern_string.startswith('/') and  # Must start with /
            not pattern_string.endswith('/') and  # Must not end with /
            all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/{}' for c in pattern_string) and  # Valid chars
            _validate_curly_braces(pattern_string)  # Curly braces only wrap 'stageId'
        )
    )
    
    # Test if regex matches
    matches = re.fullmatch(pattern_regex, pattern_string) is not None
    
    # Property: Regex should match if and only if pattern is valid
    assert matches == should_be_valid, \
        f"Pattern '{pattern_string}' validation mismatch: regex says {matches}, should be {should_be_valid}"


def _validate_curly_braces(pattern: str) -> bool:
    """Validate that curly braces only wrap 'stageId'."""
    # Find all occurrences of text within curly braces
    brace_contents = re.findall(r'\{([^}]*)\}', pattern)
    
    # Check for unmatched braces
    if pattern.count('{') != pattern.count('}'):
        return False
    
    # All brace contents must be 'stageId'
    for content in brace_contents:
        if content != 'stageId':
            return False
    
    return True


@settings(max_examples=20)  # Minimal iterations per testing guidelines
@given(st.sampled_from([
    '/{stageId}/public',
    '/public',
    '/{stageId}/assets',
    '/content/{stageId}/public',
    '/public/{stageId}',
    '/{stageId}',
    '/a',
    '/a/b',
    '/a/b/c',
    '',  # Empty (uses default)
]))
def test_property_1_known_valid_patterns(valid_pattern):
    """Test that known valid patterns are accepted by the regex.
    
    **Feature: origin-path-pattern, Property 1: Pattern Validation Completeness**
    **Validates: Requirements 1.3, 1.4, 1.5, 1.6**
    """
    pattern_regex = get_pattern_regex()
    
    # Property: All known valid patterns should match
    matches = re.fullmatch(pattern_regex, valid_pattern) is not None
    assert matches, f"Valid pattern '{valid_pattern}' should match the regex"


@settings(max_examples=20)  # Minimal iterations per testing guidelines
@given(st.sampled_from([
    'public',  # Doesn't start with /
    '/public/',  # Ends with /
    '/{stage}/public',  # Wrong placeholder
    '/public/!@#',  # Invalid characters
    '/{stageId',  # Unclosed brace
    '/stageId}/public',  # Unopened brace
    '/{}/public',  # Empty braces
    '/{stageId}/{otherId}',  # Multiple different placeholders
    '//public',  # Double slash
    '/ /public',  # Space
]))
def test_property_1_known_invalid_patterns(invalid_pattern):
    """Test that known invalid patterns are rejected by the regex.
    
    **Feature: origin-path-pattern, Property 1: Pattern Validation Completeness**
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
    """
    pattern_regex = get_pattern_regex()
    
    # Property: All known invalid patterns should NOT match
    matches = re.fullmatch(pattern_regex, invalid_pattern) is not None
    assert not matches, f"Invalid pattern '{invalid_pattern}' should NOT match the regex"
