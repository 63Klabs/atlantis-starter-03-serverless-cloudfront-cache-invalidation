"""Property-based tests for Ingestor event filtering."""

import sys
import os

from hypothesis import given, settings, strategies as st

# Add the functions directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../functions/ingestor'))

from event_filter import should_process_event
from common.constants import (
    ORIGIN_PATH_PATTERN,
    PRODUCTION_STAGE_IDENTIFIERS,
    NON_PRODUCTION_STAGE_IDENTIFIERS,
    PUBLIC_PATH_SEGMENT
)


# Custom strategies for generating test data

@st.composite
def stage_identifier_and_path(draw):
    """Generate a stage identifier and corresponding path.
    
    Returns a tuple of (stage_id, path, is_production)
    """
    # Choose whether to generate production or non-production stage
    is_production = draw(st.booleans())
    
    if is_production:
        stage_id = draw(st.sampled_from(PRODUCTION_STAGE_IDENTIFIERS))
    else:
        stage_id = draw(st.sampled_from(NON_PRODUCTION_STAGE_IDENTIFIERS))
    
    # Generate a file name
    filename = draw(st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'),
            whitelist_characters='-_.'
        )
    ))
    
    # Create path matching the pattern /{stageId}/public/filename
    path = f'/{stage_id}/{PUBLIC_PATH_SEGMENT}/{filename}'
    
    return (stage_id, path, is_production)


# Property Tests

@settings(max_examples=20)
@given(stage_identifier_and_path())
def test_property_5_production_stage_filtering_with_placeholder(stage_and_path):
    """Property 5: Production Stage Filtering with Placeholder.
    
    For any origin path pattern containing {stageId} and any event path,
    the Ingestor function should queue/allow the event if and only if
    the extracted stage identifier is in PRODUCTION_STAGE_IDENTIFIERS.
    
    **Feature: origin-path-pattern, Property 5: Production Stage Filtering with Placeholder**
    **Validates: Requirements 5.1, 7.1, 7.2**
    """
    stage_id, path, is_production = stage_and_path
    
    # Call should_process_event with the generated path
    should_process, reason = should_process_event(path)
    
    # Verify the result matches the expected behavior
    if is_production:
        assert should_process, \
            f"Production stage '{stage_id}' should be accepted for path '{path}', but was filtered: {reason}"
    else:
        assert not should_process, \
            f"Non-production stage '{stage_id}' should be filtered for path '{path}', but was accepted: {reason}"
    
    # Verify the stage identifier is correctly identified in the reason
    assert stage_id in reason or 'public segment' in reason.lower(), \
        f"Reason should mention stage '{stage_id}' or fallback logic, got: {reason}"
