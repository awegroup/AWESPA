from awespa.pipeline.aep import calculate_aep
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"
CONFIG = Path(__file__).parent.parent / "config" / "example"

aep_results = calculate_aep(
    power_curve_path=CONFIG / "inertiafree_qsm_power_curves.yml",
    wind_resource_path=CONFIG / "wind_resource.yml",
    output_path=RESULTS / "aep_results.yml",
    plot=True,
    plot_output_dir=RESULTS / "plots",
)
print(aep_results['annual_energy_production']["total"])