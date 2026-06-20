#!/usr/bin/env python3
"""Analyze AEP and capacity factor for the case-study 1 100 kW sizing sweep."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Callable

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from _case1_100kw_sizing_common import (
    AEP_DIR,
    FIGURES_DIR,
    POWER_CURVE_DIR,
    SUMMARY_CSV,
    TETHER_FORCES_KN,
    apply_case_study_plot_style,
    design_color,
    design_color_label,
    generated_system_metadata,
    group_rows,
    load_yaml,
    maximum_cycle_power_kw,
    rated_wind_speed,
    resolve_wind_resource,
    tether_force_linestyle,
    write_csv,
    write_yaml,
)
from awespa.pipeline.aep import calculate_aep


FAILED_POWER_THRESHOLD_KW = 1.0
RATED_POWER_WINDOW_MIN_KW = 100.0
RATED_POWER_WINDOW_MAX_KW = 103.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wind-resource",
        type=Path,
        default=None,
        help="Wind-resource YAML. Defaults to the case-study 1 power-law file.",
    )
    parser.add_argument(
        "--skip-aep-yaml",
        action="store_true",
        help="Calculate summaries without writing per-system AEP YAML files.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Only write the summary CSV.",
    )
    return parser.parse_args()


def _csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    csv_rows: list[dict[str, Any]] = []
    for row in rows:
        csv_rows.append(
            {
                key: str(value) if isinstance(value, Path) else value
                for key, value in row.items()
            }
        )
    return csv_rows


def _power_curve_path(system_id: str) -> Path:
    return POWER_CURVE_DIR / f"{system_id}.yml"


def _aep_input_path(power_curve_path: Path) -> Path:
    power_data = load_yaml(power_curve_path)
    if "reference_wind_speeds" in power_data:
        return power_curve_path
    if "reference_wind_speeds_m_s" not in power_data:
        raise KeyError(f"{power_curve_path} has no reference wind-speed key.")

    aep_input_path = AEP_DIR / f"{power_curve_path.stem}_aep_input.yml"
    patched_data = dict(power_data)
    patched_data["reference_wind_speeds"] = patched_data["reference_wind_speeds_m_s"]
    write_yaml(aep_input_path, patched_data)
    return aep_input_path


def calculate_summary_rows(
    wind_resource_path: Path,
    skip_aep_yaml: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metadata in generated_system_metadata():
        power_curve_path = _power_curve_path(metadata["system_id"])
        if not power_curve_path.exists():
            print(f"Skipping missing power curve: {power_curve_path}")
            continue

        power_data = load_yaml(power_curve_path)
        aep_output_path = AEP_DIR / f"{metadata['system_id']}_aep.yml"
        aep_result = calculate_aep(
            power_curve_path=_aep_input_path(power_curve_path),
            wind_resource_path=wind_resource_path,
            output_path=None if skip_aep_yaml else aep_output_path,
            plot=False,
        )

        total_aep = aep_result["annual_energy_production"]["total"]["aep_mwh"]
        capacity_factor = aep_result["power_summary"]["capacity_factor"]
        rows.append(
            {
                **metadata,
                "power_curve_path": power_curve_path,
                "aep_output_path": "" if skip_aep_yaml else aep_output_path,
                "aep_mwh": float(total_aep),
                "capacity_factor": float(capacity_factor),
                "capacity_factor_percent": float(capacity_factor) * 100.0,
                "rated_power_kW": maximum_cycle_power_kw(power_data),
                "rated_wind_speed_mps": rated_wind_speed(power_data),
            }
        )
    return rows


def _wind_speeds(power_data: dict[str, Any]) -> np.ndarray:
    values = power_data.get("reference_wind_speeds_m_s") or power_data.get(
        "reference_wind_speeds"
    )
    if values is None:
        raise KeyError("Power curve has no reference wind speeds.")
    return np.asarray(values, dtype=float)


def _curve_power_kw(curve: dict[str, Any]) -> np.ndarray:
    if "wind_speed_data" not in curve and "electrical_cycle_power_w" in curve:
        return np.asarray(curve["electrical_cycle_power_w"], dtype=float) / 1000.0
    return np.asarray(
        [
            item["performance"]["electrical_power"]["average_cycle_power"]
            for item in curve["wind_speed_data"]
        ],
        dtype=float,
    ) / 1000.0


def smooth_power_curve_for_plot(
    wind_speeds: np.ndarray,
    power_kw: np.ndarray,
    window: int = 3,
) -> np.ndarray:
    valid = np.isfinite(power_kw) & (power_kw > FAILED_POWER_THRESHOLD_KW)
    if np.count_nonzero(valid) >= 2:
        smoothed = np.interp(wind_speeds, wind_speeds[valid], power_kw[valid])
    elif np.count_nonzero(valid) == 1:
        smoothed = np.full_like(power_kw, float(power_kw[valid][0]))
    else:
        return power_kw

    if window <= 1 or smoothed.size < window:
        return smoothed

    pad_left = window // 2
    pad_right = window - 1 - pad_left
    padded = np.pad(smoothed, (pad_left, pad_right), mode="edge")
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def _first_curve_xy(row: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    power_data = load_yaml(Path(row["power_curve_path"]))
    wind = _wind_speeds(power_data)
    curve = power_data["power_curves"][0]
    return wind, smooth_power_curve_for_plot(wind, _curve_power_kw(curve))


def plot_power_curves(
    rows: list[dict[str, Any]],
    output_path: Path,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> Path | None:
    selected_rows = [row for row in rows if predicate is None or predicate(row)]
    if not selected_rows:
        return None

    apply_case_study_plot_style(mpl)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generator_powers = sorted({float(row["generator_power_kW"]) for row in selected_rows})
    fig, axes = plt.subplots(
        1,
        len(generator_powers),
        figsize=(8, 2.8),
        sharey=True,
        constrained_layout=True,
    )
    if len(generator_powers) == 1:
        axes = [axes]

    for ax, generator_kw in zip(axes, generator_powers):
        generator_rows = [
            row
            for row in selected_rows
            if math.isclose(float(row["generator_power_kW"]), generator_kw)
        ]
        for row in sorted(
            generator_rows,
            key=lambda item: (
                float(item["kite_area_m2"]),
                float(item["max_tether_force_kN"]),
            ),
        ):
            wind, power_kw = _first_curve_xy(row)
            ax.plot(
                wind,
                power_kw,
                color=design_color(mpl, row["kite_name"], generator_kw),
                linestyle=tether_force_linestyle(float(row["max_tether_force_kN"])),
                alpha=0.9,
            )
        ax.set_title(f"{generator_kw:.0f} kW")
        ax.set_xlabel(r"Wind speed (m s$^{-1}$)")
        ax.grid(True, alpha=0.25)
    axes[0].set_ylabel("Cycle power (kW)")

    kite_names = sorted({row["kite_name"] for row in selected_rows})
    kite_handles = [
        Line2D(
            [0],
            [0],
            color=design_color(mpl, kite_name, generator_powers[0]),
            label=design_color_label(kite_name, generator_powers[0]),
        )
        for kite_name in kite_names
    ]
    tether_handles = [
        Line2D(
            [0],
            [0],
            color="0.2",
            linestyle=tether_force_linestyle(force_kn),
            label=f"{force_kn:g} kN",
        )
        for force_kn in sorted(TETHER_FORCES_KN)
    ]
    axes[0].legend(handles=kite_handles, loc="lower right", title="Kite size")
    axes[-1].legend(handles=tether_handles, loc="upper left", title="Tether force")

    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def _line_plot_by_generator(rows: list[dict[str, Any]], metric: str, ylabel: str, output: Path) -> None:
    apply_case_study_plot_style(mpl)
    output.parent.mkdir(parents=True, exist_ok=True)
    generator_powers = sorted({float(row["generator_power_kW"]) for row in rows})
    fig, axes = plt.subplots(
        1,
        len(generator_powers),
        figsize=(8, 2.8),
        sharey=True,
        constrained_layout=True,
    )
    if len(generator_powers) == 1:
        axes = [axes]

    for ax, generator_kw in zip(axes, generator_powers):
        generator_rows = [
            row for row in rows if math.isclose(float(row["generator_power_kW"]), generator_kw)
        ]
        for kite_name, kite_rows in group_rows(generator_rows, "kite_name").items():
            kite_rows = sorted(kite_rows, key=lambda row: float(row["max_tether_force_kN"]))
            ax.plot(
                [float(row["max_tether_force_kN"]) for row in kite_rows],
                [float(row[metric]) for row in kite_rows],
                marker="o",
                color=design_color(mpl, kite_name, generator_kw),
                label=design_color_label(kite_name, generator_kw),
            )
        ax.set_title(f"{generator_kw:.0f} kW")
        ax.set_xlabel("Maximum tether force (kN)")
        ax.grid(True, alpha=0.25)
    axes[0].set_ylabel(ylabel)
    axes[0].legend(loc="best", title="Kite size")
    fig.savefig(output)
    plt.close(fig)


def _heatmap_plot(rows: list[dict[str, Any]], metric: str, label: str, output: Path) -> None:
    apply_case_study_plot_style(mpl)
    output.parent.mkdir(parents=True, exist_ok=True)
    generator_powers = sorted({float(row["generator_power_kW"]) for row in rows})
    kite_areas = sorted({float(row["kite_area_m2"]) for row in rows})
    tether_forces = sorted({float(row["max_tether_force_kN"]) for row in rows})

    fig, axes = plt.subplots(
        1,
        len(generator_powers),
        figsize=(8, 2.8),
        sharey=True,
        constrained_layout=True,
    )
    if len(generator_powers) == 1:
        axes = [axes]

    image = None
    for ax, generator_kw in zip(axes, generator_powers):
        matrix = np.full((len(kite_areas), len(tether_forces)), np.nan)
        for row in rows:
            if not math.isclose(float(row["generator_power_kW"]), generator_kw):
                continue
            i = kite_areas.index(float(row["kite_area_m2"]))
            j = tether_forces.index(float(row["max_tether_force_kN"]))
            matrix[i, j] = float(row[metric])
        image = ax.imshow(matrix, origin="lower", aspect="auto", cmap="viridis")
        ax.set_title(f"{generator_kw:.0f} kW")
        ax.set_xticks(range(len(tether_forces)), [f"{force:g}" for force in tether_forces])
        ax.set_yticks(range(len(kite_areas)), [f"{area:g}" for area in kite_areas])
        ax.set_xlabel("Maximum tether force (kN)")
    axes[0].set_ylabel(r"Kite area (m$^2$)")
    if image is not None:
        fig.colorbar(image, ax=axes, label=label, shrink=0.85)
    fig.savefig(output)
    plt.close(fig)


def expand_scatter_limits(ax: plt.Axes, fraction: float = 0.08) -> None:
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    xpad = (xmax - xmin) * fraction
    ypad = (ymax - ymin) * fraction
    ax.set_xlim(xmin - xpad, xmax + xpad)
    ax.set_ylim(ymin - ypad, ymax + ypad)


def add_nonoverlapping_scatter_labels(
    ax: plt.Axes,
    points: list[tuple[float, float, str]],
) -> None:
    offsets = [
        (5, 5),
        (5, -8),
        (-22, 5),
        (-22, -8),
        (8, 14),
        (-28, 14),
        (8, -17),
        (-28, -17),
    ]
    used_bboxes = []
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    for x_value, y_value, label in points:
        chosen_text = None
        for dx, dy in offsets:
            text = ax.annotate(
                label,
                xy=(x_value, y_value),
                xytext=(dx, dy),
                textcoords="offset points",
                fontsize=7,
                bbox={
                    "boxstyle": "round,pad=0.12",
                    "facecolor": "white",
                    "edgecolor": "none",
                    "alpha": 0.85,
                },
            )
            fig.canvas.draw()
            bbox = text.get_window_extent(renderer=renderer).expanded(1.03, 1.15)
            if not any(bbox.overlaps(existing) for existing in used_bboxes):
                chosen_text = text
                used_bboxes.append(bbox)
                break
            text.remove()

        if chosen_text is None:
            text = ax.annotate(
                label,
                xy=(x_value, y_value),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=7,
                bbox={
                    "boxstyle": "round,pad=0.12",
                    "facecolor": "white",
                    "edgecolor": "none",
                    "alpha": 0.85,
                },
            )
            fig.canvas.draw()
            used_bboxes.append(text.get_window_extent(renderer=renderer))


def plot_scatter(rows: list[dict[str, Any]], output: Path) -> None:
    apply_case_study_plot_style(mpl)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8), constrained_layout=True)

    marker_by_tether = {60.0: "o", 70.0: "s", 80.0: "^"}
    size_by_generator = {160.0: 42, 170.0: 74, 180.0: 108}
    label_points: list[tuple[float, float, str]] = []

    for row in rows:
        x_value = float(row["capacity_factor_percent"])
        y_value = float(row["aep_mwh"])
        tether = float(row["max_tether_force_kN"])
        generator = float(row["generator_power_kW"])
        ax.scatter(
            x_value,
            y_value,
            s=size_by_generator.get(generator, 70),
            marker=marker_by_tether.get(tether, "o"),
            color=design_color(mpl, row["kite_name"], generator),
            edgecolor="black",
            linewidth=0.5,
            alpha=0.9,
        )
        label_points.append((x_value, y_value, f"{float(row['rated_power_kW']):.1f}"))

    ax.set_xlabel("Capacity factor (%)")
    ax.set_ylabel("AEP (MWh)")
    ax.grid(True, alpha=0.25)
    expand_scatter_limits(ax)
    add_nonoverlapping_scatter_labels(ax, label_points)
    expand_scatter_limits(ax)

    kite_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            color=design_color(mpl, kite_name, 170.0),
            label=design_color_label(kite_name, 170.0),
        )
        for kite_name in sorted({row["kite_name"] for row in rows})
    ]
    tether_handles = [
        Line2D(
            [0],
            [0],
            marker=marker_by_tether.get(force, "o"),
            linestyle="",
            color="0.2",
            label=f"{force:g} kN",
        )
        for force in sorted({float(row["max_tether_force_kN"]) for row in rows})
    ]
    generator_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            color="0.2",
            markersize=math.sqrt(size_by_generator.get(power, 70)),
            label=f"{power:g} kW",
        )
        for power in sorted({float(row["generator_power_kW"]) for row in rows})
    ]

    kite_legend = ax.legend(handles=kite_handles, loc="lower right", title="Kite size")
    ax.add_artist(kite_legend)
    tether_legend = ax.legend(handles=tether_handles, loc="upper left", title="Tether force")
    ax.add_artist(tether_legend)
    ax.legend(
        handles=generator_handles,
        loc="upper left",
        bbox_to_anchor=(0.28, 1.0),
        title="Generator",
    )

    fig.savefig(output)
    plt.close(fig)


def create_plots(rows: list[dict[str, Any]]) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plot_power_curves(rows, FIGURES_DIR / "case_1_sizing_power_curves.pdf")
    plot_power_curves(
        rows,
        FIGURES_DIR / "case_1_sizing_power_curves_rated_100_103kW.pdf",
        predicate=lambda row: RATED_POWER_WINDOW_MIN_KW
        < float(row["rated_power_kW"])
        < RATED_POWER_WINDOW_MAX_KW,
    )
    _line_plot_by_generator(
        rows,
        "aep_mwh",
        "AEP (MWh)",
        FIGURES_DIR / "case_1_sizing_aep.pdf",
    )
    _line_plot_by_generator(
        rows,
        "capacity_factor_percent",
        "Capacity factor (%)",
        FIGURES_DIR / "case_1_sizing_capacity_factor.pdf",
    )
    _heatmap_plot(
        rows,
        "aep_mwh",
        "AEP (MWh)",
        FIGURES_DIR / "case_1_sizing_aep_heatmap_by_generator.pdf",
    )
    _heatmap_plot(
        rows,
        "capacity_factor_percent",
        "Capacity factor (%)",
        FIGURES_DIR / "case_1_sizing_capacity_factor_heatmap_by_generator.pdf",
    )
    plot_scatter(rows, FIGURES_DIR / "case_1_sizing_aep_capacity_factor_scatter.pdf")


def print_rated_table(rows: list[dict[str, Any]]) -> None:
    print("\nRated wind speeds and rated powers:")
    print("system_id,rated_wind_speed_mps,rated_power_kW,aep_mwh,capacity_factor_percent")
    for row in sorted(
        rows,
        key=lambda item: (
            float(item["kite_area_m2"]),
            float(item["max_tether_force_kN"]),
            float(item["generator_power_kW"]),
        ),
    ):
        rated_speed = row["rated_wind_speed_mps"]
        rated_speed_text = "" if rated_speed is None else f"{float(rated_speed):.1f}"
        print(
            f"{row['system_id']},"
            f"{rated_speed_text},"
            f"{float(row['rated_power_kW']):.1f},"
            f"{float(row['aep_mwh']):.1f},"
            f"{float(row['capacity_factor_percent']):.1f}"
        )


def main() -> None:
    args = parse_args()
    wind_resource_path = resolve_wind_resource(args.wind_resource)

    rows = calculate_summary_rows(
        wind_resource_path=wind_resource_path,
        skip_aep_yaml=args.skip_aep_yaml,
    )
    if not rows:
        raise SystemExit("No power-curve results were found to analyze.")

    write_csv(SUMMARY_CSV, _csv_rows(rows))
    print(f"Summary CSV: {SUMMARY_CSV}")
    print_rated_table(rows)

    if not args.skip_plots:
        create_plots(rows)
        print(f"Figures: {FIGURES_DIR}")


if __name__ == "__main__":
    main()
