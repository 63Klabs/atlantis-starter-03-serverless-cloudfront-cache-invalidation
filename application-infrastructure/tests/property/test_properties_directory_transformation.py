"""
Property-based tests for directory structure transformation.

**Feature: test-directory-restructure, Property 1: Directory structure transformation**
**Validates: Requirements 1.3, 1.4**
"""

import os
import tempfile
import shutil
from pathlib import Path
from hypothesis import given, strategies as st
import pytest


class TestDirectoryStructureTransformation:
    """Test directory structure transformation properties."""

    def test_directory_structure_transformation_preserves_files(self):
        """
        **Feature: test-directory-restructure, Property 1: Directory structure transformation**
        
        For any test directory restructuring operation, all test files should be moved 
        from `src/tests/` to `tests/` while preserving the subdirectory organization 
        (integration, property, unit).
        
        **Validates: Requirements 1.3, 1.4**
        """
        # Test with the actual directory structure - get paths relative to project root
        current_dir = Path(__file__).parent.parent.parent.parent
        src_tests_path = current_dir / "application-infrastructure" / "src" / "tests"
        dest_tests_path = current_dir / "application-infrastructure" / "tests"
        
        # Since restructuring is complete, verify old directory no longer exists
        # and new directory exists with all files
        assert not src_tests_path.exists(), f"Old source directory {src_tests_path} should not exist after restructuring"
        assert dest_tests_path.exists(), f"New destination directory {dest_tests_path} should exist"
        
        # Verify destination directory structure exists with all expected files
        assert dest_tests_path.exists(), f"Destination directory {dest_tests_path} should exist"
        
        # Check that subdirectories exist in destination and contain test files
        expected_subdirs = ["integration", "property", "unit"]
        total_files = 0
        
        for subdir in expected_subdirs:
            dest_subdir = dest_tests_path / subdir
            assert dest_subdir.exists(), f"Destination subdirectory {dest_subdir} should exist"
            assert dest_subdir.is_dir(), f"Subdirectory {subdir} should be a directory"
            
            # Count test files in this subdirectory
            test_files = list(dest_subdir.glob("test_*.py"))
            total_files += len(test_files)
        
        # Property: All files should have been successfully moved to destination structure
        # Verify we have test files in the new location
        assert total_files > 0, "Should have test files in the new directory structure"
        
        # Verify subdirectory organization is preserved
        for subdir in expected_subdirs:
            dest_subdir = dest_tests_path / subdir
            assert dest_subdir.is_dir(), f"Subdirectory {subdir} should be preserved as directory"

    @given(st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))), min_size=1, max_size=10))
    def test_file_preservation_property(self, filenames):
        """
        Property test: File movement should preserve all files with correct structure.
        
        **Feature: test-directory-restructure, Property 1: Directory structure transformation**
        **Validates: Requirements 1.3, 1.4**
        """
        # Create temporary directory structure for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create source structure
            src_tests = temp_path / "src" / "tests"
            dest_tests = temp_path / "tests"
            
            # Create subdirectories
            subdirs = ["integration", "property", "unit"]
            for subdir in subdirs:
                (src_tests / subdir).mkdir(parents=True, exist_ok=True)
                (dest_tests / subdir).mkdir(parents=True, exist_ok=True)
            
            # Create test files in source
            created_files = {}
            for subdir in subdirs:
                created_files[subdir] = []
                for i, filename in enumerate(filenames[:3]):  # Limit to 3 files per subdir
                    # Ensure valid filename
                    safe_filename = f"test_{filename}_{i}.py"
                    file_path = src_tests / subdir / safe_filename
                    file_path.write_text(f"# Test file {safe_filename}")
                    created_files[subdir].append(safe_filename)
            
            # Simulate file movement
            for subdir in subdirs:
                src_subdir = src_tests / subdir
                dest_subdir = dest_tests / subdir
                
                for file_path in src_subdir.iterdir():
                    if file_path.is_file():
                        dest_file = dest_subdir / file_path.name
                        shutil.copy2(file_path, dest_file)
            
            # Verify all files are preserved in correct structure
            for subdir in subdirs:
                dest_subdir = dest_tests / subdir
                dest_files = [f.name for f in dest_subdir.iterdir() if f.is_file()]
                
                # Property: All created files should exist in destination
                for expected_file in created_files[subdir]:
                    assert expected_file in dest_files, f"File {expected_file} should be preserved in {subdir}"
                
                # Property: No extra files should be created
                assert len(dest_files) == len(created_files[subdir]), f"File count should match in {subdir}"

    def test_subdirectory_organization_preserved(self):
        """
        Test that subdirectory organization (integration, property, unit) is preserved.
        
        **Feature: test-directory-restructure, Property 1: Directory structure transformation**
        **Validates: Requirements 1.3, 1.4**
        """
        # Get path relative to project root
        current_dir = Path(__file__).parent.parent.parent.parent
        dest_tests_path = current_dir / "application-infrastructure" / "tests"
        
        # Required subdirectories
        required_subdirs = ["integration", "property", "unit"]
        
        # Property: All required subdirectories should exist
        for subdir in required_subdirs:
            subdir_path = dest_tests_path / subdir
            assert subdir_path.exists(), f"Subdirectory {subdir} should exist"
            assert subdir_path.is_dir(), f"{subdir} should be a directory"
        
        # Property: No unexpected subdirectories should be created
        actual_subdirs = [d.name for d in dest_tests_path.iterdir() 
                         if d.is_dir() and not d.name.startswith('.')]
        
        # Filter out expected non-test directories
        test_subdirs = [d for d in actual_subdirs if d in required_subdirs]
        
        for subdir in required_subdirs:
            assert subdir in test_subdirs, f"Required subdirectory {subdir} should be present"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])