InertiaFreeQSMPowerModel
========================

The ``InertiaFreeQSMPowerModel`` wraps the
`inertiafree-qsm <https://github.com/jbredael/InertiaFree-QSM>`_
package. The underlying model is an Inertia-Free Quasi-Steady Model (QSM)
that simulates the full pumping cycle with four flight phases
(traction, retraction, transitionRIO, transitionRORI). It numerically optimises the cycle 
parameters per wind speed to maximise output power using SLSQP.

Wrapper
-------------

.. autoclass:: awespa.power.inertiafree_qsm_power.InertiaFreeQSMPowerModel
   :members:
   :undoc-members:
   :show-inheritance:


Configuration files
-------------------

``load_configuration`` expects three YAML files:

``system_path``
    System configuration in awesIO format.

``simulation_settings_path``
    QSM-specific settings — aerodynamics, cycle parameters, phase settings,
    optimizer bounds, and solver tolerances.

``wind_resource_path``
    Output of the wind module.


Simulation settings
~~~~~~~~~~~~~~~~~~~

An annotated example is shown below
(see ``config/example/inertiafree-qsm_settings.yml``):

.. code-block:: yaml

   # ===== AERODYNAMIC SETTINGS =====
   aerodynamics:
     kite_lift_coefficient_reel_out: 0.63
     kite_drag_coefficient_reel_out: 0.14
     kite_lift_coefficient_reel_in: 0.4
     kite_drag_coefficient_reel_in: 0.12
     tether_drag_coefficient: 1.1

   # ===== OPTIMIZATION =====
   optimization:
     wind_speeds:
       cut_in: 3.0
       cut_out: 25.0
       n_points: 23

     optimizer:
       optimize_variables:
         reeling_speed_traction: true
         reeling_speed_retraction: true
         fraction_tether_length_traction_end: true
         fraction_tether_length_retraction_end: true
         elevation_angle_traction: true
         elevation_angle_end_trans_rori: true
       opt_phase_timestep:
         retraction: 1.5
         transition_riro: 0.05
         traction: 2.5
         transition_rori: 0.05
       max_iterations: 40
       ftol: 0.005
       eps: 1.0e-2
       finite_difference_steps:
         reeling_speed: 0.03
         tether_fraction: 0.005
         elevation_angle: 0.25
       x0: [2, -2, 0.65, 0.9, 30.0, 50.0]
       scaling: [1, 1, 1, 1, 30, 30]

     bounds:
       reeling_speed_traction_min: 0.01
       reeling_speed_traction_max: 15.0
       reeling_speed_retraction_min: -15.0
       reeling_speed_retraction_max: -0.01
       fraction_tether_length_traction_end_min: 0.8
       fraction_tether_length_traction_end_max: 0.95
       fraction_tether_length_retraction_end_min: 0.2
       fraction_tether_length_retraction_end_max: 0.8
       elevation_angle_traction_min: 30.0
       elevation_angle_traction_max: 60.0
       elevation_angle_end_trans_rori_min: 30.0
       elevation_angle_end_trans_rori_max: 80.0

     constraints:
       min_tether_length_fraction_difference: 0.1
       max_difference_elevation_angle_steps: 10.0

   # ===== CYCLE CONFIGURATION =====
   cycle:
     minimum_tether_force: 750.0
     minimum_height: 100.0
     elevation_angle_traction: [30.0, 30.0, 30.0, 30.0, 30.0]
     tether_length_end_traction: 0.95
     tether_length_end_retraction: 0.6
     include_transition_energy: true
     elevation_angle_end_trans_rori: 50.0

   # ===== PHASE SETTINGS =====
   retraction:
     control: ['reeling_speed', -2.0]
     time_step: 0.25
     azimuth_angle: 0.0
     course_angle: 180.0

   transition_riro:
     control: ['reeling_speed', 0]
     time_step: 0.05
     azimuth_angle: 0.0
     course_angle: 0.0

   transition_rori:
     control: ['reeling_speed', 0]
     time_step: 0.05
     azimuth_angle: 0.0
     course_angle: 180.0

   traction:
     control: ['reeling_speed', 2.0]
     time_step: 0.25
     azimuth_angle: 11.5
     course_angle: 93.0

   # ===== STEADY STATE SOLVER =====
   steady_state:
     max_iterations: 250
     convergence_tolerance: 1.0e-3

   # ===== PHASE SOLVER =====
   phase_solver:
     max_time_points: 5000


Usage example
-------------

.. code-block:: python

   from pathlib import Path
   from awespa.power.inertiafree_qsm_power import InertiaFreeQSMPowerModel

   model = InertiaFreeQSMPowerModel()
   model.load_configuration(
       system_path=Path("config/example/tudelft V3_25.yml"),
       simulation_settings_path=Path("config/example/inertiafree-qsm_settings.yml"),
       wind_resource_path=Path("config/example/wind_resource.yml"),
   )

   # Compute power curves
   model.compute_power_curves(
       output_path=Path("results/example/power_curves_qsm.yml"),
       verbose=True,
       showplot=True,
       saveplot=True,
   )

   # Single operating point with a direct simulation, meaning that the parameters are not optimized but taken directly from the settings file. This is much faster than the default method, which runs an optimization loop to find the optimal parameters at each wind speed.
   # Useful for testing
   power_w = model.calculate_power_at_wind_speed(
       wind_speed=10.0,
       method="direct",
       profile_id=1,
       verbose=True,
   )
   print(f"Power at 10 m/s: {power_w / 1000:.1f} kW - DIRECT")

   # Single operating point with an optimization-based simulation, meaning that the parameters are optimized to find the optimal settings for each wind speed.
   power_w = model.calculate_power_at_wind_speed(
       wind_speed=10.0,
       method="optimization",
       profile_id=1,
       verbose=True,
   )
   print(f"Power at 10 m/s: {power_w / 1000:.1f} kW - OPTIMIZATION")

Or use the ready-made script:

.. code-block:: bash

   python scripts/run_inertiafree_qsm.py
