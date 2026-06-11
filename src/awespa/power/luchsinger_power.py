"""Luchsinger power estimation wrapper for the power-luchsinger package.

This wrapper adapts the Luchsinger power model to the AWESPA modular
architecture. The underlying model accepts awesIO format configuration files
directly and computes power curves using wind shear profiles from a wind resource."""

import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

from .base import PowerEstimationModel

try:
    from awesio.validator import validate as awesio_validate  # type: ignore
except ImportError:
    awesio_validate = None

try:
    from power_luchsinger.power_model import PowerModel  # type: ignore
except ImportError as e:
    print(f"Import error for LuchsingerPowerModel: {e}")
    PowerModel = None


class LuchsingerPowerModel(PowerEstimationModel):
    """Wrapper for the Luchsinger pumping kite power model.

    This wrapper adapts the vendored Luchsinger power model to the AWESPA
    modular architecture. The model requires three configuration files in
    awesIO format:

    - System configuration (kite, tether, ground station properties)
    - Wind resource (profiles, probability matrix)
    - Simulation settings (operational envelope, atmosphere parameters)
    """

    def __init__(self):
        """Initialize the Luchsinger power estimation model."""
        self.model: Optional[Any] = None
        self.systemPath: Optional[Path] = None
        self.windResourcePath: Optional[Path] = None
        self.simulationSettingsPath: Optional[Path] = None

    def load_configuration(
        self,
        system_path: Path,
        simulation_settings_path: Path,
        operational_constraints_path: Path = None,
        wind_resource_path: Path = None,
        validate: bool = True,
    ) -> None:
        """Load power model configuration from YAML files.

        Creates a ``PowerModel`` instance from the vendored Luchsinger package
        using the provided configuration files.

        Args:
            system_path (Path): Path to the system configuration YAML file
                (awesIO format with wing, tether, ground_station components).
            simulation_settings_path (Path): Path to simulation settings YAML
                file containing operational envelope and atmosphere parameters.
            operational_constraints_path (Path): Not used by this model.
                Defaults to None.
            wind_resource_path (Path): Path to wind resource YAML file
                containing profiles and probability matrix.
            validate (bool): If True, validate configuration files using
                the awesIO validator. Defaults to True.

        Raises:
            ImportError: If the vendored PowerModel cannot be imported.
            FileNotFoundError: If any required file does not exist.
        """
        if PowerModel is None:
            raise ImportError(
                "PowerModel could not be imported from LuchsingerPowerModel"
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

        if self.windResourcePath is None:
            raise ValueError(
                "wind_resource_path is required for the Luchsinger model."
            )
        if not self.windResourcePath.exists():
            raise FileNotFoundError(
                f"Wind resource file not found: {self.windResourcePath}"
            )

        # Create the PowerModel (loads all config internally)
        self.model = PowerModel(
            system_config_path=self.systemPath,
            wind_resource_path=self.windResourcePath,
            simulation_settings_path=self.simulationSettingsPath,
            validate_file=validate,
        )

        print(f"Loaded Luchsinger configuration:")
        print(f"  Wing area:              {self.model.wingArea:.1f} m\u00b2")
        print(f"  Nominal tether force:   {self.model.nominalTetherForce:.0f} N")
        print(f"  Nominal generator power:{self.model.nominalGeneratorPower / 1000:.1f} kW")
        print(f"  Cut-in wind speed:      {self.model.cutInWindSpeed:.1f} m/s")
        print(f"  Cut-out wind speed:     {self.model.cutOutWindSpeed:.1f} m/s")
        print(
            f"  Number of wind profiles:"
            f" {self.model.wind_resource['n_profiles']}"
        )

    def compute_power_curves(
        self,
        wind_speeds: Optional[np.ndarray] = None,
        selected_profiles: list = None,
        output_path: Path = None,
        verbose: bool = True,
        showplot: bool = False,
        saveplot: bool = False,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Compute power curves for all wind shear profiles and optionally export.

        Args:
            output_path (Path): Path where power curve YAML will be written.
                If None, no export is performed. Defaults to None.
            wind_speeds (np.ndarray): Custom wind speeds to evaluate [m/s].
                If None, uses a linearly-spaced array between cut-in and
                cut-out from simulation settings. Defaults to None.
            verbose (bool): Whether to print a summary after generation.
                Defaults to True.
            showplot (bool): Whether to display plots after generation.
                Defaults to False.
            saveplot (bool): Whether to save plots to file alongside the
                YAML output. Requires ``output_path``. Defaults to False.
            validate (bool): If True, validate the output YAML file using
                the awesIO validator. Defaults to True.

        Returns:
            dict: Power curve data with keys ``'reference_height_m'``,
                ``'operational_altitude_m'``, ``'altitudes'``, and
                ``'profiles'``.

        Raises:
            ValueError: If model is not initialized.
        """
        if self.model is None:
            raise ValueError(
                "Power model not initialized. Call load_configuration first."
            )

        nprofiles = self.model.wind_resource["n_profiles"]
        print(f"Computing Luchsinger power curves ({nprofiles} wind profile(s))...")

        data = self.model.generate_power_curves(
            wind_speeds=wind_speeds,
            selected_profiles=selected_profiles,
            output_path=output_path,
            verbose=verbose,
            show_plot=showplot,
            save_plot=saveplot,
            validate_file=validate,
        )

        return data

    def calculate_power_at_wind_speed(
        self,
        wind_speed: float,
        selected_profile: int = 1,
        output_path: Path = None,
        verbose: bool = True,
        showplot: bool = False,
        saveplot: bool = False,
        validate: bool = True,
    ) -> float:
        """Calculate power output at a single wind speed.

        Uses the selected wind profile to derive the wind shear
        and calls the Luchsinger model for a single operating point.

        Args:
            wind_speed (float): Wind speed at reference height [m/s].
            selected_profile (int): Profile index (1-indexed). Defaults to 1.
            output_path (Path): Not used; the vendor model does not support
                single-point export. Defaults to None.
            verbose (bool): Whether to print the result. Defaults to True.
            showplot (bool): Not used. Defaults to False.
            saveplot (bool): Not used. Defaults to False.
            validate (bool): Not used for single-point evaluation.
                Defaults to True.

        Returns:
            float: Average cycle power output [W].

        Raises:
            ValueError: If model is not initialized.
        """
        if self.model is None:
            raise ValueError(
                "Power model not initialized. Call load_configuration first."
            )
        results = self.model.simulate_cycle_at_one_wind_speed(
            ws_ref=wind_speed,
            selected_profiles=[selected_profile - 1],  # Convert 1-indexed to 0-indexed
            verbose=verbose,
        )

        power = float(results[0]["cyclePower"])
        return power

    def plot_power_curves(
        self,
        power_curve_path: Path,
        output_dir: Path = None,
    ) -> None:
        """Plot power curves using the vendor's plotting functions.

        Loads the exported YAML and calls the vendor's
        ``plot_comprehensive_analysis`` visualisation.

        Args:
            power_curve_path (Path): Path to the exported power curves YAML.
            output_dir (Path): Directory where plot files will be saved.
                If None, plots are saved alongside ``power_curve_path``.
                Defaults to None.

        Raises:
            FileNotFoundError: If the power curves file does not exist.
            ImportError: If vendor plotting functions cannot be imported.
        """
        try:
            from src.power_luchsinger.plotting import (  # type: ignore
                plot_comprehensive_analysis,
                extract_model_params,
            )
        except ImportError as e:
            raise ImportError(
                f"Could not import vendor plotting functions: {e}"
            )

        powerCurvePath = Path(power_curve_path)
        if not powerCurvePath.exists():
            raise FileNotFoundError(
                f"Power curves file not found: {powerCurvePath}"
            )

        if output_dir is None:
            outputDir = powerCurvePath.parent
        else:
            outputDir = Path(output_dir)
            outputDir.mkdir(parents=True, exist_ok=True)

        savePath = str(outputDir / "power_curve_analysis.pdf")

        print(f"Generating power curve plot from: {powerCurvePath.name}")

        # Re-run power curves to get data object (vendor plotter requires dict,
        # not the YAML path) - use cached model
        data = self.compute_power_curves(verbose=False)

        plot_comprehensive_analysis(
            data,
            extract_model_params(self.model),
            save_path=savePath,
            show=True,
        )

        print(f"Plot saved to: {savePath}")

