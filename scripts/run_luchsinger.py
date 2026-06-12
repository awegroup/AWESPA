#!/usr/bin/env python3
"""Run the Luchsinger power model via the AWESPA wrapper.

Demonstrates both direct single-wind-speed calculation and full power curve
generation using the LuchsingerPowerModel wrapper class.

Usage:
    python scripts/run_luchsinger.py
"""

import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from awespa.power.luchsinger_power import LuchsingerPowerModel


def main():
    """Run Luchsinger model and export power curves."""
    # ---- paths -----------------------------------------------    ------------
    configDir = PROJECT_ROOT / "config"
    systemPath = configDir / "example" / "tudelft V3_25.yml"
    simulationSettingsPath = configDir /"example" / "luchsinger_settings.yml"
    windResourcePath = configDir / "example" / "wind_resource.yml"

    resultsDir = PROJECT_ROOT / "results" / "example"
    resultsDir.mkdir(parents=True, exist_ok=True)
    outputPath = resultsDir / "luchsinger_power_curves.yml"

    # ---- initialise and load model ---------------------------------------
    model = LuchsingerPowerModel()

    model.load_configuration(
        system_path=systemPath,
        simulation_settings_path=simulationSettingsPath,
        wind_resource_path=windResourcePath,
    )

    # ---- single wind speed test ------------------------------------------
    print("\n" + "=" * 60)
    print("SINGLE WIND SPEED TEST (profile 1)")
    print("=" * 60)
    power = model.calculate_power_at_wind_speed(
        wind_speed=10.0,
        verbose=True,
        showplot=True,
        saveplot=True,
    )
    print(f"\nCalculated power at 10 m/s: {power} W")

    # ---- full power curve ------------------------------------------------
    print("\n" + "=" * 60)
    print("FULL POWER CURVE GENERATION")
    print("=" * 60)
    data = model.compute_power_curves(
        output_path=outputPath,
        verbose=True,
        showplot=True,
        saveplot=True,
    )

    # ---- summary ---------------------------------------------------------
    print("\n" + "=" * 60)
    print("POWER CURVE GENERATION COMPLETE")
    print("=" * 60)
    print(f"\n  Output: {outputPath}")
    print("\nAll done!")


if __name__ == "__main__":
    main()
