"""Unit tests for common layer structure."""

import importlib
from pathlib import Path
import pytest


class TestCommonLayerStructure:
    """Test that the common layer has the correct structure and modules."""
    
    def test_required_common_modules_exist(self):
        """Test that required common modules exist in correct locations."""
        # Requirements: 4.1, 4.4
        base_path = Path(__file__).parent.parent.parent / "layers" / "common" / "python" / "common"
        
        required_modules = [
            'logger.py',
            'constants.py', 
            'retry.py',
            'window_tracker.py'
        ]
        
        for module_name in required_modules:
            module_path = base_path / module_name
            assert module_path.exists(), f"Required common module {module_name} should exist at {module_path}"
            assert module_path.is_file(), f"Common module {module_name} should be a file"
            assert module_path.stat().st_size > 0, f"Common module {module_name} should not be empty"
    
    def test_common_init_file_exists(self):
        """Test that __init__.py exists in the common directory."""
        # Requirements: 4.4
        init_path = Path(__file__).parent.parent.parent / "layers" / "common" / "python" / "common" / "__init__.py"
        assert init_path.exists(), "Common layer should have __init__.py file"
        assert init_path.is_file(), "__init__.py should be a file"
    
    def test_common_modules_can_be_imported(self):
        """Test that common modules can be imported properly."""
        # Requirements: 4.1, 4.4
        modules_to_test = [
            'common.logger',
            'common.constants',
            'common.retry', 
            'common.window_tracker'
        ]
        
        for module_name in modules_to_test:
            try:
                module = importlib.import_module(module_name)
                assert module is not None, f"Module {module_name} should import successfully"
                
                # Verify it comes from the correct location
                if hasattr(module, '__file__') and module.__file__:
                    module_path = Path(module.__file__)
                    assert 'layers/common/python/common' in str(module_path), (
                        f"Module {module_name} should be loaded from layers/common/python/common"
                    )
                    
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
    
    def test_common_directory_structure(self):
        """Test that the common layer has the expected directory structure."""
        # Requirements: 4.4
        base_path = Path(__file__).parent.parent.parent / "layers" / "common"
        
        # Check main directories exist
        assert (base_path / "python").exists(), "layers/common/python directory should exist"
        assert (base_path / "python" / "common").exists(), "layers/common/python/common directory should exist"
        
        # Check requirements.txt exists at layer level
        assert (base_path / "requirements.txt").exists(), "layers/common/requirements.txt should exist"
    
    def test_no_duplicate_modules_in_functions(self):
        """Test that multi-function utilities are not duplicated in function directories."""
        # Requirements: 4.1
        functions_base = Path(__file__).parent.parent.parent / "functions"
        common_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
        function_dirs = ['ingestor', 'processor']
        
        for function_dir in function_dirs:
            function_path = functions_base / function_dir
            if function_path.exists():
                for module_name in common_modules:
                    duplicate_path = function_path / module_name
                    assert not duplicate_path.exists(), (
                        f"Common module {module_name} should not be duplicated in {function_dir} function directory. "
                        f"Found duplicate at {duplicate_path}"
                    )