# AWESPA - Airborne Wind Energy System Performance Assessment

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://awegroup.github.io/AWESPA/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A modular Python toolchain for assessing Airborne Wind Energy (AWE) system performance using wind profile clustering, physics-based power estimation models, and Annual Energy Production (AEP) calculation.

## Overview

AWESPA provides a complete, three-step pipeline for AWE system performance analysis:

1. **Wind module** – Process ERA5 (or other) wind data to extract representative wind profiles via clustering.
2. **Power module** – Compute power curves for each wind profile cluster using a physics-based power model.
3. **Pipeline module** – Which combines the other modules for example to calculate AEP.

### Design philosophy

All tools are installed as a Python package and can be used as a library or through the provided runnable scripts. Each module is built around an Abstract Base Class (ABC) so that different implementations (e.g. different power models) share the same interface. Swapping in a new model only requires changing the class you instantiate — the rest of the pipeline stays the same.

All configuration is stored in YAML files, making analyses easy to reproduce and share. The inter-module data format follows the [awesIO](https://github.com/awegroup/awesIO) standard, so the output of one step is directly readable by the next.

### Reason for development
While there are existing tools for AWE performance assessment, they often lack modularity, are not open-source, or require significant effort to set up and run. AWESPA aims to fill this gap by providing a user-friendly, flexible, and extensible toolchain that can be easily adopted by researchers and practitioners in the AWE community.

## Project Structure

```
AWESPA/
├── config/                    # YAML configuration files
│   └── example/               # Ready-to-run example configurations
├── data/                      # Input wind data (ERA5 NetCDF files)
├── results/                   # AEP results, power curves, and plots
├── scripts/                   # Runnable analysis scripts
│   ├── run_wind_clustering.py
│   ├── run_luchsinger.py
│   └── run_inertiafree_qsm.py
├── src/awespa/                # Package source code
│   ├── wind/                  # Wind module (base class + ERA5 clustering wrapper)
│   ├── power/                 # Power module (base class + model wrappers)
│   └── pipeline/              # AEP pipeline
├── tests/                     # Test suite
└── docs/                      # Sphinx documentation
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip
- Git (required to fetch the GitHub-hosted dependencies)

### Option A — Install as a library (recommended for most users)

If you want to use AWESPA in your own project without cloning this repository, install it directly from GitHub:

```bash
pip install git+https://github.com/jbredael/AWESPA.git
```

After installation you can import AWESPA in any Python environment:

```python
from awespa.wind.clustering import WindProfileClusteringModel
from awespa.power.luchsinger_power import LuchsingerPowerModel
from awespa.pipeline.aep import calculate_aep
```

You will still need to provide your own configuration YAML files and wind data.
The example configuration files in `config/example/` of this repository can serve as a starting point.

### Option B — Clone the repository (for running the example scripts or contributing)

1. Clone the repository:
    ```bash
    git clone https://github.com/jbredael/AWESPA.git
    cd AWESPA
    ```

2. Create and activate a virtual environment:

    Linux / macOS:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

    Windows (PowerShell):
    ```bash
    python -m venv venv
    .\venv\Scripts\Activate
    ```

3. Install the package:

    For users (run the example scripts):
    ```bash
    pip install .
    ```

    For developers (editable install with dev tools):
    ```bash
    pip install -e .[dev]
    ```

4. To deactivate the virtual environment when you are done:
    ```bash
    deactivate
    ```

> **Note:** All physics-based dependencies (`inertiafree-qsm`, `power-luchsinger`, `wind-profile-clustering`) are fetched automatically from GitHub during `pip install`. Git must be available on your `PATH`.

## Usage

### Imports

```python

# Module-level imports
from awespa.wind.clustering import WindProfileClusteringModel
from awespa.power.luchsinger_power import LuchsingerPowerModel
from awespa.power.inertiafree_qsm_power import InertiaFreeQSMPowerModel
from awespa.pipeline.aep import calculate_aep
```

### Running the example scripts

Each script uses the configuration files in `config/example/` and writes output to `results/example/`.

**Step 1 – Wind profile clustering:**
```bash
python scripts/run_wind_clustering.py
```

**Step 2 – Power curve generation (Luchsinger model):**
```bash
python scripts/run_luchsinger.py
```

**OR (Inertia-Free QSM):**
```bash
python scripts/run_inertiafree_qsm.py
```

### Complete pipeline example

```python
from pathlib import Path
from awespa.wind.clustering import WindProfileClusteringModel
from awespa.power.luchsinger_power import LuchsingerPowerModel
from awespa.pipeline.aep import calculate_aep

CONFIG = Path("config/example")
RESULTS = Path("results/example")
RESULTS.mkdir(parents=True, exist_ok=True)

# --- Step 1: Wind profile clustering ---
wind_model = WindProfileClusteringModel()
wind_model.load_configuration(CONFIG / "wind_clustering_settings.yml")
wind_model.cluster(
    dataPath=Path("data/wind_data/era5"),
    outputPath=RESULTS / "wind_resource.yml",
    verbose=True,
    showplot=False,
    saveplot=True,
)

# --- Step 2: Power curve generation ---
power_model = LuchsingerPowerModel()
power_model.load_configuration(
    system_path=CONFIG / "tudelft V3_25.yml",
    simulation_settings_path=CONFIG / "luchsinger_settings.yml",
    wind_resource_path=RESULTS / "wind_resource.yml",
)
power_model.compute_power_curves(
    output_path=RESULTS / "power_curves.yml",
    verbose=True,
    showplot=False,
    saveplot=True,
)

# --- Step 3: AEP calculation ---
aep_results = calculate_aep(
    power_curve_path=RESULTS / "power_curves.yml",
    wind_resource_path=RESULTS / "wind_resource.yml",
    output_path=RESULTS / "aep_results.yml",
    plot=True,
    plot_output_dir=RESULTS / "plots",
)
print(aep_results['annual_energy_production']["total"])
```

## Configuration files

Each step is controlled by one or more YAML files. Example files are provided in `config/example/`:

| File | Used by | Purpose |
|------|---------|---------|
| `wind_clustering_settings.yml` | Wind module | Clustering parameters, data source, location |
| `tudelft V3_25.yml` | Power module | System parameters (wing, tether, ground station) in awesIO format |
| `luchsinger_settings.yml` | Power module | Luchsinger simulation settings |
| `inertiafree-qsm_settings.yml` | Power module | Inertia-Free QSM simulation settings |
| `wind_resource.yml` | Power module, Pipeline | Output of the wind module; wind profiles and probability matrix |
| `power_curves.yml` | Pipeline | Output of the power module; power curves for each profile |

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change. Please make sure to update tests as appropriate.

See [README_dev.md](README_dev.md) for detailed development guidelines.

## License

MIT License — Copyright (c) 2024 Airborne Wind Energy Research Group, TU Delft

Technische Universiteit Delft hereby disclaims all copyright interest in the program "AWESPA" (Airborne Wind Energy System Performance Assessment Toolchain) written by the Author(s).

Prof.dr. H.G.C. (Henri) Werij, Dean of Aerospace Engineering

## Documentation

- [**AWESPA Documentation**](https://awegroup.github.io/AWESPA/) - Getting started guide and API reference
- [AWE Group | Developer Guide](https://awegroup.github.io/developer-guide/)
- [AWESPA GitHub Repository](https://github.com/awegroup/AWESPA)


