Power Module
============

The power module computes **power curves** — the electrical power output of
an AWE system as a function of wind speed — for each wind profile cluster
produced by the wind module. The resulting power curve file (in awesIO YAML
format) is the direct input for the AEP pipeline and a good reference for
performance analysis.

Architecture
------------

The module is built around an Abstract Base Class that defines the interface
every power model must implement. Concrete implementations are thin wrappers
around external physics-based packages.

.. code-block:: text

   PowerEstimationModel  (abstract base class)
   ├── LuchsingerPowerModel       (wraps power-luchsinger)
   └── InertiaFreeQSMPowerModel   (wraps inertiafree-qsm)

Swapping models requires only changing the class that is instantiated — the
rest of the pipeline (configuration loading, output format, AEP calculation)
remains identical.

Base Class — ``PowerEstimationModel``
--------------------------------------

.. autoclass:: awespa.power.base.PowerEstimationModel
   :members:
   :undoc-members:
   :show-inheritance:

Every implementation must provide three methods:

``load_configuration(system_path, simulation_settings_path, ..., validate=True)``
    Load all model settings from awesIO-format YAML files. Validates that
    required files exist and creates the underlying model object. When
    ``validate`` is True, input configuration files are checked against
    their awesIO schema.

``compute_power_curves(output_path, verbose, showplot, saveplot, plot_path, validate=True)``
    Calculate the full power curve for every wind profile cluster, optionally
    export the result to YAML, and optionally show / save plots. When
    ``validate`` is True, the output YAML is validated against the awesIO
    power curves schema.

``calculate_power_at_wind_speed(wind_speed, output_path, verbose, showplot, saveplot, validate=True)``
    Simulate a single operating point (one wind speed) and return the
    average cycle power in watts. When ``validate`` is True, the output
    YAML is validated against the awesIO schema.

Output format
-------------

Both models write a YAML file in awesIO format with the following top-level
keys:

* ``metadata`` — system configuration and model settings (wing area, mass,
  generator efficiency, nominal power, cut-in/cut-out wind speeds, etc.)
* ``altitudes`` — altitude grid [m] at which wind profiles are defined
* ``reference_wind_speeds`` — wind speed vector [m/s] used for evaluation
* ``power_curves`` — list of per-cluster power curve dictionaries, each
  containing the profile ID, probability weight, wind profile shape,
  and power output [W], tether forces [N], timings etc at each reference wind speed
* ``time_history`` — metadata describing time-series channel outputs (including
  tether forces, power, reel speed, altitude, wind speeds at kite,
  aerodynamic forces, lift-to-drag ratio, and control angles) saved in
  the accompanying ``.npz`` binary file

This file is directly consumed by :func:`awespa.pipeline.aep.calculate_aep`.

Implementations
---------------

.. toctree::
   :maxdepth: 1

   power_luchsinger
   power_inertiafree_qsm

Output
------

The output of the power module is a YAML file in awesIO format. More info of the power_curves.yml can be found in the awesIO documentation:https://awegroup.github.io/awesIO/source/power_curves_schema.html. This file contains the representative wind profile shapes, their associated wind speed probability distributions, and cluster occurrence frequencies. This file is the shared input for all power-module models and the AEP pipeline.