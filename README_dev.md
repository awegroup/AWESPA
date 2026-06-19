# AWESPA Developer Guide

Welcome to the AWESPA development guide. This document contains instructions for developers working on the AWESPA project.

## Introduction

AWESPA (Airborne Wind Energy System Performance Assessment) is a modular Python toolchain with three main components:
- **Wind Module**: Wind profile clustering from ERA5 data
- **Power Module**: Physics-based power estimation models
- **Pipeline Module**: Has different functions that combine the different modules in AWESPA or do calculation with the exported data like AEP calculation. This module does not refer to external code.

## Project Architecture

```
src/awespa/
├── __init__.py              # Package initialization and exports
├── wind/                    # Wind modeling components
│   ├── base.py              # WindProfileModel ABC
│   └── clustering.py        # WindProfileClusteringModel implementation
├── power/                   # Power estimation models
│   ├── base.py                      # PowerEstimationModel ABC
│   ├── luchsinger_power.py          # Luchsinger power model
│   └── inertiafree_qsm_power.py     # Inertia-Free QSM power model
├── pipeline/                # Pipeline orchestration
│   └── aep.py               # AEP calculation functions
```



## Naming Conventions

| Element       | Convention         | Examples                            |
|---------------|-------------------|-------------------------------------|
| Functions     | snake_case        | `compute_force`, `calculate_power`  |
| Variables     | mixedCase         | `windSpeed`, `turbinePower`         |
| Classes       | CamelCase         | `WindModel`, `PowerCalculator`      |
| Methods       | snake_case        | `get_values`, `update_state`        |
| Constants     | UPPER_SNAKE_CASE  | `AIR_DENSITY`, `MAX_ITERATIONS`     |
| Modules       | snake_case        | `utilities.py`, `aero_model.py`     |
| Packages      | lowercase         | `simulation`, `windanalysis`        |
| Booleans      | is_ prefix or UPPER| `is_valid`, `IS_ACTIVE`            |

## Docstring Conventions

Use Google-style docstrings:

```python
def calculate_power(wind_speed: float, air_density: float = 1.225) -> float:
    """Calculate power output at given wind speed.

    Computes mechanical power using simplified physics model.

    Args:
        wind_speed: Wind speed in m/s.
        air_density: Air density in kg/m³. Defaults to 1.225.

    Raises:
        ValueError: If wind_speed is negative.

    Returns:
        Power output in Watts.
    """
    if wind_speed < 0:
        raise ValueError("Wind speed cannot be negative")
    return 0.5 * air_density * wind_speed ** 3
```

## Setting Up Your Development Environment

1. Clone the repository:
    ```bash
    git clone https://github.com/awegroup/AWESPA.git
    cd AWESPA
    ```

2. Create and activate a virtual environment:
    ```bash
    # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate
    
    # Windows (PowerShell)
    python -m venv venv
    .\venv\Scripts\Activate
    ```

3. Install in development mode:
    ```bash
    pip install -e .[dev]
    ```

4. Verify installation:
    ```bash
    python -c "import awespa; print(awespa.__version__)"
    ```

## Workflow for Implementing New Features

1. **Setup Environment**
    ```bash
    cd AWESPA
    # Remove old venv if necessary
    python -m venv venv
    source venv/bin/activate  # or .\venv\Scripts\Activate on Windows
    pip install -e .[dev]
    ```

2. **Create Issue on GitHub**
   - Describe the feature or bug fix
   - Assign labels and milestone

3. **Create Feature Branch**
    ```bash
    git checkout -b feature/<issue-number>-<short-description>
    ```

4. **Implement Your Feature**
   - Follow naming conventions (see below)
   - Add/update docstrings
   - Write tests

5. **Verify with Tests**
    ```bash
    pytest
    pytest --cov=awespa
    ```

6. **Commit and Push**
    ```bash
    git add .
    git commit -m "#<issue-number> <descriptive commit message>"
    git push -u origin feature/<issue-number>-<short-description>
    ```

7. **Create Pull Request**
   - Open PR on GitHub
   - Link to the issue
   - Request review

8. **After Merge**
    ```bash
    git fetch --prune
    git checkout main
    git pull
    git branch -d feature/<issue-number>-<short-description>
    ```


## Testing Guidelines

### Test Structure
```
tests/
├── conftest.py              # Shared fixtures
├── test_wind_clustering.py  # Wind module tests
├── test_power_models.py     # Power module tests
└── test_aep_pipeline.py     # Pipeline tests
```

### Test Naming
- Test files: `test_<module>.py`
- Test functions: `test_<function>_<scenario>`

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=awespa --cov-report=html

# Run specific test file
pytest tests/test_power_models.py

# Run specific test function
pytest tests/test_power_models.py::test_luchsinger_power_curve
```

### Test Requirements
- Target ~70% code coverage
- Tests should be independent
- Tests should run quickly
- Mock external dependencies when appropriate

## Packaging with pyproject.toml

### Key Configuration Fields

```toml
[project]
name = "awespa"
version = "1.0.0"
description = "Airborne Wind Energy System Performance Assessment Toolchain"
requires-python = ">=3.8"

dependencies = [
    "numpy",
    "pandas>=1.5.3",
    "matplotlib>=3.7.1",
    "pyyaml",
    "scipy",
    "scikit-learn",
    "xarray",
    "netCDF4",
    "inertiafree-qsm @ git+https://github.com/awegroup/InertiaFree-QSM.git",
    "power-luchsinger @ git+https://github.com/awegroup/LuchsingerPowerModel.git",
    "wind-profile-clustering @ git+https://github.com/awegroup/wind-profile-clustering.git",
    "awesio @ git+https://github.com/awegroup/awesIO.git"
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "black", "flake8", "isort", "mypy"]
docs = ["sphinx>=5.0", "furo", "myst-parser", "sphinx-autodoc-typehints"]
```

### Using the Package

```python
# Import the main package
import awespa

# Import specific components
from awespa import WindProfileClusteringModel, calculate_aep
from awespa.power import LuchsingerPowerModel, InertiaFreeQSMPowerModel

# Access version
print(awespa.__version__)
```

## Adding New Power Models

To add a new power estimation model:

1. Create a new file in `src/awespa/power/` (e.g., `my_power_model.py`)

2. Inherit from the abstract base class:
    ```python
    from awespa.power.base import PowerEstimationModel
    
    class MyPowerModel(PowerEstimationModel):
        def load_configuration(self, system_path, simulation_settings_path=None,
                               operational_constraints_path=None,
                               wind_resource_path=None):
            # Implementation
            pass

        def compute_power_curves(self, output_path, verbose=False,
                                 showplot=False, saveplot=False, plot_path=None):
            # Implementation
            pass

        def calculate_power_at_wind_speed(self, wind_speed, output_path=None,
                                          verbose=False, showplot=False,
                                          saveplot=False, plot_path=None):
            # Implementation
            pass
    ```

3. Export in `src/awespa/power/__init__.py`:
    ```python
    from .my_power_model import MyPowerModel
    __all__ = [..., 'MyPowerModel']
    ```

4. Add tests in `tests/test_power_models.py`

## Documentation

### Building Documentation

```bash
pip install -e .[docs]
cd docs
.\make html
```

Documentation is built using Sphinx with the Furo theme.

## Resources

- [**AWESPA Documentation**](https://awegroup.github.io/AWESPA/) - Getting started guide and API reference
- [AWE Group Developer Guide](https://awegroup.github.io/developer-guide/)
- [AWESPA Repository](https://github.com/awegroup/AWESPA)
- [Python Packaging Guide](https://packaging.python.org/)
- [pytest Documentation](https://docs.pytest.org/)
