LuchsingerPowerModel
====================

The ``LuchsingerPowerModel`` wraps the
`power-luchsinger <https://github.com/awegroup/LuchsingerPowerModel>`_
package. The underlying model is an energy-balance model for pumping-cycle
AWE systems originally proposed by Luchsinger (2013). It analytically
evaluates the cycle power for a given wind shear profile by splitting the
pumping cycle into a reel-out (traction) and a reel-in (retraction) phase.

The wrapper maps three awesIO configuration files to the underlying
``PowerModel`` constructor and exposes the AWESPA standard interface.

Wrapper
-------------

.. autoclass:: awespa.power.luchsinger_power.LuchsingerPowerModel
   :members:
   :undoc-members:
   :show-inheritance:


Configuration files
-------------------

``load_configuration`` expects three YAML files:

``system_path``
    System configuration in awesIO format (wing area, nominal tether force,
    nominal generator power, cut-in / cut-out wind speeds, etc.).

``simulation_settings_path``
    Simulation settings controlling the operational envelope, aerodynamic
    coefficients, and atmosphere parameters.

``wind_resource_path``
    Output of the wind module — altitude profiles, cluster shapes, and the
    wind speed probability matrix.


Simulation settings
~~~~~~~~~~~~~~~~~~~

An annotated example is shown below
(see ``config/example/luchsinger_settings.yml``):

.. code-block:: yaml

   settings:
     model: luchsinger_original        # luchsinger_original | luchsinger_extended_const_lod_in

     cut_in_wind_speed_m_s: 4.0        # Cut-in wind speed [m/s]
     cut_out_wind_speed_m_s: 25.0      # Cut-out wind speed [m/s]

     elevation_angle_out_deg: 30.0     # Tether elevation during reel-out [deg]
     elevation_angle_in_deg: 45.0      # Reel-in angle [deg] (luchsinger_original only)

     num_points: 250                   # Wind speed points for power curve

     minimum_tether_length_m: 100.0    # Minimum tether length [m]

     air_density_kg_m3: 1.225          # Air density [kg/m³]

     lift_coefficient_reel_out: 0.63
     drag_coefficient_reel_out: 0.14
     tether_drag_coefficient: 1.1

     lift_coefficient_reel_in: 0.4     # luchsinger_original only
     drag_coefficient_reel_in: 0.12


Usage example
-------------

.. code-block:: python

   from pathlib import Path
   from awespa.power.luchsinger_power import LuchsingerPowerModel

   model = LuchsingerPowerModel()
   model.load_configuration(
       system_path=Path("config/example/kitepower V3_20.yml"),
       simulation_settings_path=Path("config/example/luchsinger_settings.yml"),
       wind_resource_path=Path("results/example/wind_resource.yml"),
   )

   # Compute all power curves and save to YAML
   model.compute_power_curves(
       output_path=Path("results/example/power_curves.yml"),
       verbose=True,
       showplot=False,
       saveplot=True,
   )

   # Single operating point
   power_w = model.calculate_power_at_wind_speed(
       wind_speed=10.0,
       selected_profile=1,
       verbose=True,
   )
   print(f"Power at 10 m/s: {power_w / 1000:.1f} kW")

Or use the ready-made script:

.. code-block:: bash

   python scripts/run_luchsinger.py
