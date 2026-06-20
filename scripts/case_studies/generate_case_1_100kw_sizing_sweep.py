#!/usr/bin/env python3
"""Generate the 100 kW sizing-sweep system and QSM settings files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _case1_100kw_sizing_common import (
    GENERATED_SETTINGS_DIR,
    GENERATED_SYSTEMS_CSV,
    GENERATED_SYSTEM_DIR,
    generate_all_system_files,
    write_csv,
)


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


def main() -> None:
    rows = generate_all_system_files()
    write_csv(GENERATED_SYSTEMS_CSV, _csv_rows(rows))

    print(f"Generated {len(rows)} 100 kW sizing systems.")
    print(f"System files: {GENERATED_SYSTEM_DIR}")
    print(f"QSM settings files: {GENERATED_SETTINGS_DIR}")
    print(f"Metadata CSV: {GENERATED_SYSTEMS_CSV}")


if __name__ == "__main__":
    main()
