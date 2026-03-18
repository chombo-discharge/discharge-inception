#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plot the relative electric field change Δ E(rel) vs time for all runs found
under a parent directory containing one or more ``voltage_*`` subdirectories
(each with its own ``index.json``), or directly from a single database
directory.

All curves are drawn on one figure, labelled by their sweep-parameter values.
An interactive window is shown by default; PNG output and CSV data export are
opt-in via ``--png`` and ``--output``.

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


# ---- Group discovery ----

def _find_groups(db_dir: Path) -> list:
    """Return sorted subdirectories that contain index.json.
    Falls back to [db_dir] itself if no subdirectories qualify."""
    subs = sorted(p for p in db_dir.iterdir()
                  if p.is_dir() and (p / 'index.json').exists())
    if subs:
        return subs
    if (db_dir / 'index.json').exists():
        return [db_dir]
    print(f"error: no index.json found under {db_dir}", file=sys.stderr)
    sys.exit(1)


# ---- Metadata loading ----

def load_metadata(db_dir: Path) -> Tuple[list, str, dict, list]:
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
    prefix : str
        Directory prefix for run folders.
    run_index : dict
        Mapping ``str(run_id) -> list of parameter values``.
    sorted_ids : list of str
        Run IDs sorted numerically.
    """
    index_path = db_dir / "index.json"
    if not index_path.exists():
        print(f"error: {index_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(index_path) as f:
        idx = json.load(f)

    keys = idx.get("keys") or idx.get("key") or []
    prefix = idx.get("prefix", "run_")
    run_index = idx["index"]
    sorted_ids = sorted(run_index.keys(), key=int)
    return keys, prefix, run_index, sorted_ids


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


# ---- Helpers ----

def _fmt_val(v) -> str:
    if isinstance(v, list):
        return '[' + ', '.join(_fmt_val(x) for x in v) + ']'
    try:
        return f'{v:.4g}'
    except (TypeError, ValueError):
        return str(v)


def _run_label(keys, param_values, group_path: Path, group_count: int) -> str:
    if keys and param_values:
        pairs = [(k, v) for k, v in zip(keys, param_values)
                 if k != "particle_position"]
        if pairs:
            return ", ".join(f"{k} = {_fmt_val(v)}" for k, v in pairs)
    return group_path.name


# ---- Plotting ----

def plot_all(curves, png_path=None, show: bool = False) -> None:
    """Draw all curves on one figure, optionally saving to PNG."""
    fig, ax = plt.subplots(figsize=(8, 4))
    for label, t, E_rel in curves:
        ax.plot(t * 1e9, E_rel, label=label)
    ax.set_ylabel(r'$\Delta E_\mathrm{rel}$ (%)')
    ax.set_xlabel('$t$ [ns]')
    ax.grid(True, linestyle=':', linewidth=0.5)
    if curves:
        ax.legend(fontsize='small')
    fig.tight_layout()
    if png_path:
        fig.savefig(png_path, dpi=150)
        print(f"Saved: {png_path}")
    if not png_path or show:
        plt.show()
    plt.close(fig)


# ---- CSV output ----

FIELDS       = ['label', 't_ns', 'delta_e_rel_pct']
DESCRIPTIONS = ['run label', 'simulation time [ns]', 'Delta E(rel) [%]']


def _aligned_rows(fieldnames, descriptions, rows):
    """Yield fixed-width formatted lines: 2 comment lines then header then data."""
    widths = []
    for f, d in zip(fieldnames, descriptions):
        w = max(len(f), len(d))
        if rows:
            w = max(w, max(len(str(row.get(f, ''))) for row in rows))
        widths.append(w + 2)

    def fmt(vals):
        return '  '.join(f'{str(v):<{w}}' for v, w in zip(vals, widths)).rstrip()

    yield '# ' + fmt(fieldnames)
    yield '# ' + fmt(descriptions)
    yield fmt(fieldnames)
    for row in rows:
        yield fmt([row.get(f, '') for f in fieldnames])


def write_csv(path: Path, curves) -> None:
    """Write curve data to a fixed-width aligned file with a commented header block."""
    rows = [{'label': label, 't_ns': f'{ti:.6g}', 'delta_e_rel_pct': f'{ei:.6g}'}
            for label, t, E_rel in curves
            for ti, ei in zip(t * 1e9, E_rel)]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# Delta E(rel) vs time\n')
        for line in _aligned_rows(FIELDS, DESCRIPTIONS, rows):
            f.write(line + '\n')
    print(f"Saved: {path}")


# ---- Main ----

def make_parser(add_help=True) -> argparse.ArgumentParser:
    """Return the configured argument parser (separated from main() for CLI reuse)."""
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description=(
            "Plot Delta E(rel) vs time for all runs found under a parent "
            "directory.  Multiple voltage_* subdirectories (each with "
            "index.json) are collected into one figure labelled by their "
            "sweep-parameter values."
        )
    )
    ap.add_argument(
        "db_dir",
        help="Parent directory containing voltage_* subdirs with index.json, "
             "or a single database directory with index.json.",
    )
    ap.add_argument(
        "--prefix", default="pout", metavar="PREFIX",
        help="Prefix for log filenames (default: 'pout', giving pout.0).",
    )
    ap.add_argument(
        "--png", metavar="FILE", default=None,
        help="Save figure to FILE (overrides default Results/ path).",
    )
    ap.add_argument(
        "--no-png", action="store_true",
        help="Skip saving the figure (show interactive window instead).",
    )
    ap.add_argument(
        "--show", action="store_true",
        help="Open an interactive matplotlib window (in addition to saving).",
    )
    ap.add_argument(
        "-o", "--output", metavar="FILE", default=None,
        help="Write curve data to a CSV file (overrides default Results/ path).",
    )
    ap.add_argument(
        "--no-csv", action="store_true",
        help="Skip writing the CSV output.",
    )
    return ap


def run(args) -> None:
    """Execute the pipeline given a pre-parsed Namespace."""
    db_dir = Path(args.db_dir)
    if not db_dir.is_dir():
        print(f"error: '{db_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    groups = _find_groups(db_dir)

    curves = []
    for group in groups:
        keys, dir_prefix, run_index, sorted_ids = load_metadata(group)
        for run_str in sorted_ids:
            run_id = int(run_str)
            pout_path = group / f"{dir_prefix}{run_id}" / f"{args.prefix}.0"
            t, E_rel = parse_pout(pout_path)
            if t.size == 0:
                continue
            label = _run_label(keys, run_index[run_str], group, len(groups))
            curves.append((label, t, E_rel))

    if not curves:
        print("warning: no data found", file=sys.stderr)
        sys.exit(1)

    from discharge_inception.results import ensure_results_dir, link_metadata
    results_dir = ensure_results_dir(db_dir)

    if args.no_png:
        png_path = None
    elif args.png:
        png_path = Path(args.png)
    else:
        png_path = results_dir / 'delta_e_rel.png'

    plot_all(curves, png_path=png_path, show=args.show)

    if not args.no_csv:
        csv_path = Path(args.output) if args.output else results_dir / 'delta_e_rel.csv'
        write_csv(csv_path, curves)

    link_metadata(db_dir, results_dir)


def main():
    """Parse command-line arguments and plot Delta E(rel) curves."""
    run(make_parser().parse_args())


if __name__ == "__main__":
    main()
