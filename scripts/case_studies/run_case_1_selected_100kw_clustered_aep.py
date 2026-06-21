#!/usr/bin/env python3
"""Run selected 100 kW AEP calculations for clustered profiles and power law."""

from __future__ import annotations

import argparse
import csv
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from _case1_100kw_sizing_common import (
    PROJECT_ROOT,
    apply_case_study_plot_style,
    load_yaml,
    write_yaml,
)
from awespa.pipeline.aep import calculate_aep
from awespa.power.inertiafree_qsm_power import InertiaFreeQSMPowerModel


FAILED_POWER_THRESHOLD_W = 1.0
PLOT_SMOOTHING_WINDOW = 5
DEFAULT_SYSTEM_ID = "case1_100kw_V11_160_80kN_170kW"
DEFAULT_INPUT_DIR = (
    PROJECT_ROOT / "config" / "meridional_case1" / "case_1_selected_100kw"
)
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results" / "case_studies" / "case_1_selected_100kw"


def default_paths() -> dict[str, Path]:
    return {
        "system": DEFAULT_INPUT_DIR / f"{DEFAULT_SYSTEM_ID}.yml",
        "settings": DEFAULT_INPUT_DIR / f"{DEFAULT_SYSTEM_ID}_QSM_settings.yml",
        "clustered_wind": PROJECT_ROOT
        / "config"
        / "meridional_case1"
        / "clustered_case_1.yml",
        "power_law_wind": PROJECT_ROOT
        / "config"
        / "meridional_case1"
        / "power_law_case_1.yml",
        "clustered_power_curves": DEFAULT_RESULTS_DIR
        / f"power_curves_{DEFAULT_SYSTEM_ID}_clustered.yml",
        "power_law_power_curves": DEFAULT_RESULTS_DIR
        / f"power_curves_{DEFAULT_SYSTEM_ID}_power_law.yml",
        "clustered_aep": DEFAULT_RESULTS_DIR / f"aep_{DEFAULT_SYSTEM_ID}_clustered.yml",
        "power_law_aep": DEFAULT_RESULTS_DIR / f"aep_{DEFAULT_SYSTEM_ID}_power_law.yml",
        "clustered_summary_csv": DEFAULT_RESULTS_DIR
        / f"aep_{DEFAULT_SYSTEM_ID}_clustered_summary.csv",
        "power_law_summary_csv": DEFAULT_RESULTS_DIR
        / f"aep_{DEFAULT_SYSTEM_ID}_power_law_summary.csv",
        "figures_dir": DEFAULT_RESULTS_DIR / "figures",
    }


def parse_args() -> argparse.Namespace:
    paths = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", type=Path, default=paths["system"])
    parser.add_argument("--settings", type=Path, default=paths["settings"])
    parser.add_argument(
        "--wind-resource",
        type=Path,
        default=paths["clustered_wind"],
        help="Clustered/profile wind-resource YAML.",
    )
    parser.add_argument(
        "--power-law-wind-resource",
        type=Path,
        default=paths["power_law_wind"],
        help="Power-law wind-resource YAML.",
    )
    parser.add_argument(
        "--power-curves",
        type=Path,
        default=paths["clustered_power_curves"],
        help="Output path for clustered/profile power curves.",
    )
    parser.add_argument(
        "--power-law-power-curves",
        type=Path,
        default=paths["power_law_power_curves"],
        help="Output path for power-law power curves.",
    )
    parser.add_argument(
        "--aep-output",
        type=Path,
        default=paths["clustered_aep"],
        help="Output path for clustered/profile AEP YAML.",
    )
    parser.add_argument(
        "--power-law-aep-output",
        type=Path,
        default=paths["power_law_aep"],
        help="Output path for power-law AEP YAML.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=paths["clustered_summary_csv"],
        help="Summary CSV for clustered/profile AEP.",
    )
    parser.add_argument(
        "--power-law-summary-csv",
        type=Path,
        default=paths["power_law_summary_csv"],
        help="Summary CSV for power-law AEP.",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=paths["figures_dir"],
        help="Directory for selected-system figures.",
    )
    parser.add_argument(
        "--profile-ids",
        type=int,
        nargs="+",
        default=None,
        help="Clustered/profile IDs to compute. Defaults to all profiles.",
    )
    parser.add_argument(
        "--power-law-profile-ids",
        type=int,
        nargs="+",
        default=[1],
        help="Power-law profile IDs to compute. Defaults to profile 1.",
    )
    parser.add_argument(
        "--wind-speeds",
        type=float,
        nargs="+",
        default=None,
        help="Reference wind speeds to compute. Defaults to the settings file grid.",
    )
    parser.add_argument(
        "--compute-power-curves",
        action="store_true",
        help="Recompute the QSM power curves before AEP.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate QSM input/output YAMLs with awesIO.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed QSM optimizer progress.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def compute_power_curves(
    label: str,
    system_path: Path,
    settings_path: Path,
    wind_resource_path: Path,
    output_path: Path,
    profile_ids: list[int] | None,
    wind_speeds: np.ndarray | None,
    validate: bool,
    verbose: bool,
) -> Path:
    print(f"\nComputing {label} power curves")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = InertiaFreeQSMPowerModel()
    model.load_configuration(
        system_path=system_path,
        simulation_settings_path=settings_path,
        wind_resource_path=wind_resource_path,
        validate=validate,
    )
    model.compute_power_curves(
        wind_speeds=wind_speeds,
        profile_ids=profile_ids,
        output_path=output_path,
        verbose=verbose,
        showplot=False,
        saveplot=True,
        validate=validate,
    )
    return output_path


def _wind_speeds(power_data: dict[str, Any]) -> np.ndarray:
    values = power_data.get("reference_wind_speeds_m_s") or power_data.get(
        "reference_wind_speeds"
    )
    if values is None:
        raise KeyError("Power curve has no reference wind-speed array.")
    return np.asarray(values, dtype=float)


def _electrical_power_values(curve: dict[str, Any]) -> np.ndarray:
    if "wind_speed_data" not in curve and "electrical_cycle_power_w" in curve:
        return np.asarray(curve["electrical_cycle_power_w"], dtype=float)
    if "cycle_power_w" in curve:
        return np.asarray(curve["cycle_power_w"], dtype=float)
    return np.asarray(
        [
            item["performance"]["electrical_power"]["average_cycle_power"]
            for item in curve["wind_speed_data"]
        ],
        dtype=float,
    )


def _interpolate_failed_points(wind_speeds: np.ndarray, power_w: np.ndarray) -> tuple[np.ndarray, int]:
    valid = np.isfinite(power_w) & (power_w > FAILED_POWER_THRESHOLD_W)
    failed_count = int(np.count_nonzero(~valid))
    if failed_count == 0:
        return power_w.copy(), 0
    if np.count_nonzero(valid) >= 2:
        return np.interp(wind_speeds, wind_speeds[valid], power_w[valid]), failed_count
    if np.count_nonzero(valid) == 1:
        return np.full_like(power_w, float(power_w[valid][0])), failed_count
    return power_w.copy(), failed_count


def _update_curve_power_values(curve: dict[str, Any], filled_power_w: np.ndarray) -> None:
    if "wind_speed_data" not in curve:
        curve["electrical_cycle_power_w"] = [float(value) for value in filled_power_w]
        curve["cycle_power_w"] = [float(value) for value in filled_power_w]
        return

    for item, power_w in zip(curve["wind_speed_data"], filled_power_w):
        performance = item.setdefault("performance", {})
        performance.setdefault("power", {})["average_cycle_power"] = float(power_w)
        performance.setdefault("electrical_power", {})[
            "average_cycle_power"
        ] = float(power_w)
        item["successful"] = bool(power_w > FAILED_POWER_THRESHOLD_W)


def _smooth_power_for_plot(power_kw: np.ndarray, window: int = PLOT_SMOOTHING_WINDOW) -> np.ndarray:
    if window <= 1 or power_kw.size < 3:
        return power_kw

    window = min(window, power_kw.size)
    if window % 2 == 0:
        window -= 1
    if window < 3:
        return power_kw

    pad = window // 2
    padded = np.pad(power_kw, (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=float) / float(window)
    smoothed = np.convolve(padded, kernel, mode="valid")
    smoothed[0] = power_kw[0]
    smoothed[-1] = power_kw[-1]
    return smoothed


def smooth_failed_power_curve_points(power_curve_path: Path, label: str) -> Path:
    power_data = deepcopy(load_yaml(power_curve_path))
    wind_speeds = _wind_speeds(power_data)
    total_failed = 0
    for curve in power_data.get("power_curves", []):
        power_w = _electrical_power_values(curve)
        filled_power_w, failed_count = _interpolate_failed_points(wind_speeds, power_w)
        total_failed += failed_count
        _update_curve_power_values(curve, filled_power_w)

    smoothed_path = power_curve_path.with_name(f"{power_curve_path.stem}_smoothed.yml")
    write_yaml(smoothed_path, power_data)
    print(f"{label}: smoothed {total_failed} failed power points -> {smoothed_path}")
    return smoothed_path


def calculate_and_save_aep(
    label: str,
    power_curve_path: Path,
    wind_resource_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    print(f"\nCalculating {label} AEP")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = calculate_aep(
        power_curve_path=power_curve_path,
        wind_resource_path=wind_resource_path,
        output_path=output_path,
        plot=False,
    )
    total = result["annual_energy_production"]["total"]["aep_mwh"]
    cf = result["power_summary"]["capacity_factor"] * 100.0
    rated_kw = result["power_summary"]["max_rated_power_w"] / 1000.0
    print(f"{label}: AEP {total:.1f} MWh, CF {cf:.1f}%, rated power {rated_kw:.1f} kW")
    return result


def write_summary_csv(path: Path, label: str, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = [
        {
            "label": label,
            "profile_id": "total",
            "frequency_percent": 100.0,
            "rated_power_kW": result["power_summary"]["max_rated_power_w"] / 1000.0,
            "rated_wind_speed_mps": result["power_summary"][
                "max_rated_power_wind_speed_m_s"
            ],
            "aep_mwh": result["annual_energy_production"]["total"]["aep_mwh"],
            "capacity_factor_percent": result["power_summary"]["capacity_factor"] * 100.0,
        }
    ]
    for profile in result["annual_energy_production"]["by_profile"]:
        rows.append(
            {
                "label": label,
                "profile_id": profile["profile_id"],
                "frequency_percent": float(profile["frequency"]) * 100.0,
                "rated_power_kW": float(profile["rated_power_w"]) / 1000.0,
                "rated_wind_speed_mps": profile["rated_wind_speed_m_s"],
                "aep_mwh": profile["aep_mwh"],
                "capacity_factor_percent": "",
            }
        )

    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{label} summary CSV: {path}")


def _plot_power_curve_file(
    ax: plt.Axes,
    power_curve_path: Path,
    label: str,
    power_law: bool,
) -> None:
    power_data = load_yaml(power_curve_path)
    wind_speeds = _wind_speeds(power_data)
    if power_law:
        for curve_index, curve in enumerate(power_data.get("power_curves", []), start=1):
            curve_label = label if curve_index == 1 else f"{label} {curve_index}"
            ax.plot(
                wind_speeds,
                _smooth_power_for_plot(_electrical_power_values(curve) / 1000.0),
                color="black",
                linestyle="--",
                label=curve_label,
            )
        return

    for curve in power_data.get("power_curves", []):
        profile_id = curve.get("profile_id", len(ax.lines) + 1)
        ax.plot(
            wind_speeds,
            _smooth_power_for_plot(_electrical_power_values(curve) / 1000.0),
            label=f"Profile {profile_id}",
            alpha=0.9,
        )


def plot_power_curves(
    power_law_power_curve_path: Path,
    clustered_power_curve_path: Path,
    output_path: Path,
) -> Path:
    apply_case_study_plot_style(mpl)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.0), constrained_layout=True)
    _plot_power_curve_file(ax, clustered_power_curve_path, "Profiles", power_law=False)
    _plot_power_curve_file(ax, power_law_power_curve_path, "Power law", power_law=True)
    ax.set_xlabel(r"Wind speed (m s$^{-1}$)")
    ax.set_ylabel("Cycle power (kW)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Power-curve PDF: {output_path}")
    return output_path


def main() -> None:
    args = parse_args()
    system_path = resolve_path(args.system)
    settings_path = resolve_path(args.settings)
    clustered_wind_path = resolve_path(args.wind_resource)
    power_law_wind_path = resolve_path(args.power_law_wind_resource)
    clustered_power_curves_path = resolve_path(args.power_curves)
    power_law_power_curves_path = resolve_path(args.power_law_power_curves)
    clustered_aep_path = resolve_path(args.aep_output)
    power_law_aep_path = resolve_path(args.power_law_aep_output)
    clustered_summary_csv = resolve_path(args.summary_csv)
    power_law_summary_csv = resolve_path(args.power_law_summary_csv)
    figures_dir = resolve_path(args.figures_dir)
    wind_speeds = (
        np.asarray(args.wind_speeds, dtype=float)
        if args.wind_speeds is not None
        else None
    )

    if args.compute_power_curves:
        compute_power_curves(
            label="power-law",
            system_path=system_path,
            settings_path=settings_path,
            wind_resource_path=power_law_wind_path,
            output_path=power_law_power_curves_path,
            profile_ids=args.power_law_profile_ids,
            wind_speeds=wind_speeds,
            validate=args.validate,
            verbose=args.verbose,
        )
    power_law_smoothed_path = smooth_failed_power_curve_points(
        power_law_power_curves_path,
        "Power law",
    )
    power_law_aep = calculate_and_save_aep(
        "Power law",
        power_law_smoothed_path,
        power_law_wind_path,
        power_law_aep_path,
    )
    write_summary_csv(power_law_summary_csv, "power_law", power_law_aep)

    if args.compute_power_curves:
        compute_power_curves(
            label="profile",
            system_path=system_path,
            settings_path=settings_path,
            wind_resource_path=clustered_wind_path,
            output_path=clustered_power_curves_path,
            profile_ids=args.profile_ids,
            wind_speeds=wind_speeds,
            validate=args.validate,
            verbose=args.verbose,
        )
    clustered_smoothed_path = smooth_failed_power_curve_points(
        clustered_power_curves_path,
        "Profiles",
    )
    clustered_aep = calculate_and_save_aep(
        "Profiles",
        clustered_smoothed_path,
        clustered_wind_path,
        clustered_aep_path,
    )
    write_summary_csv(clustered_summary_csv, "profiles", clustered_aep)

    plot_power_curves(
        power_law_power_curve_path=power_law_smoothed_path,
        clustered_power_curve_path=clustered_smoothed_path,
        output_path=figures_dir / "selected_100kw_power_curves.pdf",
    )


if __name__ == "__main__":
    main()
