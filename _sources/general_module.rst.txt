General Module Structure
========================

This page describes the general structure and conventions of AWESPA modules.
Each module performs a specific step in the AWE performance assessment process
and can be used independently or combined in a pipeline.


Configuration: ``load_configuration``
--------------------------------------

All module classes expose a **``load_configuration``** method that accepts one
or more YAML file paths. This file contains every setting and parameter the
module needs, making analyses reproducible and easy to share.


Main Functionality
------------------

After loading its configuration each module provides methods that execute its
core task (e.g. clustering, power curve generation). Every main-functionality
method accepts the following four keyword arguments:

``outputPath``
    Path (including file name) where the output file will be written. The
    parent directory of this path is also used as the location for any saved
    plots.

``verbose``
    If ``True``, print progress and diagnostic information during execution.

``showplot``
    If ``True``, display plots interactively after execution.

``saveplot``
    If ``True``, save plots to disk in the directory derived from
    ``outputPath``.
``validate``
    If ``True``, validate the output file against the awesIO schema. This is
    enabled by default but can be disabled when experimenting or developing.

These conventions ensure a uniform interface across all modules.


Module Input / Output Overview
------------------------------

The table below summarises the files consumed and produced by each module and
whether they follow the awesIO standard.

.. list-table::
   :header-rows: 1
   :widths: 25 40 35

   * - Module
     - Input files / data
     - Output files / data
   * - ``WindProfileClusteringModel``
     - | Raw wind data (NetCDF for ERA5, lidar, or DOWA)
       | wind_clustering_settings (YAML, non-awesIO)
     - Wind resource file (YAML, awesIO)
   * - ``LuchsingerPowerModel``
     - | System configuration (YAML, awesIO)
       | Wind resource file (YAML, awesIO)
       | luchsinger_settings (YAML, non-awesIO)
     - | Power curves file (YAML, awesIO)
       | Time-history file (``.npz``, related to awesIO)
   * - ``InertiaFreeQSMPowerModel``
     - | System configuration (YAML, awesIO)
       | Wind resource file (YAML, awesIO)
       | qsm_settings (YAML, non-awesIO)
     - Power curves file (YAML, awesIO)


Requirements for Adding a New Module
-------------------------------------

A tool can be added as an AWESPA module when it satisfies all of the following:

1. **Relevance** -- the tool must address a step in the AWE performance
   assessment process (wind resource assessment, power estimation, farm
   modelling, economic modelling, etc.).

2. **YAML-driven execution** -- the tool must be executable through a wrapper
   whose simulation settings are provided via a YAML configuration file. This
   can be handled by the wrapper or by the underlying code, but the wrapper
   must be able to read the YAML file and forward the settings.

3. **awesIO-compliant input and output** -- the tool must read its inputs from
   user-specified paths following the awesIO standard and write its outputs to a
   user-specified path following the awesIO standard, ensuring compatibility
   with downstream modules.
   Or the wrapper must be able to take in awesIO-compliant input files, convert them to the format required by the underlying code, execute the tool, and convert the output back to awesIO format.

4. **ABC compliance** -- the wrapper must implement the abstract base class of
   the module category it belongs to (e.g. power-estimation models implement
   ``PowerEstimationModel``). This guarantees a consistent interface so users
   can swap models without changing their scripts.
