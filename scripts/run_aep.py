#!/usr/bin/env python3
"""Run AEP calculation for the example configuration.

Usage:
    python scripts/run_aep.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from awespa.pipeline.aep import calculate_aep


def main() -> None:
    results_dir = PROJECT_ROOT / "results"
    config_dir = PROJECT_ROOT / "config" / "example"

    aep_results = calculate_aep(
        power_curve_path=config_dir / "inertiafree_qsm_power_curves.yml",
        wind_resource_path=config_dir / "wind_resource.yml",
        output_path=results_dir / "aep_results.yml",
        plot=True,
        plot_output_dir=results_dir / "plots",
    )
    print(aep_results["annual_energy_production"]["total"])


if __name__ == "__main__":
    main()