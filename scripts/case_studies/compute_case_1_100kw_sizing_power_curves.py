#!/usr/bin/env python3
"""Compute QSM power curves for the case-study 1 100 kW sizing sweep."""

from __future__ import annotations

import argparse
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from _case1_100kw_sizing_common import (
    FIGURES_DIR,
    GENERATED_SYSTEMS_CSV,
    POWER_CURVE_DIR,
    POWER_CURVES_CSV,
    TETHER_FORCES_KN,
    apply_case_study_plot_style,
    design_color,
    design_color_label,
    extract_power_curve_rows_from_file,
    generated_system_metadata,
    group_rows,
    load_yaml,
    resolve_wind_resource,
    tether_force_linestyle,
    write_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wind-resource",
        type=Path,
        default=None,
        help="Wind-resource YAML. Defaults to the case-study 1 power-law file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute curves even if the output YAML already exists.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Number of parallel worker processes to use.",
    )
    parser.add_argument(
        "--generator-power",
        type=float,
        action="append",
        default=None,
        help="Only run systems with this generator rating in kW. Can be repeated.",
    )
    parser.add_argument(
        "--system-id",
        action="append",
        default=None,
        help="Only run this generated system ID. Can be repeated.",
    )
    parser.add_argument(
        "--profile-ids",
        type=int,
        nargs="+",
        default=None,
        help="Optional wind-profile IDs to pass to the QSM constructor.",
    )
    parser.add_argument(
        "--skip-plot",
        action="store_true",
        help="Do not regenerate the aggregate power-curve PDF.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated power-curve YAML files with awesIO.",
    )
    return parser.parse_args()


def _matches_filters(row: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.system_id is not None and row["system_id"] not in set(args.system_id):
        return False
    if args.generator_power is not None:
        return any(
            math.isclose(float(row["generator_power_kW"]), float(power_kw))
            for power_kw in args.generator_power
        )
    return True


def _run_one_power_curve(
    row: dict[str, Any],
    wind_resource_path: Path,
    profile_ids: list[int] | None,
    overwrite: bool,
    validate: bool,
) -> dict[str, Any]:
    from awespa.power.inertiafree_qsm_power import InertiaFreeQSMPowerModel

    output_path = POWER_CURVE_DIR / f"{row['system_id']}.yml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        return {
            "system_id": row["system_id"],
            "status": "skipped",
            "output_path": output_path,
        }

    model = InertiaFreeQSMPowerModel()
    model.load_configuration(
        system_path=Path(row["system_path"]),
        simulation_settings_path=Path(row["simulation_settings_path"]),
        wind_resource_path=wind_resource_path,
        validate=validate,
    )
    model.compute_power_curves(
        profile_ids=profile_ids,
        output_path=output_path,
        verbose=True,
        showplot=False,
        saveplot=True,
        validate=validate,
    )
    return {
        "system_id": row["system_id"],
        "status": "computed",
        "output_path": output_path,
    }


def run_power_curves(
    rows: list[dict[str, Any]],
    wind_resource_path: Path,
    profile_ids: list[int] | None,
    overwrite: bool,
    max_workers: int,
    validate: bool,
) -> list[dict[str, Any]]:
    if max_workers <= 1:
        return [
            _run_one_power_curve(
                row,
                wind_resource_path=wind_resource_path,
                profile_ids=profile_ids,
                overwrite=overwrite,
                validate=validate,
            )
            for row in rows
        ]

    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _run_one_power_curve,
                row,
                wind_resource_path,
                profile_ids,
                overwrite,
                validate,
            )
            for row in rows
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def collect_existing_power_curve_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for power_curve_path in sorted(POWER_CURVE_DIR.glob("case1_100kw_*.yml")):
        if power_curve_path.stem.endswith("_smoothed"):
            continue
        try:
            rows.extend(extract_power_curve_rows_from_file(power_curve_path))
        except FileNotFoundError as exc:
            print(f"Skipping {power_curve_path.name}: {exc}")
    return rows


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


def plot_power_curves(rows: list[dict[str, Any]]) -> Path | None:
    if not rows:
        return None

    apply_case_study_plot_style(mpl)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    generator_groups = group_rows(rows, "generator_power_kW")
    generator_powers = sorted(generator_groups, key=float)
    fig, axes = plt.subplots(
        1,
        len(generator_powers),
        figsize=(8, 2.8),
        sharey=True,
        constrained_layout=True,
    )
    if len(generator_powers) == 1:
        axes = [axes]

    kite_names = sorted({row["kite_name"] for row in rows})
    for ax, generator_kw in zip(axes, generator_powers):
        generator_rows = generator_groups[generator_kw]
        for system_rows in group_rows(generator_rows, "system_id").values():
            system_rows = sorted(system_rows, key=lambda row: float(row["wind_speed_mps"]))
            first = system_rows[0]
            ax.plot(
                [float(row["wind_speed_mps"]) for row in system_rows],
                [float(row["cycle_power_kW"]) for row in system_rows],
                color=design_color(mpl, first["kite_name"], float(generator_kw)),
                linestyle=tether_force_linestyle(float(first["max_tether_force_kN"])),
                alpha=0.9,
            )
        ax.set_title(f"{float(generator_kw):.0f} kW")
        ax.set_xlabel(r"Wind speed (m s$^{-1}$)")
        ax.grid(True, alpha=0.25)
    axes[0].set_ylabel("Cycle power (kW)")

    kite_handles = [
        Line2D(
            [0],
            [0],
            color=design_color(mpl, kite_name, float(generator_powers[0])),
            label=design_color_label(kite_name, float(generator_powers[0])),
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

    output_path = FIGURES_DIR / "case_1_sizing_power_curves.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def main() -> None:
    args = parse_args()
    wind_resource_path = resolve_wind_resource(args.wind_resource)

    rows = generated_system_metadata()
    selected_rows = [row for row in rows if _matches_filters(row, args)]
    if not selected_rows:
        raise SystemExit("No generated systems matched the selected filters.")

    print(f"Generated-system metadata: {GENERATED_SYSTEMS_CSV}")
    print(f"Wind resource: {wind_resource_path}")
    print(f"Selected systems: {len(selected_rows)}")

    results = run_power_curves(
        selected_rows,
        wind_resource_path=wind_resource_path,
        profile_ids=args.profile_ids,
        overwrite=args.overwrite,
        max_workers=max(1, args.max_workers),
        validate=args.validate,
    )

    computed = sum(result["status"] == "computed" for result in results)
    skipped = sum(result["status"] == "skipped" for result in results)
    print(f"Computed {computed} power curves; skipped {skipped} existing curves.")

    power_rows = collect_existing_power_curve_rows()
    write_csv(POWER_CURVES_CSV, _csv_rows(power_rows))
    print(f"Aggregate power-curve CSV: {POWER_CURVES_CSV}")

    if not args.skip_plot:
        figure_path = plot_power_curves(power_rows)
        if figure_path is not None:
            print(f"Aggregate power-curve figure: {figure_path}")

    # Touch one YAML load at the end so malformed outputs fail fast.
    for result in results:
        output_path = Path(result["output_path"])
        if output_path.exists():
            load_yaml(output_path)


if __name__ == "__main__":
    main()
