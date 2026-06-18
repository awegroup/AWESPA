======
AWESPA
======

**Airborne Wind Energy System Performance Assessment Toolchain**

A modular Python toolchain for assessing Airborne Wind Energy (AWE) system
performance using wind profile clustering, physics-based power estimation
models, and Annual Energy Production (AEP) calculation.

Getting Started
===============

Overview
--------

AWESPA provides a complete, three-step pipeline:

1. **Wind module** — Process wind data to extract representative wind profiles
   via clustering. See :doc:`wind_module`.
2. **Power module** — Compute power curves for each wind profile cluster using
   a physics-based model. See :doc:`power_module`.
3. **Pipeline** — Scripts which are not referring to an external library, this is a helper module that already contains for example the AEP calculation.

All inter-module data is exchanged through the awesIO-format YAML files as much as possible, so the
output of one step is directly readable by the next. Each module follows an
Abstract Base Class interface, making it straightforward to swap in other models of the same module. The setting files for each module are also YAML-based, ensuring that the entire analysis is reproducible from a single configuration file. But these configuration files are not in awesIO format.

Project Structure
-----------------

.. code-block:: text

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
   │   ├── wind/                  # Wind module
   │   ├── power/                 # Power module
   │   └── pipeline/              # Pipline scripts and utilities
   ├── tests/                     # Test suite
   └── docs/                      # This documentation

Installation
------------

Prerequisites
~~~~~~~~~~~~~

* Python 3.8 or higher
* pip
* Git (required for pip to fetch the GitHub-hosted dependencies)

Installation Instructions
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Clone the repository:

   .. code-block:: bash

      git clone https://github.com/awegroup/AWESPA.git
      cd AWESPA

2. Create a virtual environment:

   **Linux / macOS:**

   .. code-block:: bash

      python3 -m venv venv
      source venv/bin/activate

   **Windows (PowerShell):**

   .. code-block:: bash

      python -m venv venv
      .\venv\Scripts\Activate

3. Install the package:

   **For users:**

   .. code-block:: bash

      pip install .

   **For developers (editable install with dev tools):**

   .. code-block:: bash

      pip install -e .[dev]

4. To deactivate the virtual environment:

   .. code-block:: bash

      deactivate

.. note::

   The three dependencies (``inertiafree-qsm``,
   ``power-luchsinger``, ``wind-profile-clustering``) are fetched
   automatically from GitHub during ``pip install``. Git must be available
   on your ``PATH``.

Usage
-----

Running the example scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each script uses the configuration files in ``config/example/`` and writes
output to ``results/example/``.

**Step 1 — Wind profile clustering:**

.. code-block:: bash

   python scripts/run_wind_clustering.py

**Step 2 — Power curve generation (Luchsinger model):**

.. code-block:: bash

   python scripts/run_luchsinger.py

**Step 2 (alternative) — Power curve generation (Inertia-Free QSM):**

.. code-block:: bash

   python scripts/run_inertiafree_qsm.py

Complete pipeline example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

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

Contributing
============

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change. Please make sure to update tests
as appropriate.

See the `Developer Guide <https://github.com/awegroup/AWESPA/blob/main/README_dev.md>`_
for detailed development guidelines.

Resources
=========

* `GitHub Repository <https://github.com/awegroup/AWESPA>`_
* `AWE Group Developer Guide <https://awegroup.github.io/developer-guide/>`_

License
=======

MIT License — Copyright (c) 2024 Airborne Wind Energy Research Group, TU Delft

API Reference
=============

.. toctree::
   :maxdepth: 2

   general_module
   wind_module
   power_module

Indices and Tables
==================

* :ref:`genindex`
* :ref:`search`
