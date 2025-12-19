# Python Virtual Environment Guidelines

This document outlines the standards for Python virtual environment usage and dependency management.

## Virtual Environment Setup

### Naming Convention
- **Preferred**: `.venv` for new projects
- **Respect existing**: If `.ve` or `venv` already exists, use it
- **Location**: Virtual environment directory must be in the project root

### Creation and Activation
```bash
# Create virtual environment (preferred name, uses latest Python version)
python -m venv .venv

# Activate virtual environment
# Linux/Mac:
source .venv/bin/activate
# Windows:
.ve\Scripts\activate

# Verify activation
which python  # Should point to virtual environment
```

### Git Exclusion
- Virtual environments must NOT be committed to repository
- Ensure `.gitignore` excludes virtual environment directories
- Most repositories use `.*` pattern which covers `.venv` and `.ve`
- If using `venv` (without dot), explicitly add to `.gitignore`

## Requirements Management

### Requirements Files Structure
- **requirements.txt**: Production/deployment packages only
- **requirements-dev.txt**: Local development packages
- **requirements-test.txt**: Testing-specific packages

### Requirements Content Guidelines

#### requirements.txt (Production)
- Minimal packages for deployed compute services (Lambda, EC2)
- Exclude packages provided by compute environment (boto3, etc.)
- Keep packages up to date
- Mark outdated packages with comments for follow-up

#### requirements-dev.txt (Development)
- Packages needed for local development
- Include packages that would be available in build/compute environments
- Examples: boto3 (for local AWS development), development tools
- Comment: "Install requirements.txt and requirements-test.txt first, then this file"

#### requirements-test.txt (Testing)
- Only packages necessary for testing
- Exclude packages provided by CodeBuild or CI environment
- Focus on test frameworks and testing utilities
- Comment: "Install requirements.txt first, then this file"

### Package Management
- **Prune regularly**: Remove unused packages from requirements files
- **Keep updated**: Maintain current versions when possible
- **Avoid version pinning**: Only pin versions when specific issues exist
- **Document exceptions**: Comment pinned packages with timeline for resolution (address by next dev cycle)
- **Minimize deployment**: Keep Lambda/compute packages to absolute minimum

## Installation Process

### Standard Installation Order
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Install production requirements
pip install -r requirements.txt

# 3. Install test requirements (except for deployment packages)
pip install -r requirements-test.txt

# 4. Install dev requirements (local development only)
pip install -r requirements-dev.txt
```

### Environment-Specific Installation
- **Local Development**: Install all three requirements files
- **CI/CodeBuild**: Install requirements.txt + requirements-test.txt
- **Production/Lambda**: Install requirements.txt only

## Deployment Considerations

### Lambda and Compute Services
- **No virtual environment** during packaging for deployment
- Install packages directly in function directory for packaging
- Use minimal requirements.txt for deployment
- Exclude environment-provided packages

### CodeBuild
- Use AWS recommended practices by default
- Use virtual environments only when multiple tests/functions may conflict
- Follow standard installation process
- Exclude dev requirements in build environment

## AI Assistant Guidelines

### Python Task Execution
- Always use virtual environment when performing Python tasks
- Verify virtual environment is activated before running scripts
- Install required packages in virtual environment
- Check for existing virtual environment before creating new one

### Commands for AI
```bash
# Check for existing virtual environment
ls -la | grep -E "\.ve|\.venv|venv"

# Activate existing or create new
if [ -d ".ve" ]; then
    source .ve/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    python -m venv .venv
    source .venv/bin/activate
fi

# Install requirements (full development setup)
pip install -r requirements.txt
if [ -f "requirements-test.txt" ]; then
    pip install -r requirements-test.txt
fi
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
fi
```

## Best Practices

### Development Workflow
1. Always activate virtual environment before Python work
2. Install/update packages within virtual environment
3. Update requirements files when adding/removing packages
4. Test in clean virtual environment before deployment
5. Use latest Python version available on environment

### Version Management
- **No Python version pinning**: Always use latest available Python version
- **Minimal package pinning**: Only pin when specific version issues exist
- **Temporary solutions**: Address pinned packages by next development cycle
- **Keep moving forward**: Maintain currency with latest versions

### Maintenance
- Review and prune requirements monthly
- Update packages regularly (test thoroughly)
- Monitor for security vulnerabilities
- Keep requirements files organized and commented
- Include installation order comments in requirements files