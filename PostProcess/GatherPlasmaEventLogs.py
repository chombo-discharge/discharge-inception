#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gather plasma simulation event logs from a database directory and produce a
structured CSV summary of each run's final state.

For every run in the database the script reads the last ``--tail`` lines of
``{prefix}{run_id}/pout.0``, extracts timing information and event flags
(inception, convergence failures, unexpected aborts), derives a per-run
status, and writes the results to a CSV file.  A human-readable summary table
is always printed to standard output.

Usage::

    python GatherPlasmaEventLogs.py <db_dir> [options]

See ``--help`` for the full option list.

Authors:
    André Kapelrud, Robert Marskar

Copyright © 2026 SINTEF Energi AS
"""

import argparse
import csv
import json
import re
import sys
from collections import deque
from pathlib import Path

# ---- optional imports ----

def _try_import_matplotlib():
    """Lazily import matplotlib.pyplot; return the module or None."""
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


# ---- metadata loading ----

def load_metadata(db_dir: Path):
    """
    Load run metadata from ``index.json`` (required) and ``structure.json``
    (optional) in *db_dir*.

    Parameters
    ----------
    db_dir : Path
        Root directory of the plasma simulation database.

    Returns
    -------
    keys : list of str
        Ordered list of sweep-parameter key names.
    coord_values : dict
        Mapping ``key -> sorted list of unique values`` for each parameter.
    run_index : dict
        Mapping ``str(run_id) -> list of parameter values`` (raw from index.json).
    prefix : str
        Run-directory prefix (e.g. ``"run_"``).
    """
    index_path = db_dir / "index.json"
    if not index_path.exists():
        print(f"error: {index_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(index_path) as f:
        idx = json.load(f)

    keys = idx["keys"]
    run_index = idx["index"]  # {"0": [val0, val1, ...], ...}
    prefix = idx.get("prefix", "run_")

    # Try to get coordinate order from structure.json
    structure_path = db_dir / "structure.json"
    coord_values = {}
    if structure_path.exists():
        with open(structure_path) as f:
            structure = json.load(f)
        pspace = structure.get("parameter_space", {})
        for key in keys:
            if key in pspace and "values" in pspace[key]:
                coord_values[key] = sorted(pspace[key]["values"])

    # Fallback: derive unique values from index
    for i, key in enumerate(keys):
        if key not in coord_values:
            vals = sorted({combo[i] for combo in run_index.values()})
            coord_values[key] = vals

    return keys, coord_values, run_index, prefix


# ---- per-run log parsing ----

_TIME_RE = re.compile(
    r'^Time\s*=\s*(?P<time>[-+]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][-+]?[0-9]+)?)'
)
_DT_RE = re.compile(
    r'^dt\s*=\s*(?P<dt>[-+]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][-+]?[0-9]+)?)'
)
_STEP_RE = re.compile(r'Driver::Time step report -- Time step #(?P<step>\d+)')

_INCEPTION_PREFIXES = (
    "ItoKMCBackgroundEvaluator -- stopping because",  # new soft-exit (daf83c56)
    "ItoKMCBackgroundEvaluator -- abort because",     # old hard-exit (backward compat)
)
_CONVERGENCE_PREFIX = (
    "ItoKMCGodunovStepper::advanceEulerMaruyama - Poisson solve did not converge"
)


def parse_pout(pout_path: Path, tail_n: int) -> dict:
    """
    Read the last *tail_n* lines of *pout_path* and extract run state.

    Parameters
    ----------
    pout_path : Path
        Path to the ``pout.0`` log file.
    tail_n : int
        Number of lines to read from the end of the file.

    Returns
    -------
    dict with keys:
        ``final_step``           – int or None
        ``final_time``           – float or None
        ``final_dt``             – float or None
        ``inception``            – bool
        ``convergence_failures`` – int
        ``other_abort``          – bool
        ``status``               – str: one of ``"not_found"``, ``"inception"``,
                                   ``"convergence_failure"``, ``"abort"``,
                                   ``"completed"``
    """
    result = {
        "final_step": None,
        "final_time": None,
        "final_dt": None,
        "inception": False,
        "convergence_failures": 0,
        "other_abort": False,
        "status": "not_found",
    }

    if not pout_path.exists():
        return result

    try:
        with open(pout_path, encoding="utf-8", errors="replace") as f:
            tail = deque(f, tail_n)
    except OSError as e:
        print(f"  warning: could not read {pout_path}: {e}", file=sys.stderr)
        return result

    for line in tail:
        stripped = line.strip()

        m = _STEP_RE.search(stripped)
        if m:
            result["final_step"] = int(m.group("step"))
            continue

        m = _TIME_RE.match(stripped)
        if m:
            result["final_time"] = float(m.group("time"))
            continue

        m = _DT_RE.match(stripped)
        if m:
            result["final_dt"] = float(m.group("dt"))
            continue

        if stripped.startswith(_INCEPTION_PREFIXES):
            result["inception"] = True
        elif stripped.startswith(_CONVERGENCE_PREFIX):
            result["convergence_failures"] += 1
        elif "abort" in stripped.lower() or "stopping because" in stripped.lower():
            result["other_abort"] = True

    # Derive status (priority: not_found > inception > convergence_failure > abort > completed)
    if result["final_time"] is None and result["final_step"] is None:
        result["status"] = "not_found"
    elif result["inception"]:
        result["status"] = "inception"
    elif result["convergence_failures"] > 0:
        result["status"] = "convergence_failure"
    elif result["other_abort"]:
        result["status"] = "abort"
    else:
        result["status"] = "completed"

    return result


# ---- data collection ----

def collect_runs(db_dir: Path, keys: list, run_index: dict, prefix: str, tail_n: int):
    """
    Iterate over every run in *run_index*, parse its ``pout.0``, and return
    a list of per-run result dicts.

    Parameters
    ----------
    db_dir : Path
        Root directory of the database.
    keys : list of str
        Parameter key names (in order).
    run_index : dict
        Mapping ``str(run_id) -> list of parameter values``.
    prefix : str
        Run-directory prefix.
    tail_n : int
        Lines to read from the end of each ``pout.0``.

    Returns
    -------
    list of dict
        One dict per run containing ``run_id``, one key per parameter, and
        all fields returned by :func:`parse_pout`.
    """
    rows = []
    for run_str, param_combo in sorted(run_index.items(), key=lambda x: int(x[0])):
        run_id = int(run_str)
        pout_path = db_dir / f"{prefix}{run_id}" / "pout.0"
        info = parse_pout(pout_path, tail_n)

        row = {"run_id": run_id}
        for i, key in enumerate(keys):
            row[key] = param_combo[i]
        row.update(info)
        rows.append(row)

    return rows


# ---- CSV output ----

_EXTRACT_FIELDS = [
    "final_step",
    "final_time",
    "final_dt",
    "inception",
    "convergence_failures",
    "other_abort",
    "status",
]


def write_csv(rows: list, keys: list, output_path: Path):
    """
    Write per-run results to a CSV file.

    Parameters
    ----------
    rows : list of dict
        Per-run data as returned by :func:`collect_runs`.
    keys : list of str
        Parameter key names (used to determine column order).
    output_path : Path
        Destination CSV file path.
    """
    fieldnames = ["run_id"] + keys + _EXTRACT_FIELDS
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})
    print(f"Wrote CSV to: {output_path}")


# ---- summary table ----

def print_summary(rows: list, keys: list):
    """
    Print a fixed-width summary table to standard output.

    Parameters
    ----------
    rows : list of dict
        Per-run data as returned by :func:`collect_runs`.
    keys : list of str
        Parameter key names.
    """
    param_w = 18
    status_w = 20
    time_w = 16
    dt_w = 16

    header_params = "  ".join(f"{k:>{param_w}}" for k in keys)
    print(f"#\n# {'Run':>5}  {header_params}  {'status':>{status_w}}"
          f"  {'final_time':>{time_w}}  {'final_dt':>{dt_w}}")
    print("# " + "-" * (5 + 2 + (param_w + 2) * len(keys) + status_w + 2 + time_w + 2 + dt_w))

    for row in rows:
        param_str = "  ".join(f"{row[k]:>{param_w}.6g}" for k in keys)
        t_str = f"{row['final_time']:>{time_w}.6g}" if row["final_time"] is not None else f"{'—':>{time_w}}"
        dt_str = f"{row['final_dt']:>{dt_w}.6g}" if row["final_dt"] is not None else f"{'—':>{dt_w}}"
        print(f"{row['run_id']:>5}  {param_str}  {row['status']:>{status_w}}  {t_str}  {dt_str}")
    print()


# ---- optional plot ----

def plot_status(rows: list, keys: list, plot_param: str):
    """
    Scatter plot of final simulation time vs. *plot_param*, colour-coded by
    status.  Requires matplotlib.

    Parameters
    ----------
    rows : list of dict
        Per-run data as returned by :func:`collect_runs`.
    keys : list of str
        Parameter key names (used to validate *plot_param*).
    plot_param : str
        Name of the sweep parameter to use as the x-axis.
    """
    plt = _try_import_matplotlib()
    if plt is None:
        print("error: matplotlib is not installed. Cannot plot.", file=sys.stderr)
        sys.exit(1)

    if plot_param not in keys:
        print(f"error: '{plot_param}' is not a known parameter. Known: {keys}", file=sys.stderr)
        sys.exit(1)

    status_colours = {
        "completed": "tab:green",
        "inception": "tab:orange",
        "convergence_failure": "tab:red",
        "abort": "tab:purple",
        "not_found": "tab:grey",
    }

    fig, ax = plt.subplots(figsize=(8, 5))
    for status, colour in status_colours.items():
        xs = [r[plot_param] for r in rows if r["status"] == status and r["final_time"] is not None]
        ys = [r["final_time"] for r in rows if r["status"] == status and r["final_time"] is not None]
        if xs:
            ax.scatter(xs, ys, label=status, color=colour, s=60, zorder=3)

    ax.set_xlabel(plot_param)
    ax.set_ylabel("Final simulation time")
    ax.set_title(f"Plasma run status vs {plot_param}")
    ax.legend()
    ax.grid(True, linestyle=":", linewidth=0.5)
    fig.tight_layout()
    plt.show()


# ---- main ----

def make_parser(add_help=True) -> argparse.ArgumentParser:
    """Return the configured argument parser (separated from main() for CLI reuse)."""
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description=(
            "Gather plasma event logs from a simulation database and write "
            "a structured CSV summary."
        )
    )
    ap.add_argument(
        "db_dir",
        help="Path to the plasma simulation database directory (must contain index.json).",
    )
    ap.add_argument(
        "--output", default=None, metavar="PATH",
        help="Output CSV path (default: <db_dir>/plasma_event_log.csv).",
    )
    ap.add_argument(
        "--tail", type=int, default=50, metavar="N",
        help="Number of lines to read from the end of each pout.0 (default: 50).",
    )
    ap.add_argument(
        "--plot", default=None, metavar="PARAM",
        help="Plot final time vs PARAM, colour-coded by status (requires matplotlib).",
    )
    ap.add_argument(
        "--no-output", action="store_true",
        help="Skip writing the CSV file; only print the summary table to stdout.",
    )
    return ap


def run(args) -> None:
    """Execute the pipeline given a pre-parsed Namespace."""
    db_dir = Path(args.db_dir)
    if not db_dir.is_dir():
        print(f"error: '{db_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    # Load metadata
    keys, coord_values, run_index, prefix = load_metadata(db_dir)

    print(f"# Database : {db_dir}")
    print(f"# Keys     : {keys}")
    print(f"# Runs     : {len(run_index)}")
    for k in keys:
        print(f"#   {k}: {coord_values[k]}")

    # Collect per-run data
    rows = collect_runs(db_dir, keys, run_index, prefix, args.tail)

    # Print summary
    print_summary(rows, keys)

    # Write CSV
    if not args.no_output:
        from discharge_inception.results import ensure_results_dir, link_metadata
        results_dir = ensure_results_dir(db_dir)
        output_path = Path(args.output) if args.output else results_dir / "plasma_event_log.csv"
        write_csv(rows, keys, output_path)
        link_metadata(db_dir, results_dir)

    # Optional plot
    if args.plot:
        plot_status(rows, keys, args.plot)


def main():
    """Parse command-line arguments and orchestrate the data pipeline."""
    run(make_parser().parse_args())


if __name__ == "__main__":
    main()
