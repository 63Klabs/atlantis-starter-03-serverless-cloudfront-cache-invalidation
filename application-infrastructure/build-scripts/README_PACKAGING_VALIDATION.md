# Packaging Validation Tools

This directory contains tools to validate that Lambda function and layer packaging follows the correct structure for AWS deployment.

## Tools

### 1. Property-Based Tests

Located in `tests/property/`:

- `test_properties_layer_packaging_structure.py` - Validates layer packaging creates correct `python/common/` structure
- `test_properties_function_packaging_separation.py` - Validates functions exclude common layer code
- `test_properties_deployment_artifact_structure.py` - Validates deployment artifacts match Lambda expectations

Run with:
```bash
# Run all packaging validation tests
python -m pytest tests/property/test_properties_*packaging*.py tests/property/test_properties_deployment_artifact_structure.py -v

# Run specific property tests
python -m pytest tests/property/test_properties_layer_packaging_structure.py -v
python -m pytest tests/property/test_properties_function_packaging_separation.py -v
python -m pytest tests/property/test_properties_deployment_artifact_structure.py -v
```

### 2. Validation Script

`validate_packaging.py` - Interactive validation script for development use.

Usage:
```bash
# Validate everything
python build-scripts/validate_packaging.py --all

# Validate specific components
python build-scripts/validate_packaging.py --layer
python build-scripts/validate_packaging.py --functions
python build-scripts/validate_packaging.py --packages

# Validate layer and functions (most common)
python build-scripts/validate_packaging.py --layer --functions
```

## What Gets Validated

### Layer Structure (Property 6)
- ✅ `layers/common/python/common/` directory structure
- ✅ Required common modules: `logger.py`, `constants.py`, `retry.py`, `window_tracker.py`
- ✅ `__init__.py` exists in common module
- ✅ `requirements.txt` at layer root
- ✅ No Python files directly in `python/` directory
- ✅ Layer packaging creates correct zip structure

### Function Separation (Property 7)
- ✅ Functions have `handler.py` and `requirements.txt`
- ✅ Functions do NOT contain common layer modules
- ✅ Functions do NOT have `python/` or `common/` directories
- ✅ Function imports use `from common.module import` pattern
- ✅ Build process installs dependencies separately

### Deployment Artifacts (Property 15)
- ✅ CloudFormation template uses standard `CodeUri` and `ContentUri` patterns
- ✅ Layer references use `!Ref` pattern, not hardcoded ARNs
- ✅ Build process creates Lambda-compatible packages
- ✅ Handler functions exist with correct entry points
- ✅ No system files that interfere with Lambda deployment

## Integration with CI/CD

The property-based tests are automatically run as part of the test suite. The validation script can be used for local development and debugging.

### In buildspec.yml

The build process already includes:
- Layer dependency installation to `layers/common/python/`
- Function dependency installation to function directories
- Layer packaging with correct `python/` structure
- CloudFormation packaging for deployment

### Exit Codes

- `0` - All validations passed
- `1` - Some validations failed

## Troubleshooting

### Common Issues

1. **Missing common modules in layer**
   - Ensure modules exist in `layers/common/python/common/`
   - Check that `__init__.py` exists

2. **Function contains common modules**
   - Remove duplicate modules from function directories
   - Use imports like `from common.logger import setup_logger`

3. **Incorrect build configuration**
   - Check `buildspec.yml` dependency installation paths
   - Ensure layer packaging includes `python/` directory

4. **CloudFormation template issues**
   - Use `CodeUri: functions/function_name/` pattern
   - Use `ContentUri: layers/common/` pattern
   - Use `!Ref LayerName` for layer references

### Running Validation

Always run validation after making changes:

```bash
# Quick validation
python build-scripts/validate_packaging.py

# Full test suite
python -m pytest tests/property/test_properties_*packaging*.py -v
```

## Requirements Validated

This validation ensures compliance with:

- **Requirement 2.4**: Layer packaging creates `python/common/` structure
- **Requirement 2.5**: Function packaging excludes common layer code  
- **Requirement 5.3**: Deployment artifacts match Lambda expectations

The validation tools provide confidence that the packaging structure will work correctly in AWS Lambda runtime environment.