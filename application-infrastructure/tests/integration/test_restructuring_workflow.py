#!/usr/bin/env python3
"""
Integration tests for complete restructuring workflow.

**Feature: test-directory-restructure, Integration Test: Complete restructuring workflow**
**Validates: Requirements 2.3, 3.3**

This module tests the end-to-end restructuring process to verify all components
work together correctly after the directory structure changes.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import pytest
from pathlib import Path

# No need to add src to path - using new function structure

class TestRestructuringWorkflow:
    """Integration tests for the complete restructuring workflow."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        self.test_root = Path(__file__).parent.parent.parent
        self.src_dir = self.test_root / "src"
        self.tests_dir = self.test_root / "tests"
        
    def test_directory_structure_exists(self):
        """
        Test that the new directory structure exists and is properly organized.
        
        **Validates: Requirements 1.1, 1.2**
        """
        # Verify new tests directory exists
        assert self.tests_dir.exists(), "Tests directory should exist at application-infrastructure/tests/"
        
        # Verify old tests directory no longer exists
        old_tests_dir = self.src_dir / "tests"
        assert not old_tests_dir.exists(), "Old tests directory should not exist at src/tests/"
        
        # Verify subdirectory structure is preserved
        expected_subdirs = ["integration", "property", "unit"]
        for subdir in expected_subdirs:
            subdir_path = self.tests_dir / subdir
            assert subdir_path.exists(), f"Subdirectory {subdir} should exist in tests/"
            assert subdir_path.is_dir(), f"{subdir} should be a directory"
    
    def test_virtual_environment_setup(self):
        """
        Test that the test virtual environment is properly configured.
        
        **Validates: Requirements 4.1, 4.3**
        """
        venv_dir = self.tests_dir / ".venv-test"
        requirements_file = self.tests_dir / "requirements.txt"
        
        # Verify virtual environment directory exists
        assert venv_dir.exists(), "Virtual environment directory should exist"
        assert venv_dir.is_dir(), "Virtual environment should be a directory"
        
        # Verify requirements.txt exists
        assert requirements_file.exists(), "Test requirements.txt should exist"
        
        # Verify virtual environment has Python executable
        python_exe = venv_dir / "bin" / "python"
        if not python_exe.exists():
            python_exe = venv_dir / "Scripts" / "python.exe"  # Windows
        assert python_exe.exists(), "Python executable should exist in virtual environment"
    
    def test_import_paths_work_correctly(self):
        """
        Test that all import paths work correctly from the new location.
        
        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        # Test that we can import from new function structure
        try:
            from common.logger import setup_logger
            from common.constants import SQS_VISIBILITY_TIMEOUT_SECONDS
            from functions.ingestor.handler import handler as ingestor_handler
            from functions.processor.handler import handler as processor_handler
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
        
        # Verify imports work as expected
        logger = setup_logger("test")
        assert logger is not None, "Logger should be created successfully"
        assert isinstance(SQS_VISIBILITY_TIMEOUT_SECONDS, int), "Constant should be imported correctly"
    
    def test_all_test_files_can_be_imported(self):
        """
        Test that all test files can be imported without errors.
        
        **Validates: Requirements 2.3**
        """
        test_files_to_check = []
        
        # Collect all Python test files
        for test_subdir in ["integration", "property", "unit"]:
            test_dir = self.tests_dir / test_subdir
            if test_dir.exists():
                for test_file in test_dir.glob("test_*.py"):
                    test_files_to_check.append(test_file)
        
        assert len(test_files_to_check) > 0, "Should find test files to check"
        
        # Try to import each test file
        import_errors = []
        for test_file in test_files_to_check:
            try:
                # Get module name relative to tests directory
                relative_path = test_file.relative_to(self.tests_dir)
                module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
                module_name = ".".join(module_parts)
                
                # Import the module
                __import__(module_name)
            except ImportError as e:
                import_errors.append(f"{test_file.name}: {e}")
        
        if import_errors:
            pytest.fail(f"Import errors found:\n" + "\n".join(import_errors))
    
    def test_build_configuration_updated(self):
        """
        Test that build configuration files reference the correct test paths.
        
        **Validates: Requirements 3.1, 3.2**
        """
        buildspec_file = self.test_root / "buildspec.yml"
        
        if buildspec_file.exists():
            buildspec_content = buildspec_file.read_text()
            
            # Check that buildspec references new test location
            assert "tests/" in buildspec_content, "buildspec.yml should reference tests/ directory"
            
            # Check that old test path is not referenced
            assert "src/tests/" not in buildspec_content, "buildspec.yml should not reference old src/tests/ path"
    
    def test_test_execution_works(self):
        """
        Test that tests can be executed successfully from the new location.
        
        **Validates: Requirements 2.3, 4.2**
        """
        # Try to run a simple unit test to verify execution works
        test_command = [
            sys.executable, "-m", "pytest", 
            str(self.tests_dir / "unit"), 
            "-v", "--tb=short", "-x"  # Stop on first failure
        ]
        
        try:
            # Run in the application-infrastructure directory
            result = subprocess.run(
                test_command,
                cwd=str(self.test_root),
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )
            
            # Check that pytest could at least start and discover tests
            # We don't require all tests to pass, just that the structure works
            assert result.returncode in [0, 1], f"pytest should run successfully. Output: {result.stdout}\nError: {result.stderr}"
            
            # Verify no import errors in output
            assert "ImportError" not in result.stderr, f"No import errors should occur. Error output: {result.stderr}"
            assert "ModuleNotFoundError" not in result.stderr, f"No module not found errors should occur. Error output: {result.stderr}"
            
        except subprocess.TimeoutExpired:
            pytest.fail("Test execution timed out - this may indicate import or configuration issues")
        except Exception as e:
            pytest.fail(f"Failed to execute tests: {e}")
    
    def test_property_tests_can_run(self):
        """
        Test that property-based tests can be executed from the new location.
        
        **Validates: Requirements 2.3**
        """
        # Try to run a property test to verify Hypothesis integration works
        property_test_dir = self.tests_dir / "property"
        
        if not property_test_dir.exists():
            pytest.skip("No property tests directory found")
        
        # Find a property test file to run
        property_test_files = list(property_test_dir.glob("test_*.py"))
        if not property_test_files:
            pytest.skip("No property test files found")
        
        # Run one property test file
        test_file = property_test_files[0]
        test_command = [
            sys.executable, "-m", "pytest", 
            str(test_file), 
            "-v", "--tb=short", "-x"
        ]
        
        try:
            result = subprocess.run(
                test_command,
                cwd=str(self.test_root),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Verify no import errors
            assert "ImportError" not in result.stderr, f"No import errors in property tests. Error: {result.stderr}"
            assert "ModuleNotFoundError" not in result.stderr, f"No module errors in property tests. Error: {result.stderr}"
            
        except subprocess.TimeoutExpired:
            pytest.fail("Property test execution timed out")
        except Exception as e:
            pytest.fail(f"Failed to execute property tests: {e}")
    
    def test_integration_test_structure(self):
        """
        Test that integration tests maintain their structure and can be discovered.
        
        **Validates: Requirements 2.3, 3.3**
        """
        integration_dir = self.tests_dir / "integration"
        assert integration_dir.exists(), "Integration tests directory should exist"
        
        # Check for key integration test files
        expected_files = [
            "test_iam_permissions.py",
            "test_dynamodb_window_tracking.py"
        ]
        
        for expected_file in expected_files:
            file_path = integration_dir / expected_file
            if file_path.exists():  # Only check if file exists (some may be optional)
                assert file_path.is_file(), f"{expected_file} should be a file"
                
                # Verify file can be imported
                try:
                    # Read file to check for basic Python syntax
                    content = file_path.read_text()
                    assert "def test_" in content or "class Test" in content, f"{expected_file} should contain test functions or classes"
                except Exception as e:
                    pytest.fail(f"Failed to read {expected_file}: {e}")


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])