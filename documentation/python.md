# 🐍 Python Dependency Management Cheatsheet

This cheatsheet covers essential Python commands for installing, managing, and updating dependencies, along with basic project setup commands.

## 📦 Package Installation

### Install packages with pip

```bash
# Install a specific package
pip install package_name

# Install a specific version
pip install package_name==1.2.3

# Install from requirements file
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install package in editable mode (for development)
pip install -e .
```

### Alternative pip commands

```bash
# Use pip3 explicitly (useful when both Python 2 and 3 are installed)
pip3 install package_name

# Install for current user only
pip install --user package_name

# Upgrade a package to latest version
pip install --upgrade package_name
pip install -U package_name
```

## 🔄 Version Management

### Version specifiers

```bash
# Exact version
pip install package_name==1.2.3

# Compatible release (patch updates allowed)
pip install "package_name~=1.2.0"  # allows 1.2.x but not 1.3.0

# Minimum version
pip install "package_name>=1.2.0"

# Version range
pip install "package_name>=1.2.0,<2.0.0"

# Latest version
pip install package_name
```

### Update dependencies

```bash
# Update a single package to latest version
pip install --upgrade package_name

# Update all packages (use with caution)
pip list --outdated
pip install --upgrade package1 package2 package3

# Update packages from requirements file
pip install --upgrade -r requirements.txt
```

## 📋 Requirements Management

### Generate requirements file

```bash
# Generate requirements.txt from current environment
pip freeze > requirements.txt

# Generate requirements.txt without version pinning
pip freeze | sed 's/==.*//' > requirements.txt

# Show outdated packages
pip list --outdated
```

### Requirements file format

```text
# requirements.txt examples
package_name==1.2.3          # Exact version
package_name~=1.2.0          # Compatible release
package_name>=1.2.0          # Minimum version
package_name>=1.2.0,<2.0.0   # Version range

# Development dependencies (requirements-dev.txt)
pytest>=6.0.0
coverage>=5.0.0
black>=21.0.0
```

## 🏗️ Virtual Environment Management

### Create and activate virtual environment

```bash
# Create virtual environment
python -m venv venv
python3 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Deactivate virtual environment
deactivate
```

### Virtual environment with specific Python version

```bash
# Create with specific Python version
python3.10 -m venv venv310
python3.11 -m venv venv311

# Using virtualenv (if installed)
virtualenv -p python3.12 venv312
```

## 🔍 Package Information

### Check installed packages

```bash
# List all installed packages
pip list

# List installed packages in requirements format
pip freeze

# Show package information
pip show package_name

# Check package dependencies
pip show package_name | grep Requires
```

### Package search and verification

```bash
# Search for packages (deprecated, use PyPI website instead)
pip search package_name  # Note: This command is disabled

# Check if package is installed
pip show package_name

# Verify installed packages have compatible dependencies
pip check
```

## 🧹 Cleanup and Maintenance

### Uninstall packages

```bash
# Uninstall a package
pip uninstall package_name

# Uninstall multiple packages
pip uninstall package1 package2

# Uninstall packages from requirements file
pip uninstall -r requirements.txt
```

### Cache management

```bash
# Clear pip cache
pip cache purge

# Show cache information
pip cache info

# List cache contents
pip cache list
```

## 🚀 Basic Python Project Setup

### Project initialization

```bash
# Create project directory
mkdir my_python_project
cd my_python_project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Linux/Mac

# Create basic project structure
mkdir src tests docs
touch README.md requirements.txt requirements-dev.txt .gitignore

# Install common development tools
pip install pytest black flake8 coverage
pip freeze > requirements-dev.txt
```

### Common project files

```bash
# .gitignore for Python projects
echo "venv/
__pycache__/
*.pyc
*.pyo
*.egg-info/
.coverage
htmlcov/
.pytest_cache/" > .gitignore

# Basic setup.py structure
touch setup.py
```

## 🛠️ Troubleshooting

### Common issues and solutions

```bash
# Permission errors (use virtual environment instead)
pip install --user package_name

# SSL certificate errors
pip install --trusted-host pypi.org --trusted-host pypi.python.org package_name

# Upgrade pip itself
pip install --upgrade pip
python -m pip install --upgrade pip

# Force reinstall
pip install --force-reinstall package_name

# Install without cache
pip install --no-cache-dir package_name

# Verbose output for debugging
pip install -v package_name
```

### Environment debugging

```bash
# Check Python and pip versions
python --version
pip --version

# Check Python path
python -c "import sys; print(sys.path)"

# Check site-packages location
python -c "import site; print(site.getsitepackages())"

# Check if in virtual environment
python -c "import sys; print(sys.prefix != sys.base_prefix)"
```

## 📚 Additional Resources

- [pip documentation](https://pip.pypa.io/)
- [Python Virtual Environments Guide](https://docs.python.org/3/tutorial/venv.html)
- [PyPI - Python Package Index](https://pypi.org/)
- [Requirements File Format](https://pip.pypa.io/en/stable/reference/requirements-file-format/)