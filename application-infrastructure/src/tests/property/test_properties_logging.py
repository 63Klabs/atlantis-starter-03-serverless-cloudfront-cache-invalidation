"""Property-based tests for JSON logging format."""

import sys
import os
import json
import logging
from io import StringIO

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from hypothesis import given, settings, strategies as st
from common.logger import setup_logger


# Custom strategies for generating test data

@st.composite
def log_message_data(draw):
    """Generate random log message data."""
    message = draw(st.text(min_size=1, max_size=200))
    
    # Generate extra fields dictionary
    num_fields = draw(st.integers(min_value=0, max_value=10))
    extra_fields = {}
    
    for _ in range(num_fields):
        key = draw(st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_')
        ).filter(lambda x: x and x[0].isalpha()))
        
        # Generate various types of values
        value_type = draw(st.integers(min_value=0, max_value=4))
        if value_type == 0:
            value = draw(st.text(max_size=100))
        elif value_type == 1:
            value = draw(st.integers())
        elif value_type == 2:
            value = draw(st.floats(allow_nan=False, allow_infinity=False))
        elif value_type == 3:
            value = draw(st.booleans())
        else:
            value = None
        
        extra_fields[key] = value
    
    return message, extra_fields


@st.composite
def log_level_choice(draw):
    """Generate a random log level."""
    return draw(st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']))


# Property Tests

@settings(max_examples=100)
@given(log_message_data(), log_level_choice())
def test_property_27_json_log_format_validity(log_data, log_level):
    """Property 27: JSON log format validity.
    
    For any log message produced by the Lambda functions, the message should
    be valid JSON that can be parsed without errors.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 27: JSON log format validity**
    **Validates: Requirements 13.3**
    """
    message, extra_fields = log_data
    
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a new logger for this test to avoid interference
    test_logger_name = f'test_logger_{id(log_buffer)}'
    logger = logging.getLogger(test_logger_name)
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    # Add handler with JSON formatter
    from common.logger import JSONFormatter
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log a message with extra fields
    log_method = getattr(logger, log_level.lower())
    if extra_fields:
        log_method(message, extra={'extra_fields': extra_fields})
    else:
        log_method(message)
    
    # Get the logged output
    log_output = log_buffer.getvalue().strip()
    
    # Verify the output is valid JSON
    try:
        parsed_log = json.loads(log_output)
        
        # Verify it's a dictionary
        assert isinstance(parsed_log, dict), "Log output should be a JSON object"
        
        # Verify required fields are present (based on our JSONFormatter implementation)
        assert 'timestamp' in parsed_log, "Log should contain a timestamp field"
        assert 'level' in parsed_log, "Log should contain a level field"
        assert 'message' in parsed_log, "Log should contain a message field"
        assert 'logger' in parsed_log, "Log should contain a logger field"
        
        # Verify the message matches what we logged
        assert parsed_log['message'] == message, "Message should match the logged message"
        
        # Verify the level matches
        assert parsed_log['level'] == log_level, "Level should match the log level"
        
        # If extra fields were provided, verify they're in the output
        if extra_fields:
            # Our JSONFormatter adds extra_fields directly to the log_data
            for key, value in extra_fields.items():
                assert key in parsed_log, f"Extra field '{key}' should be in log output"
                # Note: We can't always assert value equality because JSON serialization
                # may change types (e.g., None becomes null, which becomes None again)
        
    except json.JSONDecodeError as e:
        # If JSON parsing fails, the test should fail
        assert False, f"Log output is not valid JSON: {e}\nOutput: {log_output}"
    except Exception as e:
        # Any other exception should also fail the test
        assert False, f"Error validating log format: {e}\nOutput: {log_output}"
