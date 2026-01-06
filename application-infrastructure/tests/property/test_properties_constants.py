"""Property-based tests for constants module environment variable handling."""

import sys
import os
from unittest.mock import patch

from hypothesis import given, settings, strategies as st


@settings(max_examples=5)  # Optimized for faster execution
@given(st.integers(min_value=1, max_value=1000))
def test_property_3_environment_variable_reading(sibling_threshold):
    """Property 3: Environment variable reading.
    
    For any valid SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable value,
    the constants module should use that value as the default threshold.
    
    **Feature: sibling-directory-consolidation-threshold, Property 3: Environment variable reading**
    **Validates: Requirements 1.4, 5.2**
    """
    env_vars = {
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': str(sibling_threshold)
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        # Reload the constants module to pick up the new environment variable
        if 'common.constants' in sys.modules:
            del sys.modules['common.constants']
        
        from common.constants import SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD as loaded_threshold
        
        # Property: Environment variable should be read and used as constant
        assert loaded_threshold == sibling_threshold, \
            f"Expected threshold {sibling_threshold}, got {loaded_threshold}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.one_of(
    st.integers(min_value=-1000, max_value=0),  # Below valid range
    st.integers(min_value=1001, max_value=2000),  # Above valid range
    st.text(min_size=1, max_size=20).filter(lambda x: not x.isdigit()),  # Non-numeric
    st.just('')  # Empty string
))
def test_property_15_environment_variable_validation(invalid_value):
    """Property 15: Environment variable validation.
    
    For any SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable value,
    the system should validate it is between 1 and 1000 inclusive.
    
    **Feature: sibling-directory-consolidation-threshold, Property 15: Environment variable validation**
    **Validates: Requirements 5.4**
    """
    env_vars = {
        'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': str(invalid_value)
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        # Reload the constants module to pick up the new environment variable
        if 'common.constants' in sys.modules:
            del sys.modules['common.constants']
        
        from common.constants import SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD as loaded_threshold
        
        # Property: Invalid values should fall back to default of 10
        assert loaded_threshold == 10, \
            f"Expected default threshold 10 for invalid value '{invalid_value}', got {loaded_threshold}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.just(None))  # Test missing environment variable
def test_property_16_environment_variable_fallback(_):
    """Property 16: Environment variable fallback.
    
    For any invalid or missing SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable,
    the system should use the hardcoded default of 10.
    
    **Feature: sibling-directory-consolidation-threshold, Property 16: Environment variable fallback**
    **Validates: Requirements 5.3**
    """
    # Ensure the environment variable is not set
    env_vars = {}
    if 'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD' in os.environ:
        env_vars['SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD'] = None
    
    with patch.dict(os.environ, env_vars, clear=True):
        # Remove the environment variable if it exists
        if 'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD' in os.environ:
            del os.environ['SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD']
        
        # Reload the constants module
        if 'common.constants' in sys.modules:
            del sys.modules['common.constants']
        
        from common.constants import SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD as loaded_threshold
        
        # Property: Missing environment variable should use hardcoded default of 10
        assert loaded_threshold == 10, \
            f"Expected default threshold 10 for missing env var, got {loaded_threshold}"


@settings(max_examples=5)  # Optimized for faster execution
@given(
    st.one_of(
        st.integers(min_value=-100, max_value=-1),  # Below valid range
        st.integers(min_value=21, max_value=100),   # Above valid range (updated max is 20)
        st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_characters='\x00')).filter(lambda x: not x.isdigit()),  # Non-numeric, no null bytes
        st.just('')  # Empty string
    )
)
def test_property_11_13_14_consolidation_stop_level_validation(invalid_value):
    """Property 11, 13, 14: ConsolidationStopLevel parameter validation.
    
    For any ConsolidationStopLevel parameter value, the CloudFormation template should accept
    values between 0 and 20 inclusive and reject values outside this range.
    
    **Feature: sibling-directory-consolidation-threshold, Property 11: ConsolidationStopLevel parameter validation**
    **Feature: sibling-directory-consolidation-threshold, Property 13: ConsolidationStopLevel upper bound validation**
    **Feature: sibling-directory-consolidation-threshold, Property 14: ConsolidationStopLevel lower bound validation**
    **Validates: Requirements 4.1, 4.3, 4.4**
    """
    env_vars = {
        'CONSOLIDATION_STOP_LEVEL': str(invalid_value)
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        # Reload the constants module to pick up the new environment variable
        if 'common.constants' in sys.modules:
            del sys.modules['common.constants']
        
        from common.constants import CONSOLIDATION_STOP_LEVEL as loaded_stop_level
        
        # Property: Invalid values should fall back to default of 1
        assert loaded_stop_level == 1, \
            f"Expected default stop level 1 for invalid value '{invalid_value}', got {loaded_stop_level}"


@settings(max_examples=5)  # Optimized for faster execution
@given(st.integers(min_value=0, max_value=20))
def test_property_consolidation_stop_level_valid_range(stop_level):
    """Test that valid ConsolidationStopLevel values (0-20) are accepted.
    
    **Feature: sibling-directory-consolidation-threshold, Property 11: ConsolidationStopLevel parameter validation**
    **Validates: Requirements 4.1**
    """
    env_vars = {
        'CONSOLIDATION_STOP_LEVEL': str(stop_level)
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        # Reload the constants module to pick up the new environment variable
        if 'common.constants' in sys.modules:
            del sys.modules['common.constants']
        
        from common.constants import CONSOLIDATION_STOP_LEVEL as loaded_stop_level
        
        # Property: Valid values should be used as-is
        assert loaded_stop_level == stop_level, \
            f"Expected stop level {stop_level}, got {loaded_stop_level}"