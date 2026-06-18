Wind Module
===========

The wind module is responsible for processing raw wind data and producing a
**wind resource file** — a YAML file (in awesIO format) that contains the
representative wind profile shapes, their associated wind speed probability
distributions, and cluster occurrence frequencies. This file is the shared
input for all power-module models and the AEP pipeline.

Architecture
------------

The module is built around an Abstract Base Class (ABC) that defines the
interface every wind model must implement.

Abstract methods on the ``WindProfileModel`` ABC must be implemented by every wind model. Non-abstract methods define optional interfaces that implementations may override when supported (clustering, profile fitting, prescribing).

For the wind module it was difficult to define a single core functionality that all implementations must have, because different use cases may require different methods. For example, some users may only want to perform clustering, while others may want to fit profiles or prescribe analytical profiles. Therefore, we decided to make the load_configuration method the only required method for all wind models, and make the cluster, fit_profile, and prescribe_profile methods optional. This way, users can choose which functionalities they want to use based on their specific needs and data availability.

.. code-block:: text

   WindProfileModel  (abstract base class)
   └── WindProfileClusteringModel  (ERA5 / lidar / DOWA wrapper)

Base Class — ``WindProfileModel``
---------------------------------

.. autoclass:: awespa.wind.base.WindProfileModel
   :members:
   :undoc-members:
   :show-inheritance:

The base class enforces the following interface on every implementation:

``load_configuration(config_path, validate=True)``
    Load all model settings from a YAML configuration file so that the
    analysis is fully reproducible from a single file. When ``validate``
    is True, input files are checked against their awesIO schema.

``cluster(data_path, output_path, verbose, showplot, saveplot, validate=True)``
    Execute the clustering and write the wind resource YAML to
    ``output_path``. When ``validate`` is True, the output YAML is
    validated against the awesIO wind resource schema.

``fit_profile(data_path, output_path, verbose, showplot, saveplot, validate=True)``
    Fit an analytical wind profile (logarithmic or power law) to measured
    wind data and write the result to ``output_path``. When ``validate``
    is True, the output YAML is validated.

``prescribe_profile(output_path, verbose, showplot, saveplot, validate=True)``
    Build a prescribed analytical wind profile without measured data and
    write the result to ``output_path``. When ``validate`` is True, the
    output YAML is validated.

Only ``load_configuration`` is abstract — implementations must provide it.
The remaining methods are optional; a wind model that only performs
clustering need not implement ``fit_profile`` or ``prescribe_profile``.

Implementations
---------------

.. toctree::
   :maxdepth: 1

   wind_clustering

Output
------

The output of the windmodule is a YAML file in awesIO format. More info of the wind_resource.yml can be found in the awesIO documentation:https://awegroup.github.io/awesIO/source/wind_resource_schema.html. This file contains the representative wind profile shapes, their associated wind speed probability distributions, and cluster occurrence frequencies. This file is the shared input for all power-module models and the AEP pipeline.