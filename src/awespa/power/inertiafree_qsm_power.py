"""Inertia-Free QSM power estimation wrapper for the InertiaFree-QSM package.

This wrapper adapts the Inertia-Free Quasi-Steady Model to the AWESPA
modular architecture. The underlying model accepts awesIO format configuration
files directly and supports power curve generation, while single-wind-speed
simulations can be either direct or optimized."""

import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List

from .base import PowerEstimationModel

try:
    from awesio.validator import validate as awesio_validate  # type: ignore
except ImportError:
    awesio_validate = None

try:
    from inertiafree_qsm import PowerCurveConstructor  # type: ignore
except ImportError as e:
    print(f"Import error for InertiaFree-QSM: {e}")
    PowerCurveConstructor = None


class InertiaFreeQSMPowerModel(PowerEstimationModel):
    """Wrapper for the Inertia-Free Quasi-Steady Model power curve constructor.

    This wrapper adapts the vendored InertiaFree-QSM to the AWESPA modular
    architecture. Power curves are generated from optimized cycle parameters
    per wind speed. Single-wind-speed simulations can still be run either
    directly or with optimization.

    The model requires three configuration files in awesIO format:
    - System configuration (kite, tether, ground station properties)
    - Wind resource (altitude profiles, profiles, probability matrix)
    - Simulation settings (cycle parameters, optimizer bounds, phase settings)
    """

    def __init__(self):
        """Initialize the Inertia-Free QSM power estimation model."""
        self.constructor: Optional[Any] = None
        self.systemPath: Optional[Path] = None
        self.windResourcePath: Optional[Path] = None
        self.simulationSettingsPath: Optional[Path] = None

    def load_configuration(
        self,
        system_path: Path,
        simulation_settings_path: Path,
        wind_resource_path: Path = None,
        validate: bool = True,
    ) -> None:
        """Load power model configuration from YAML files.

        Creates a ``PowerCurveConstructor`` instance from the vendored
        InertiaFree-QSM package using the provided configuration files.

        Args:
            system_path (Path): Path to the system configuration YAML file
                (awesIO format with wing, tether, ground_station components).
            simulation_settings_path (Path): Path to simulation settings YAML
                file containing cycle, phase, optimizer, and solver parameters.
            wind_resource_path (Path): Path to wind resource YAML file
                containing altitude profiles, profiles, and probability matrix.
            validate (bool): If True, validate configuration files using
                the awesIO validator. Defaults to True.

        Raises:
            ImportError: If the vendored PowerCurveConstructor cannot be imported.
            FileNotFoundError: If any required file does not exist.
        """
        if PowerCurveConstructor is None:
            raise ImportError(
                "PowerCurveConstructor could not be imported from InertiaFree-QSM"
            )

        self.systemPath = Path(system_path)
        self.simulationSettingsPath = Path(simulation_settings_path)
        self.windResourcePath = Path(wind_resource_path) if wind_resource_path else None

        # Validate that required files exist
        for label, path in [
            ("System config", self.systemPath),
            ("Simulation settings", self.simulationSettingsPath),
        ]:
            if not path.exists():
                raise FileNotFoundError(f"{label} file not found: {path}")

        if self.windResourcePath is not None and not self.windResourcePath.exists():
            raise FileNotFoundError(
                f"Wind resource file not found: {self.windResourcePath}"
            )

        # Validate configuration files
        if validate:
            if awesio_validate is None:
                raise ImportError("awesIO validator not available")
            awesio_validate(input=self.systemPath)
            if self.windResourcePath is not None:
                awesio_validate(input=self.windResourcePath)
            print("Configuration files validated.")

        # Create the PowerCurveConstructor
        self.constructor = PowerCurveConstructor(
            system_config_path=self.systemPath,
            wind_resource_path=self.windResourcePath,
            simulation_settings_path=self.simulationSettingsPath,
        )

        print(f"Loaded InertiaFree-QSM configuration:")
        self.constructor.print_summary()

    def compute_power_curves(
        self,
        wind_speeds: Optional[np.ndarray] = None,
        profile_ids: Optional[List[int]] = None,
        output_path: Path = None,
        verbose: bool = True,
        showplot: bool = False,
        saveplot: bool = False,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Compute power curves.

        Args:
            output_path (Path): Path where power curve YAML will be written.
                If None, no export is performed. Defaults to None.
            wind_speeds (np.ndarray): Custom wind speeds to evaluate [m/s].
                If None, uses wind speeds from simulation settings.
                Defaults to None.
            profile_ids (list): profile IDs (1-indexed) to calculate. If None,
                calculates all profiles. Defaults to None.
            verbose (bool): Whether to print progress output.
                Defaults to True.
            showplot (bool): Whether to display plots after generation.
                Defaults to False.
            saveplot (bool): Whether to save plots to file. Requires
                ``output_path``. Defaults to False.
            validate (bool): If True, validate the output YAML file using
                the awesIO validator. Defaults to True.

        Returns:
            dict: Power curve data in awesIO format.

        Raises:
            ValueError: If model is not initialized.
        """
        if self.constructor is None:
            raise ValueError(
                "Power model not initialized. Call load_configuration first."
            )

        print("Computing power curves...")
        data = self.constructor.generate_power_curves(
            wind_speeds=wind_speeds,
            profile_ids=profile_ids,
            output_path=output_path,
            verbose=verbose,
            show_plot=showplot,
            save_plot=saveplot,
        )

        if output_path is not None:
            print(f"Power curves exported to: {output_path}")
            if validate:
                if awesio_validate is None:
                    raise ImportError("awesIO validator not available")
                awesio_validate(input=output_path)
                if verbose:
                    print(f"Output validated: {output_path}")

        return data

    def calculate_power_at_wind_speed(
        self,
        wind_speed: float,
        method: str = "direct",
        profile_id: int = 1,
        output_path: Path = None,
        verbose: bool = True,
        showplot: bool = False,
        saveplot: bool = False,
        validate: bool = True,
    ) -> float:
        """Calculate power output at a single wind speed.

        Simulates a single pumping cycle at the given wind speed and returns
        the average cycle power.

        Args:
            wind_speed (float): Wind speed at reference height [m/s].
            method (str): Simulation method, either ``'direct'`` or
                ``'optimization'``. Defaults to ``'direct'``.
            profile_id (int): profile ID (1-indexed) for wind profile
                selection. Defaults to 1.
            output_path (Path): Path where results YAML will be written.
                If None, no export is performed. Defaults to None.
            verbose (bool): Whether to print verbose output.
                Defaults to True.
            showplot (bool): Whether to display cycle detail plot.
                Defaults to False.
            saveplot (bool): Whether to save cycle detail plot. Requires
                ``output_path``. Defaults to False.
            validate (bool): If True, validate the output YAML file using
                the awesIO validator. Defaults to True.

        Returns:
            float: Average cycle power output [W].

        Raises:
            ValueError: If model is not initialized.
        """
        if self.constructor is None:
            raise ValueError(
                "Power model not initialized. Call load_configuration first."
            )

        result = self.constructor.simulate_single_wind_speed(
            wind_speed=wind_speed,
            profile_id=profile_id,
            method=method,
            output_path=output_path,
            verbose=verbose,
            show_plot=showplot,
            save_plot=saveplot,
        )

        # Extract average cycle power from result
        powerCurves = result.get("power_curves", [])
        if powerCurves:
            windSpeedData = powerCurves[0].get("wind_speed_data", [])
            if windSpeedData:
                power = windSpeedData[0]["performance"]["power"][
                    "average_cycle_power"
                ]
                if verbose:
                    print(
                        f"\nPower at {wind_speed:.1f} m/s ({method}): "
                        f"{power:.2f} W ({power / 1000:.2f} kW)"
                    )
                return float(power)

        print(f"Warning: Could not extract power from result at {wind_speed:.1f} m/s")
        return 0.0
