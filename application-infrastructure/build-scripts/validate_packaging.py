#!/usr/bin/env python3
"""
Packaging validation script for Lambda function separation project.

This script validates that layer and function packaging follows the correct
structure for AWS Lambda deployment.

Usage:
    python validate_packaging.py [--layer] [--functions] [--all]
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path
from typing import List, Dict, Any


def validate_layer_structure(layer_path: Path) -> Dict[str, Any]:
    """Validate layer directory structure for Lambda compatibility.
    
    Args:
        layer_path: Path to the layer directory
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'info': []
    }
    
    # Check if layer directory exists
    if not layer_path.exists():
        results['valid'] = False
        results['errors'].append(f"Layer directory does not exist: {layer_path}")
        return results
    
    # Check python/ subdirectory
    python_dir = layer_path / 'python'
    if not python_dir.exists():
        results['valid'] = False
        results['errors'].append("Layer missing python/ subdirectory")
    else:
        results['info'].append("✓ Found python/ subdirectory")
    
    # Check common/ module directory
    common_dir = python_dir / 'common'
    if not common_dir.exists():
        results['valid'] = False
        results['errors'].append("Layer missing python/common/ subdirectory")
    else:
        results['info'].append("✓ Found python/common/ module directory")
    
    # Check __init__.py
    init_file = common_dir / '__init__.py'
    if not init_file.exists():
        results['valid'] = False
        results['errors'].append("Layer missing __init__.py in python/common/")
    else:
        results['info'].append("✓ Found __init__.py in common module")
    
    # Check expected common modules
    expected_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    for module in expected_modules:
        module_file = common_dir / module
        if not module_file.exists():
            results['warnings'].append(f"Missing expected common module: {module}")
        else:
            results['info'].append(f"✓ Found common module: {module}")
    
    # Check requirements.txt at layer root
    requirements_file = layer_path / 'requirements.txt'
    if not requirements_file.exists():
        results['warnings'].append("Layer missing requirements.txt")
    else:
        results['info'].append("✓ Found requirements.txt at layer root")
    
    # Check for files directly in python/ (should be in subdirectories)
    if python_dir.exists():
        python_files = [f for f in python_dir.iterdir() if f.is_file() and f.suffix == '.py']
        if python_files:
            results['warnings'].append(f"Python files found directly in python/: {[f.name for f in python_files]}")
        else:
            results['info'].append("✓ No Python files directly in python/ directory")
    
    return results


def validate_function_structure(function_path: Path) -> Dict[str, Any]:
    """Validate function directory structure for Lambda compatibility.
    
    Args:
        function_path: Path to the function directory
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'info': []
    }
    
    # Check if function directory exists
    if not function_path.exists():
        results['valid'] = False
        results['errors'].append(f"Function directory does not exist: {function_path}")
        return results
    
    # Check handler.py
    handler_file = function_path / 'handler.py'
    if not handler_file.exists():
        results['valid'] = False
        results['errors'].append("Function missing handler.py")
    else:
        results['info'].append("✓ Found handler.py")
    
    # Check requirements.txt
    requirements_file = function_path / 'requirements.txt'
    if not requirements_file.exists():
        results['warnings'].append("Function missing requirements.txt")
    else:
        results['info'].append("✓ Found requirements.txt")
    
    # Check that common modules are NOT in function directory
    common_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    for module in common_modules:
        module_file = function_path / module
        if module_file.exists():
            results['valid'] = False
            results['errors'].append(f"Function contains common module {module} - should be in layer")
        else:
            results['info'].append(f"✓ No duplicate common module: {module}")
    
    # Check that no layer-like structure exists
    python_dir = function_path / 'python'
    if python_dir.exists():
        results['valid'] = False
        results['errors'].append("Function contains python/ directory - this is for layers only")
    
    common_dir = function_path / 'common'
    if common_dir.exists():
        results['valid'] = False
        results['errors'].append("Function contains common/ directory - common modules should be in layer")
    
    return results


def validate_layer_package(package_path: Path) -> Dict[str, Any]:
    """Validate a layer zip package structure.
    
    Args:
        package_path: Path to the layer zip file
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'info': []
    }
    
    if not package_path.exists():
        results['valid'] = False
        results['errors'].append(f"Layer package does not exist: {package_path}")
        return results
    
    try:
        with zipfile.ZipFile(package_path, 'r') as zipf:
            file_list = zipf.namelist()
            
            # Check for python/ directory
            python_files = [f for f in file_list if f.startswith('python/')]
            if not python_files:
                results['valid'] = False
                results['errors'].append("Layer package missing python/ directory")
            else:
                results['info'].append("✓ Layer package contains python/ directory")
            
            # Check for python/common/ structure
            common_files = [f for f in file_list if f.startswith('python/common/')]
            if not common_files:
                results['valid'] = False
                results['errors'].append("Layer package missing python/common/ structure")
            else:
                results['info'].append("✓ Layer package contains python/common/ structure")
            
            # Check for __init__.py
            if 'python/common/__init__.py' not in file_list:
                results['valid'] = False
                results['errors'].append("Layer package missing python/common/__init__.py")
            else:
                results['info'].append("✓ Layer package contains __init__.py")
            
            # Check for expected modules
            expected_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
            for module in expected_modules:
                module_path = f'python/common/{module}'
                if module_path not in file_list:
                    results['warnings'].append(f"Layer package missing expected module: {module}")
                else:
                    results['info'].append(f"✓ Layer package contains: {module}")
    
    except zipfile.BadZipFile:
        results['valid'] = False
        results['errors'].append("Invalid zip file")
    except Exception as e:
        results['valid'] = False
        results['errors'].append(f"Error reading zip file: {e}")
    
    return results


def print_results(name: str, results: Dict[str, Any]) -> None:
    """Print validation results in a formatted way."""
    print(f"\n{'='*60}")
    print(f"VALIDATION RESULTS: {name}")
    print(f"{'='*60}")
    
    if results['valid']:
        print("✅ VALIDATION PASSED")
    else:
        print("❌ VALIDATION FAILED")
    
    if results['errors']:
        print(f"\n🚨 ERRORS ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"  • {error}")
    
    if results['warnings']:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for warning in results['warnings']:
            print(f"  • {warning}")
    
    if results['info']:
        print(f"\n✅ SUCCESS ({len(results['info'])}):")
        for info in results['info']:
            print(f"  • {info}")


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate Lambda packaging structure')
    parser.add_argument('--layer', action='store_true', help='Validate layer structure')
    parser.add_argument('--functions', action='store_true', help='Validate function structures')
    parser.add_argument('--packages', action='store_true', help='Validate zip packages')
    parser.add_argument('--all', action='store_true', help='Validate everything')
    
    args = parser.parse_args()
    
    # If no specific options, validate all
    if not any([args.layer, args.functions, args.packages]):
        args.all = True
    
    if args.all:
        args.layer = args.functions = args.packages = True
    
    # Get the application infrastructure path
    script_dir = Path(__file__).parent
    app_infra_path = script_dir.parent
    
    all_valid = True
    
    # Validate layer structure
    if args.layer:
        layer_path = app_infra_path / 'layers' / 'common'
        results = validate_layer_structure(layer_path)
        print_results("Layer Structure", results)
        all_valid = all_valid and results['valid']
    
    # Validate function structures
    if args.functions:
        function_dirs = ['functions/ingestor', 'functions/processor']
        for func_dir in function_dirs:
            function_path = app_infra_path / func_dir
            results = validate_function_structure(function_path)
            print_results(f"Function Structure: {func_dir}", results)
            all_valid = all_valid and results['valid']
    
    # Validate packages if they exist
    if args.packages:
        package_files = ['common-layer.zip']
        for package_file in package_files:
            package_path = app_infra_path / package_file
            if package_path.exists():
                results = validate_layer_package(package_path)
                print_results(f"Package: {package_file}", results)
                all_valid = all_valid and results['valid']
            else:
                print(f"\n📦 Package {package_file} not found (run build to create)")
    
    # Final summary
    print(f"\n{'='*60}")
    if all_valid:
        print("🎉 ALL VALIDATIONS PASSED")
        print("Your packaging structure is ready for Lambda deployment!")
    else:
        print("💥 SOME VALIDATIONS FAILED")
        print("Please fix the errors above before deploying.")
    print(f"{'='*60}")
    
    # Exit with appropriate code
    sys.exit(0 if all_valid else 1)


if __name__ == '__main__':
    main()