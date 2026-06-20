"""Shared helpers for the case-study 1 100 kW sizing scripts."""

from __future__ import annotations

import csv
import math
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


KITE_OPTIONS = [
    {
        "name": "V11.100",
        "area_m2": 100.0,
        "projected_area_m2": 79.0,
        "mass_kg": 33.3,
        "minimum_tether_force_kn": 3.75,
    },
    {
        "name": "V11.120",
        "area_m2": 120.0,
        "projected_area_m2": 94.8,
        "mass_kg": 39.0,
        "minimum_tether_force_kn": 4.50,
    },
    {
        "name": "V11.140",
        "area_m2": 140.0,
        "projected_area_m2": 110.6,
        "mass_kg": 47.0,
        "minimum_tether_force_kn": 5.25,
    },
    {
        "name": "V11.160",
        "area_m2": 160.0,
        "projected_area_m2": 126.4,
        "mass_kg": 53.0,
        "minimum_tether_force_kn": 6.00,
    },
]

GENERATOR_POWERS_KW = [160, 170, 180]

TETHER_OPTIONS = [
    {"max_force_kn": 60.0, "diameter_m": 0.012},
    {"max_force_kn": 70.0, "diameter_m": 0.013},
    {"max_force_kn": 80.0, "diameter_m": 0.014},
]
TETHER_FORCES_KN = [option["max_force_kn"] for option in TETHER_OPTIONS]

KITE_BASE_COLORS = {
    "V11.100": "#0072B2",
    "V11.120": "#D55E00",
    "V11.140": "#009E73",
    "V11.160": "#CC79A7",
}

TEMPLATE_SYSTEM_PATH = PROJECT_ROOT / "config" / "meridional_case1" / "100kW_system.yml"
TEMPLATE_SIMULATION_SETTINGS_PATH = (
    PROJECT_ROOT / "config" / "meridional_case1" / "100kW_QSM_settings.yml"
)
GENERATED_SYSTEM_DIR = (
    PROJECT_ROOT / "config" / "meridional_case1" / "generated_100kw_sizing_systems"
)
GENERATED_SETTINGS_DIR = (
    PROJECT_ROOT / "config" / "meridional_case1" / "generated_100kw_sizing_settings"
)
RESULTS_DIR = PROJECT_ROOT / "results" / "case_studies" / "case_1_100kw_sizing"
POWER_CURVE_DIR = RESULTS_DIR / "power_curves"
AEP_DIR = RESULTS_DIR / "aep"
FIGURES_DIR = RESULTS_DIR / "figures"

GENERATED_SYSTEMS_CSV = RESULTS_DIR / "case_1_100kw_sizing_generated_systems.csv"
POWER_CURVES_CSV = RESULTS_DIR / "case_1_100kw_sizing_power_curves.csv"
SUMMARY_CSV = RESULTS_DIR / "case_1_100kw_sizing_summary.csv"

WIND_RESOURCE_CANDIDATES = [
    PROJECT_ROOT / "config" / "meridional_case1" / "power_law_case_1.yml",
    PROJECT_ROOT / "case_studies" / "case_1" / "wind_resource_profile_fit.yml",
    PROJECT_ROOT / "case_studies" / "meridional_case1" / "wind_resource_profile_fit.yml",
    PROJECT_ROOT / "config" / "meridional_case1" / "wind_resource_profile_fit.yml",
]


def resolve_wind_resource(user_path: Path | None = None) -> Path:
    if user_path is not None:
        path = user_path if user_path.is_absolute() else PROJECT_ROOT / user_path
        if path.exists():
            return path
        raise FileNotFoundError(f"Wind resource file not found: {path}")

    for path in WIND_RESOURCE_CANDIDATES:
        if path.exists():
            return path

    candidates = "\n  - ".join(str(path) for path in WIND_RESOURCE_CANDIDATES)
    raise FileNotFoundError(
        "Could not find the case-study 1 fitted power-law wind-resource YAML. "
        "Generate it first or pass --wind-resource.\nChecked:\n  - " + candidates
    )


def system_id(kite_name: str, force_kn: float, generator_kw: float) -> str:
    kite_slug = kite_name.replace(".", "_")
    return f"case1_100kw_{kite_slug}_{force_kn:g}kN_{generator_kw:g}kW"


def apply_case_study_plot_style(mpl_module: Any) -> None:
    latex_settings = (
        {
            "text.usetex": True,
            "text.latex.preamble": r"\usepackage{amsmath} \usepackage{amssymb}",
            "pgf.texsystem": "pdflatex",
            "pgf.rcfonts": False,
        }
        if shutil.which("latex")
        else {
            "text.usetex": False,
            "mathtext.fontset": "cm",
        }
    )
    mpl_module.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.prop_cycle": mpl_module.cycler(
                "color",
                [
                    "#0072B2",
                    "#D55E00",
                    "#009E73",
                    "#E69F00",
                    "#CC79A7",
                    "#56B4E9",
                ],
            ),
            "lines.linewidth": 1.5,
            "axes.linewidth": 0.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.minor.visible": True,
            "ytick.minor.visible": True,
            "xtick.major.size": 4,
            "ytick.major.size": 4,
            "xtick.minor.size": 2,
            "ytick.minor.size": 2,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.minor.width": 0.6,
            "ytick.minor.width": 0.6,
            "lines.markersize": 4,
            "errorbar.capsize": 3,
            "axes.xmargin": 0.02,
            "axes.ymargin": 0.02,
            "legend.frameon": False,
            "savefig.bbox": "tight",
            "savefig.dpi": 300,
            **latex_settings,
        }
    )


def design_color(mpl_module: Any, kite_name: str, generator_kw: float) -> tuple[float, ...]:
    base_color = KITE_BASE_COLORS.get(kite_name, "#4C4C4C")
    return _scale_color(mpl_module, base_color, 1.25)


def design_color_label(kite_name: str, generator_kw: float) -> str:
    return kite_name


def _scale_color(
    mpl_module: Any,
    color: str,
    factor: float,
) -> tuple[float, float, float, float]:
    rgb = mpl_module.colors.to_rgb(color)
    if factor < 1.0:
        lightened = tuple(1.0 - factor * (1.0 - channel) for channel in rgb)
        return (*lightened, 1.0)
    darkened = tuple(max(0.0, channel / factor) for channel in rgb)
    return (*darkened, 1.0)


def tether_diameter_m(max_tether_force_n: float) -> float:
    force_kn = max_tether_force_n / 1000.0
    for option in TETHER_OPTIONS:
        if math.isclose(option["max_force_kn"], force_kn):
            return float(option["diameter_m"])
    raise ValueError(f"No tether diameter configured for {force_kn:g} kN.")


def kite_option_by_name(kite_name: str) -> dict[str, Any]:
    for kite in KITE_OPTIONS:
        if kite["name"] == kite_name:
            return kite
    raise ValueError(f"No kite option configured for {kite_name!r}.")


def simulation_settings_path(system_id_value: str) -> Path:
    return GENERATED_SETTINGS_DIR / f"{system_id_value}_QSM_settings.yml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(data, stream, sort_keys=False)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_generated_dirs() -> None:
    GENERATED_SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    (GENERATED_SYSTEM_DIR / "README.md").write_text(
        "# Generated 100 kW sizing systems\n\n"
        "This folder is populated by "
        "`scripts/case_studies/generate_case_1_100kw_sizing_sweep.py`.\n"
        "System YAML files in this directory are generated from "
        "`config/meridional_case1/100kW_system.yml` and should not be "
        "edited by hand.\n",
        encoding="utf-8",
    )
    (GENERATED_SYSTEM_DIR / ".gitignore").write_text(
        "*.yml\n*.yaml\n!.gitignore\n!README.md\n",
        encoding="utf-8",
    )

    (GENERATED_SETTINGS_DIR / "README.md").write_text(
        "# Generated 100 kW sizing QSM settings\n\n"
        "This folder is populated by "
        "`scripts/case_studies/generate_case_1_100kw_sizing_sweep.py`.\n"
        "Each settings file is paired with one generated system YAML and "
        "contains the kite-specific minimum tether force from the sizing table.\n",
        encoding="utf-8",
    )
    (GENERATED_SETTINGS_DIR / ".gitignore").write_text(
        "*.yml\n*.yaml\n!.gitignore\n!README.md\n",
        encoding="utf-8",
    )


def make_system_file(
    template_system: dict[str, Any],
    kite: dict[str, Any],
    force_kn: float,
    generator_kw: float,
) -> dict[str, Any]:
    design_id = system_id(kite["name"], force_kn, generator_kw)
    max_force_n = force_kn * 1000.0
    diameter_m = tether_diameter_m(max_force_n)

    system = deepcopy(template_system)
    system["metadata"]["name"] = design_id
    system["metadata"]["description"] = (
        "Generated case-study 1 100 kW sizing sweep system"
    )

    wing = system["components"]["wing"]
    wing["name"] = kite["name"]
    wing["structure"]["projected_surface_area"] = float(kite["projected_area_m2"])
    wing["structure"]["mass"] = float(kite["mass_kg"])

    bridle = system["components"].get("bridle")
    if bridle is not None:
        bridle["name"] = f"{kite['name']} Bridle"

    tether = system["components"]["tether"]
    tether["name"] = f"{design_id} Tether"
    tether["structure"]["max_tether_force"] = float(max_force_n)
    tether["structure"]["diameter"] = float(diameter_m)

    ground_station = system["components"]["ground_station"]
    ground_station["name"] = f"{design_id} Ground Station"
    ground_station["generator"]["max_power"] = float(generator_kw * 1000.0)

    output_path = GENERATED_SYSTEM_DIR / f"{design_id}.yml"
    write_yaml(output_path, system)
    return metadata_from_system_file(output_path)


def make_settings_file(
    template_settings: dict[str, Any],
    kite: dict[str, Any],
    force_kn: float,
    generator_kw: float,
) -> None:
    design_id = system_id(kite["name"], force_kn, generator_kw)
    settings = deepcopy(template_settings)
    settings["cycle"]["minimum_tether_force"] = float(
        kite["minimum_tether_force_kn"] * 1000.0
    )
    write_yaml(simulation_settings_path(design_id), settings)


def generate_all_system_files() -> list[dict[str, Any]]:
    template_system = load_yaml(TEMPLATE_SYSTEM_PATH)
    template_settings = load_yaml(TEMPLATE_SIMULATION_SETTINGS_PATH)
    ensure_generated_dirs()
    for old_system_path in GENERATED_SYSTEM_DIR.glob("case1_100kw_*.yml"):
        old_system_path.unlink()
    for old_settings_path in GENERATED_SETTINGS_DIR.glob("case1_100kw_*_QSM_settings.yml"):
        old_settings_path.unlink()

    rows: list[dict[str, Any]] = []
    for kite in KITE_OPTIONS:
        for tether in TETHER_OPTIONS:
            force_kn = tether["max_force_kn"]
            for generator_kw in GENERATOR_POWERS_KW:
                rows.append(make_system_file(template_system, kite, force_kn, generator_kw))
                make_settings_file(template_settings, kite, force_kn, generator_kw)
    return rows


def metadata_from_system_file(system_path: Path) -> dict[str, Any]:
    system = load_yaml(system_path)
    wing = system["components"]["wing"]
    tether = system["components"]["tether"]
    generator = system["components"]["ground_station"]["generator"]
    kite = kite_option_by_name(wing["name"])

    max_tether_force_n = float(tether["structure"]["max_tether_force"])
    generator_power_w = float(generator["max_power"])
    system_id_value = system["metadata"]["name"]
    return {
        "system_id": system_id_value,
        "system_path": system_path,
        "simulation_settings_path": simulation_settings_path(system_id_value),
        "kite_name": wing["name"],
        "kite_area_m2": float(kite["area_m2"]),
        "kite_projected_area_m2": float(wing["structure"]["projected_surface_area"]),
        "kite_mass_kg": float(wing["structure"]["mass"]),
        "minimum_tether_force_kN": float(kite["minimum_tether_force_kn"]),
        "max_tether_force_kN": max_tether_force_n / 1000.0,
        "tether_diameter_m": float(tether["structure"]["diameter"]),
        "generator_power_kW": generator_power_w / 1000.0,
    }


def generated_system_metadata() -> list[dict[str, Any]]:
    system_paths = sorted(GENERATED_SYSTEM_DIR.glob("case1_100kw_*.yml"))
    return [metadata_from_system_file(path) for path in system_paths]


def extract_power_curve_rows(
    power_data: dict[str, Any],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    wind_speeds = power_data.get("reference_wind_speeds_m_s") or power_data.get(
        "reference_wind_speeds"
    )
    if wind_speeds is None:
        raise KeyError("Power-curve data has no reference wind speed array.")

    rows: list[dict[str, Any]] = []
    for curve in power_data["power_curves"]:
        cycle_power_w = cycle_power_values(curve)
        for wind_speed, power_w in zip(wind_speeds, cycle_power_w):
            rows.append(
                {
                    **{
                        key: value
                        for key, value in metadata.items()
                        if key != "system_path"
                    },
                    "wind_speed_mps": float(wind_speed),
                    "cycle_power_kW": float(power_w) / 1000.0,
                }
            )
    return rows


def extract_power_curve_rows_from_file(power_curve_path: Path) -> list[dict[str, Any]]:
    system_id_value = power_curve_path.stem
    system_path = GENERATED_SYSTEM_DIR / f"{system_id_value}.yml"
    metadata = metadata_from_system_file(system_path)
    return extract_power_curve_rows(load_yaml(power_curve_path), metadata)


def cycle_power_values(curve: dict[str, Any]) -> list[float]:
    if "wind_speed_data" not in curve and "electrical_cycle_power_w" in curve:
        return [float(power) for power in curve["electrical_cycle_power_w"]]
    return [
        float(item["performance"]["electrical_power"]["average_cycle_power"])
        for item in curve["wind_speed_data"]
    ]


def maximum_cycle_power_kw(power_data: dict[str, Any]) -> float:
    powers = []
    for curve in power_data.get("power_curves", []):
        powers.extend(cycle_power_values(curve))
    return max(powers) / 1000.0 if powers else 0.0


def rated_wind_speed(power_data: dict[str, Any]) -> float | None:
    wind_speeds = power_data.get("reference_wind_speeds_m_s") or power_data.get(
        "reference_wind_speeds"
    )
    if not wind_speeds:
        return None

    powers: list[float] = []
    for curve in power_data.get("power_curves", []):
        powers.extend(cycle_power_values(curve))
    if not powers:
        return None

    max_power = max(powers)
    threshold = 0.99 * max_power
    for wind_speed, power in zip(wind_speeds, powers[: len(wind_speeds)]):
        if power >= threshold:
            return float(wind_speed)
    return None


def group_rows(rows: list[dict[str, Any]], key: str) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return grouped


def tether_force_linestyle(force_kn: float) -> str:
    force_values = sorted(set(TETHER_FORCES_KN + [force_kn]))
    styles = ["-", "--", "-.", ":", (0, (5, 1)), (0, (3, 1, 1, 1))]
    return styles[force_values.index(force_kn) % len(styles)]
