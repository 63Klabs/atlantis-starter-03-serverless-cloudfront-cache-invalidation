"""Unit tests for retry decorator."""

import sys
import os
import time
from unittest.mock import Mock, patch

import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from common.retry import (
    calculate_delay_with_jitter,
    retry_with_backoff
)


class TestCalculateDelayWithJitter:
    """Tests for calculate_delay_with_jitter function."""
    
    def test_initial_delay(self):
        """Test delay calculation for first attempt."""
        delay = calculate_delay_with_jitter(
            attempt=0,
            initial_delay_ms=100,
            jitter_percent=0
        )
        assert delay == 0.1  # 100ms = 0.1s
    
    def test_exponential_backoff(self):
        """Test exponential backoff progression."""
        # With no jitter for predictable testing
        delay_0 = calculate_delay_with_jitter(0, 100, 5000, 2, 0)
        delay_1 = calculate_delay_with_jitter(1, 100, 5000, 2, 0)
        delay_2 = calculate_delay_with_jitter(2, 100, 5000, 2, 0)
        
        assert delay_0 == 0.1  # 100ms
        assert delay_1 == 0.2  # 200ms
        assert delay_2 == 0.4  # 400ms
    
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay_ms."""
        delay = calculate_delay_with_jitter(
            attempt=10,
            initial_delay_ms=100,
            max_delay_ms=1000,
            multiplier=2,
            jitter_percent=0
        )
        assert delay == 1.0  # Capped at 1000ms = 1s
    
    def test_jitter_applied(self):
        """Test that jitter is applied to delay."""
        # Set seed for reproducibility
        import random
        random.seed(42)
        
        delay_with_jitter = calculate_delay_with_jitter(
            attempt=0,
            initial_delay_ms=100,
            jitter_percent=0.25
        )
        
        # Should be within ±25% of 100ms
        assert 0.075 <= delay_with_jitter <= 0.125
    
    def test_non_negative_delay(self):
        """Test that delay is never negative even with jitter."""
        for _ in range(100):
            delay = calculate_delay_with_jitter(
                attempt=0,
                initial_delay_ms=10,
                jitter_percent=0.5
            )
            assert delay >= 0


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""
    
    def test_success_on_first_attempt(self):
        """Test that function succeeds on first attempt without retry."""
        mock_func = Mock(return_value='success')
        decorated = retry_with_backoff(max_attempts=3)(mock_func)
        
        result = decorated()
        
        assert result == 'success'
        assert mock_func.call_count == 1
    
    def test_success_after_retries(self):
        """Test that function succeeds after some failures."""
        mock_func = Mock(side_effect=[
            ValueError('fail 1'),
            ValueError('fail 2'),
            'success'
        ])
        decorated = retry_with_backoff(
            max_attempts=3,
            exceptions=(ValueError,),
            initial_delay_ms=10
        )(mock_func)
        
        result = decorated()
        
        assert result == 'success'
        assert mock_func.call_count == 3
    
    def test_failure_after_max_attempts(self):
        """Test that exception is raised after max attempts."""
        mock_func = Mock(side_effect=ValueError('persistent error'))
        decorated = retry_with_backoff(
            max_attempts=3,
            exceptions=(ValueError,),
            initial_delay_ms=10
        )(mock_func)
        
        with pytest.raises(ValueError, match='persistent error'):
            decorated()
        
        assert mock_func.call_count == 3
    
    def test_specific_exception_handling(self):
        """Test that only specified exceptions are retried."""
        mock_func = Mock(side_effect=RuntimeError('not retryable'))
        decorated = retry_with_backoff(
            max_attempts=3,
            exceptions=(ValueError,),
            initial_delay_ms=10
        )(mock_func)
        
        with pytest.raises(RuntimeError, match='not retryable'):
            decorated()
        
        # Should fail immediately without retry
        assert mock_func.call_count == 1
    
    def test_retry_with_delay(self):
        """Test that retry waits between attempts."""
        mock_func = Mock(side_effect=[
            ValueError('fail'),
            'success'
        ])
        decorated = retry_with_backoff(
            max_attempts=3,
            exceptions=(ValueError,),
            initial_delay_ms=50,
            jitter_percent=0
        )(mock_func)
        
        start_time = time.time()
        result = decorated()
        elapsed_time = time.time() - start_time
        
        assert result == 'success'
        assert mock_func.call_count == 2
        # Should have waited at least 50ms (0.05s)
        assert elapsed_time >= 0.04  # Allow some tolerance
    
    def test_on_retry_callback(self):
        """Test that on_retry callback is called on each retry."""
        callback = Mock()
        mock_func = Mock(side_effect=[
            ValueError('fail 1'),
            ValueError('fail 2'),
            'success'
        ])
        decorated = retry_with_backoff(
            max_attempts=3,
            exceptions=(ValueError,),
            initial_delay_ms=10,
            on_retry=callback
        )(mock_func)
        
        result = decorated()
        
        assert result == 'success'
        assert callback.call_count == 2  # Called on first two failures
    
    def test_function_with_arguments(self):
        """Test that decorated function preserves arguments."""
        mock_func = Mock(return_value='success')
        decorated = retry_with_backoff(max_attempts=3)(mock_func)
        
        result = decorated('arg1', 'arg2', kwarg1='value1')
        
        assert result == 'success'
        mock_func.assert_called_once_with('arg1', 'arg2', kwarg1='value1')
    
    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        def original_func():
            """Original docstring."""
            return 'success'
        
        decorated = retry_with_backoff(max_attempts=3)(original_func)
        
        assert decorated.__name__ == 'original_func'
        assert decorated.__doc__ == 'Original docstring.'
