#!/usr/bin/env python3
"""Run the Inertia-Free QSM power model via the AWESPA wrapper.

Demonstrates direct single-wind-speed calculation and power curve generation
using the InertiaFreeQSMPowerModel wrapper class.

Usage:
    python scripts/run_inertiafree_qsm.py
"""

import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from awespa.power.inertiafree_qsm_power import InertiaFreeQSMPowerModel


def main():
    """Run InertiaFree-QSM model and export power curves."""
    # ---- paths -----------------------------------------------------------
    configDir = PROJECT_ROOT / "config" / "meridional_case1"
    systemPath = configDir / "case_1_selected_100kw" / "case1_100kw_V11_160_80kN_170kW.yml"
    simulationSettingsPath = configDir / "case_1_selected_100kw" / "case1_100kw_V11_160_80kN_170kW_QSM_settings.yml"
    windResourcePath = configDir / "clustered_case_2.yml"

    resultsDir = PROJECT_ROOT / "results" / "case_studies" / "case_2_selected_100kw"
    resultsDir.mkdir(parents=True, exist_ok=True)
    outputPath = resultsDir / "power_curves_case2_100kw_V11_160_80kN_170kW_clustered.yml"

    # ---- initialise and load model ---------------------------------------
    model = InertiaFreeQSMPowerModel()

    model.load_configuration(
        system_path=systemPath,
        simulation_settings_path=simulationSettingsPath,
        wind_resource_path=windResourcePath,
    )

    # ---- single wind speed test ------------------------------------------
    power = model.calculate_power_at_wind_speed(
        wind_speed=10.0,
        method="direct",
        profile_id=1,
        verbose=True,
    )

    # ---- full power curve ----------------------------
    data = model.compute_power_curves(
        profile_ids=None,
        output_path=outputPath,
        verbose=True,
        showplot=True,
        saveplot=True,
    )

    # ---- summary ---------------------------------------------------------
    print("\n" + "=" * 60)
    print("POWER CURVE GENERATION COMPLETE")
    print("=" * 60)
    print(f"\n  Power curve output: {outputPath}")
    print("\nAll done!")


if __name__ == "__main__":
    main()
