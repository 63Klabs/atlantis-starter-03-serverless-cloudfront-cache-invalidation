#!/usr/bin/env python3
"""
Test handler integration with sibling threshold parameter.

This script tests that the processor handler correctly passes the sibling threshold
parameter from bucket configuration to the consolidate_paths function.
"""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Add the functions directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'functions'))

# Mock all the common modules
sys.modules['common'] = MagicMock()
sys.modules['common.constants'] = MagicMock()
sys.modules['common.logger'] = MagicMock()
sys.modules['common.window_tracker'] = MagicMock()

# Set up constants
from common.constants import (
    DIRECTORY_CONSOLIDATION_THRESHOLD,
    SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
    CONSOLIDATION_STOP_LEVEL
)

# Mock the constants
DIRECTORY_CONSOLIDATION_THRESHOLD = 3
SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD = 10
CONSOLIDATION_STOP_LEVEL = 1

# Mock logger
mock_logger = MagicMock()
sys.modules['common.logger'].setup_logger.return_value = mock_logger

def test_handler_sibling_threshold_integration():
    """Test that handler passes sibling threshold correctly."""
    print("Testing handler integration with sibling threshold parameter...")
    
    # Import the handler module first
    from processor import handler as handler_module
    
    # Mock all the dependencies
    with patch.dict('os.environ', {'QUEUE_URL': 'test-queue-url'}):
        with patch.object(handler_module, 'receive_messages_batch') as mock_receive:
            with patch.object(handler_module, 'validate_bucket_tags') as mock_validate_bucket:
                with patch.object(handler_module, 'get_bucket_tags') as mock_get_bucket_tags:
                    with patch.object(handler_module, 'get_bucket_consolidation_config') as mock_get_config:
                        with patch.object(handler_module, 'find_matching_distributions') as mock_find_dist:
                            with patch.object(handler_module, 'validate_distribution_tags') as mock_validate_dist:
                                with patch.object(handler_module, 'consolidate_paths') as mock_consolidate:
                                    with patch.object(handler_module, 'create_invalidation') as mock_invalidate:
                                        with patch.object(handler_module, 'delete_messages_batch') as mock_delete:
                                            with patch.object(handler_module, 'close_window') as mock_close:
                                                
                                                # Set up mock responses
                                                mock_receive.return_value = [
                                                    {
                                                        'MessageId': 'test-msg-1',
                                                        'ReceiptHandle': 'test-handle-1',
                                                        'Body': json.dumps({
                                                            'bucketName': 'test-bucket',
                                                            'objectKey': '/prod/public/test1.html',
                                                            'originPath': '/prod/public',
                                                            'stageId': 'prod',
                                                            'eventTime': '2023-01-01T00:00:00Z',
                                                            'eventType': 'ObjectCreated:Put'
                                                        }),
                                                        'parsed_body': {
                                                            'bucketName': 'test-bucket',
                                                            'objectKey': '/prod/public/test1.html',
                                                            'originPath': '/prod/public',
                                                            'stageId': 'prod',
                                                            'eventTime': '2023-01-01T00:00:00Z',
                                                            'eventType': 'ObjectCreated:Put'
                                                        }
                                                    }
                                                ]
                                                
                                                mock_validate_bucket.return_value = True
                                                mock_get_bucket_tags.return_value = {
                                                    'atlantis:Application': 'test-app'
                                                }
                                                
                                                # This is the key test - mock bucket config with sibling threshold
                                                mock_get_config.return_value = {
                                                    'directory_threshold': 3,
                                                    'stop_level': 1,
                                                    'sibling_directory_threshold': 5,  # Custom sibling threshold
                                                    'directory_threshold_source': 'bucket_tag',
                                                    'stop_level_source': 'bucket_tag',
                                                    'sibling_directory_threshold_source': 'bucket_tag'
                                                }
                                                
                                                mock_find_dist.return_value = ['test-dist-id']
                                                mock_validate_dist.return_value = True
                                                mock_consolidate.return_value = [['/prod/public/test1.html']]
                                                mock_invalidate.return_value = {'Id': 'test-invalidation-id'}
                                                mock_delete.return_value = {'successful': [{'Id': 'test-msg-1'}], 'failed': []}
                                                
                                                # Import and run handler
                                                from processor.handler import handler
                                                
                                                # Call handler
                                                result = handler({}, Mock())
                                                
                                                # Verify handler succeeded
                                                assert result['statusCode'] == 200
                                                
                                                # Verify consolidate_paths was called with sibling_threshold
                                                mock_consolidate.assert_called_once()
                                                call_args = mock_consolidate.call_args
                                                
                                                # Check that sibling_threshold was passed
                                                assert 'sibling_threshold' in call_args.kwargs
                                                assert call_args.kwargs['sibling_threshold'] == 5
                                                
                                                # Check other parameters too
                                                assert call_args.kwargs['directory_threshold'] == 3
                                                assert call_args.kwargs['stop_level'] == 1
                                                
                                                print("✅ Handler correctly passes sibling_threshold parameter")
                                                print(f"   - sibling_threshold: {call_args.kwargs['sibling_threshold']}")
                                                print(f"   - directory_threshold: {call_args.kwargs['directory_threshold']}")
                                                print(f"   - stop_level: {call_args.kwargs['stop_level']}")
                                                
                                                return True

def test_handler_backward_compatibility():
    """Test handler backward compatibility when sibling threshold is missing."""
    print("\nTesting handler backward compatibility...")
    
    # Mock all the dependencies
    with patch.dict('os.environ', {'QUEUE_URL': 'test-queue-url'}):
        with patch('processor.handler.receive_messages_batch') as mock_receive:
            with patch('processor.handler.validate_bucket_tags') as mock_validate_bucket:
                with patch('processor.handler.get_bucket_tags') as mock_get_bucket_tags:
                    with patch('processor.handler.get_bucket_consolidation_config') as mock_get_config:
                        with patch('processor.handler.find_matching_distributions') as mock_find_dist:
                            with patch('processor.handler.validate_distribution_tags') as mock_validate_dist:
                                with patch('processor.handler.consolidate_paths') as mock_consolidate:
                                    with patch('processor.handler.create_invalidation') as mock_invalidate:
                                        with patch('processor.handler.delete_messages_batch') as mock_delete:
                                            with patch('processor.handler.close_window') as mock_close:
                                                
                                                # Set up mock responses
                                                mock_receive.return_value = [
                                                    {
                                                        'MessageId': 'test-msg-1',
                                                        'ReceiptHandle': 'test-handle-1',
                                                        'Body': json.dumps({
                                                            'bucketName': 'test-bucket',
                                                            'objectKey': '/prod/public/test1.html',
                                                            'originPath': '/prod/public',
                                                            'stageId': 'prod',
                                                            'eventTime': '2023-01-01T00:00:00Z',
                                                            'eventType': 'ObjectCreated:Put'
                                                        }),
                                                        'parsed_body': {
                                                            'bucketName': 'test-bucket',
                                                            'objectKey': '/prod/public/test1.html',
                                                            'originPath': '/prod/public',
                                                            'stageId': 'prod',
                                                            'eventTime': '2023-01-01T00:00:00Z',
                                                            'eventType': 'ObjectCreated:Put'
                                                        }
                                                    }
                                                ]
                                                
                                                mock_validate_bucket.return_value = True
                                                mock_get_bucket_tags.return_value = {
                                                    'atlantis:Application': 'test-app'
                                                }
                                                
                                                # Mock bucket config WITHOUT sibling threshold (backward compatibility)
                                                mock_get_config.return_value = {
                                                    'directory_threshold': 3,
                                                    'stop_level': 1,
                                                    'sibling_directory_threshold': 10,  # Default value
                                                    'directory_threshold_source': 'default',
                                                    'stop_level_source': 'default',
                                                    'sibling_directory_threshold_source': 'default'
                                                }
                                                
                                                mock_find_dist.return_value = ['test-dist-id']
                                                mock_validate_dist.return_value = True
                                                mock_consolidate.return_value = [['/prod/public/test1.html']]
                                                mock_invalidate.return_value = {'Id': 'test-invalidation-id'}
                                                mock_delete.return_value = {'successful': [{'Id': 'test-msg-1'}], 'failed': []}
                                                
                                                # Import and run handler
                                                from processor.handler import handler
                                                
                                                # Call handler
                                                result = handler({}, Mock())
                                                
                                                # Verify handler succeeded
                                                assert result['statusCode'] == 200
                                                
                                                # Verify consolidate_paths was called with default sibling_threshold
                                                mock_consolidate.assert_called_once()
                                                call_args = mock_consolidate.call_args
                                                
                                                # Check that sibling_threshold was passed with default value
                                                assert 'sibling_threshold' in call_args.kwargs
                                                assert call_args.kwargs['sibling_threshold'] == 10  # Default
                                                
                                                print("✅ Handler backward compatibility works correctly")
                                                print(f"   - sibling_threshold (default): {call_args.kwargs['sibling_threshold']}")
                                                
                                                return True

def main():
    """Main function."""
    print("Handler Integration Test for Sibling Threshold Parameter")
    print("=" * 60)
    
    try:
        # Test 1: Custom sibling threshold
        success1 = test_handler_sibling_threshold_integration()
        
        # Test 2: Backward compatibility
        success2 = test_handler_backward_compatibility()
        
        if success1 and success2:
            print("\n🎉 All handler integration tests passed!")
            print("The sibling threshold parameter is correctly integrated in the handler.")
            return 0
        else:
            print("\n❌ Some handler integration tests failed.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Handler integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())