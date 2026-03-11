#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch-plot the relative electric field change Δ E(rel) vs time for every run
in a plasma simulation database.

For each run found in ``index.json`` the script reads the corresponding
``{prefix}{run_id}.0`` log file, extracts ``Time`` and ``Delta E(rel)`` at
every reported time step, and saves a PNG figure annotated with the run's
sweep-parameter values.

Usage::

    python PlotDeltaERel.py <db_dir> [options]

See ``--help`` for the full option list.

Authors:
    André Kapelrud, Robert Marskar

Copyright © 2026 SINTEF Energi AS
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
import matplotlib.pyplot as plt

# ---- Regex patterns ----

_NUM = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'

_TIME_RE = re.compile(
    rf'^\s*Time\s*=\s*(?P<time>{_NUM})'
)
_EREL_RE = re.compile(
    rf'^\s*Delta\s*E\(rel\)\s*=\s*(?P<E_rel>{_NUM})'
)
_STEP_RE = re.compile(r'Driver::Time step report -- Time step #(?P<step>\d+)')


# ---- Metadata loading ----

def load_metadata(db_dir: Path) -> Tuple[list, dict, list]:
    """
    Load run metadata from ``index.json`` in *db_dir*.

    Parameters
    ----------
    db_dir : Path
        Root directory of the plasma simulation database.

    Returns
    -------
    keys : list of str
        Ordered sweep-parameter key names.
    run_index : dict
        Mapping ``str(run_id) -> list of parameter values``.
    sorted_ids : list of int
        Run IDs sorted numerically.
    """
    index_path = db_dir / "index.json"
    if not index_path.exists():
        print(f"error: {index_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(index_path) as f:
        idx = json.load(f)

    keys = idx.get("keys", [])
    run_index = idx["index"]
    sorted_ids = sorted(run_index.keys(), key=int)
    return keys, run_index, sorted_ids


# ---- Per-run log parsing ----

def parse_pout(pout_path: Path) -> Tuple[np.ndarray, np.ndarray]:
    """
    Read ``Time`` and ``Delta E(rel)`` from a single ``pout.N`` log file.

    The file is scanned for ``Driver::Time step report`` sentinel lines to
    identify block boundaries.  Within each block the latest ``Time`` and
    ``Delta E(rel)`` values are recorded and stored by step number.  Steps
    that are missing either field are silently skipped.

    Parameters
    ----------
    pout_path : Path
        Path to the log file (e.g. ``pout0.0``).

    Returns
    -------
    t : np.ndarray
        Simulation times, sorted by step number.
    E_rel : np.ndarray
        Corresponding ``Delta E(rel)`` values (%).
    """
    records: dict = {}  # step -> (time, E_rel)
    current_step = None
    t_val = None
    e_val = None

    def _flush():
        if current_step is not None and t_val is not None and e_val is not None:
            records[current_step] = (t_val, e_val)

    try:
        with open(pout_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _STEP_RE.search(line)
                if m:
                    _flush()
                    current_step = int(m.group("step"))
                    t_val = None
                    e_val = None
                    continue

                if current_step is None:
                    continue

                m = _TIME_RE.match(line.strip())
                if m:
                    t_val = float(m.group("time"))
                    continue

                m = _EREL_RE.match(line.strip())
                if m:
                    e_val = float(m.group("E_rel"))

        _flush()
    except OSError as exc:
        print(f"  warning: could not read {pout_path}: {exc}", file=sys.stderr)

    if not records:
        return np.array([]), np.array([])

    steps = sorted(records.keys())
    t = np.array([records[s][0] for s in steps])
    E = np.array([records[s][1] for s in steps])
    return t, E


# ---- Single-run plotting ----

def plot_run(run_id: int,
             t: np.ndarray,
             E_rel: np.ndarray,
             keys: list,
             param_values: list,
             output_path: Path) -> None:
    """
    Save a ``Delta E(rel)`` vs time figure for one run.

    Parameters
    ----------
    run_id : int
        Run identifier (used in the default output filename).
    t : np.ndarray
        Simulation time array (seconds).
    E_rel : np.ndarray
        Corresponding ``Delta E(rel)`` values (%).
    keys : list of str
        Sweep-parameter key names (used to build the title).
    param_values : list
        Parameter values for this run (same order as *keys*).
    output_path : Path
        Destination PNG file path.
    """
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(t * 1e9, E_rel)
    ax.set_ylabel(r'$\Delta E_\mathrm{rel}$ (%)')
    ax.set_xlabel('$t$ [ns]')
    ax.grid(True, linestyle=':', linewidth=0.5)

    if keys and param_values:
        parts = ", ".join(
            f"{k} = {v:.4g}" for k, v in zip(keys, param_values)
        )
        ax.set_title(parts)
    else:
        ax.set_title(f"Run {run_id}")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {output_path}")


# ---- Main ----

def make_parser(add_help=True) -> argparse.ArgumentParser:
    """Return the configured argument parser (separated from main() for CLI reuse)."""
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description=(
            "Batch-plot Delta E(rel) vs time for every run in a plasma "
            "simulation database."
        )
    )
    ap.add_argument(
        "db_dir",
        help="Path to the plasma simulation database directory (must contain index.json).",
    )
    ap.add_argument(
        "--prefix", default="pout", metavar="PREFIX",
        help="Prefix for log filenames (default: 'pout', giving pout0.0, pout1.0, …).",
    )
    ap.add_argument(
        "--output-dir", default=None, metavar="DIR",
        help="Directory for output PNG files (default: same as db_dir).",
    )
    return ap


def run(args) -> None:
    """Execute the pipeline given a pre-parsed Namespace."""
    db_dir = Path(args.db_dir)
    if not db_dir.is_dir():
        print(f"error: '{db_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else db_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    keys, run_index, sorted_ids = load_metadata(db_dir)

    print(f"# Database : {db_dir}")
    print(f"# Runs     : {len(sorted_ids)}")

    for run_str in sorted_ids:
        run_id = int(run_str)
        pout_path = db_dir / f"{args.prefix}{run_id}.0"
        param_values = run_index[run_str]

        print(f"Run {run_id}: {pout_path}")
        t, E_rel = parse_pout(pout_path)

        if t.size == 0:
            print(f"  warning: no data found, skipping.")
            continue

        out_png = output_dir / f"plt_{run_id}.png"
        plot_run(run_id, t, E_rel, keys, param_values, out_png)


def main():
    """Parse command-line arguments and produce one PNG per database run."""
    run(make_parser().parse_args())


if __name__ == "__main__":
    main()
