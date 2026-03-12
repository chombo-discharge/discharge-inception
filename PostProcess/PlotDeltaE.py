#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plot peak ΔE vs voltage for all runs in a ``run_*`` database directory.

Reads ``index.json`` to find voltage (U) and ionisation coefficient (K) values,
then scans each ``voltage_*/pout.0`` log for the maximum ``Delta E(rel)`` and
``Delta E(max)`` across all time steps.

The resulting figure has:
  - Bottom x-axis: applied voltage U [V]
  - Upper x-axis:  K values (ticks aligned to U positions)
  - Left y-axis:   peak ΔE(rel) [%]  (default, or ``--rel-field``)
  - Right y-axis:  peak ΔE(max) [%]  (``--max-field``)

Authors:
    André Kapelrud, Robert Marskar

Copyright © 2026 SINTEF Energi AS
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_NUM = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'

_STEP_RE = re.compile(r'Driver::Time step report -- Time step #(?P<step>\d+)')
_EREL_RE = re.compile(rf'^\s*Delta\s*E\(rel\)\s*=\s*(?P<val>{_NUM})')
_EMAX_RE = re.compile(rf'^\s*Delta\s*E\(max\)\s*=\s*(?P<val>{_NUM})')


# ---------------------------------------------------------------------------
# Metadata loading  (verbatim from PlotDeltaERel.py)
# ---------------------------------------------------------------------------

def load_metadata(db_dir: Path) -> Tuple[list, str, dict, list]:
    """
    Load run metadata from ``index.json`` in *db_dir*.

    Returns
    -------
    keys : list of str
    prefix : str
    run_index : dict
    sorted_ids : list of str
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


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

def parse_pout_max(pout_path: Path) -> Tuple[Optional[float], Optional[float]]:
    """
    Scan *pout_path* and return the running maximum of ``Delta E(rel)`` and
    ``Delta E(max)`` across all time-step blocks.

    Returns
    -------
    (max_E_rel, max_E_max) — either value may be ``None`` if not found.
    """
    max_E_rel: Optional[float] = None
    max_E_max: Optional[float] = None

    in_block = False
    cur_erel: Optional[float] = None
    cur_emax: Optional[float] = None

    def _flush():
        nonlocal max_E_rel, max_E_max
        if cur_erel is not None:
            max_E_rel = cur_erel if max_E_rel is None else max(max_E_rel, cur_erel)
        if cur_emax is not None:
            max_E_max = cur_emax if max_E_max is None else max(max_E_max, cur_emax)

    try:
        with open(pout_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if _STEP_RE.search(line):
                    _flush()
                    in_block = True
                    cur_erel = None
                    cur_emax = None
                    continue

                if not in_block:
                    continue

                m = _EREL_RE.match(line)
                if m:
                    cur_erel = float(m.group("val"))
                    continue

                m = _EMAX_RE.match(line)
                if m:
                    cur_emax = float(m.group("val"))

        _flush()
    except OSError as exc:
        print(f"  warning: could not read {pout_path}: {exc}", file=sys.stderr)

    return max_E_rel, max_E_max


# ---------------------------------------------------------------------------
# Key lookup
# ---------------------------------------------------------------------------

def _find_key_index(keys: list, name_or_pattern: str, label: str) -> int:
    """Return the index in *keys* whose lowercase name matches *name_or_pattern*.

    Tries exact match first, then substring.  Exits with an error if not found.
    """
    needle = name_or_pattern.lower()
    # exact match
    for i, k in enumerate(keys):
        if k.lower() == needle:
            return i
    # substring match
    for i, k in enumerate(keys):
        if needle in k.lower():
            return i
    print(
        f"error: could not find {label} key in index.json keys {keys!r}. "
        f"Use the appropriate --voltage-key / --k-key override.",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_peak(rows: list, show_rel: bool, show_max: bool,
              png_path: Optional[Path]) -> None:
    """
    Draw peak ΔE vs voltage.

    Parameters
    ----------
    rows : list of (U, K, max_E_rel, max_E_max)
    show_rel : bool
    show_max : bool
    png_path : Path or None  — None means interactive window
    """
    Us = [r[0] for r in rows]

    fig, ax_left = plt.subplots(figsize=(7, 4))
    ax_left.set_xlabel('$U$ [V]')

    lines = []

    if show_rel:
        y_rel = [r[2] for r in rows]
        (ln,) = ax_left.plot(Us, y_rel, marker='o',
                             label=r'$\Delta E_\mathrm{rel}$ (%)')
        lines.append(ln)
        ax_left.set_ylabel(r'Peak $\Delta E_\mathrm{rel}$ (%)')

    if show_max:
        ax_right = ax_left.twinx()
        y_max = [r[3] for r in rows]
        (ln,) = ax_right.plot(Us, y_max, marker='s', color='tab:orange',
                              label=r'$\Delta E_\mathrm{max}$ (%)')
        lines.append(ln)
        ax_right.set_ylabel(r'Peak $\Delta E_\mathrm{max}$ (%)')

    # Upper x-axis: K values at the same tick positions as U
    ax_top = ax_left.twiny()
    ax_top.set_xlim(ax_left.get_xlim())
    ax_top.set_xticks([r[0] for r in rows])
    ax_top.set_xticklabels([f'{r[1]:.3g}' for r in rows], rotation=45, ha='left')
    ax_top.set_xlabel('$K$')

    if len(lines) > 1:
        labels = [ln.get_label() for ln in lines]
        ax_left.legend(lines, labels, fontsize='small')

    fig.tight_layout()

    if png_path:
        fig.savefig(png_path, dpi=150)
        print(f"Saved: {png_path}")
    else:
        plt.show()

    plt.close(fig)


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list, show_rel: bool, show_max: bool) -> None:
    """Write peak ΔE data to a CSV file."""
    col_names = ['U_V', 'K']
    if show_rel:
        col_names.append('peak_delta_e_rel_pct')
    if show_max:
        col_names.append('peak_delta_e_max_pct')

    with open(path, 'w') as f:
        f.write('# Peak Delta E vs voltage\n')
        f.write(f'# Columns: {", ".join(col_names)}\n')
        f.write('# U_V                  - applied voltage [V]\n')
        f.write('# K                    - ionisation coefficient K\n')
        if show_rel:
            f.write('# peak_delta_e_rel_pct - peak Delta E(rel) [%]\n')
        if show_max:
            f.write('# peak_delta_e_max_pct - peak Delta E(max) [%]\n')

        for row in rows:
            U, K, e_rel, e_max = row
            parts = [f'{U:.6g}', f'{K:.6g}']
            if show_rel:
                parts.append('' if e_rel is None else f'{e_rel:.6g}')
            if show_max:
                parts.append('' if e_max is None else f'{e_max:.6g}')
            f.write(','.join(parts) + '\n')

    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def make_parser(add_help: bool = True) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description=(
            "Plot peak Delta E vs voltage for all runs in a run_* directory. "
            "Bottom x-axis: U [V]; upper x-axis: K; left y-axis: peak ΔE(rel); "
            "right y-axis: peak ΔE(max)."
        ),
    )
    ap.add_argument(
        'db_dir',
        help='run_* directory containing index.json and voltage_*/ sub-dirs.',
    )
    ap.add_argument(
        '--rel-field', action='store_true',
        help='Plot peak Delta E(rel) on left y-axis (default if neither flag given).',
    )
    ap.add_argument(
        '--max-field', action='store_true',
        help='Plot peak Delta E(max) on right y-axis.',
    )
    ap.add_argument(
        '--voltage-key', default=None, metavar='KEY',
        help='Key name in index.json for voltage (auto-detected if omitted).',
    )
    ap.add_argument(
        '--k-key', default=None, metavar='KEY',
        help='Key name in index.json for K (auto-detected if omitted).',
    )
    ap.add_argument(
        '--prefix', default='pout', metavar='PREFIX',
        help="Log filename prefix (default: 'pout', giving pout.0).",
    )
    ap.add_argument(
        '--png', default=None, metavar='FILE',
        help='Save figure to FILE instead of opening an interactive window.',
    )
    ap.add_argument(
        '-o', '--output', default=None, metavar='FILE',
        help='Write results to a CSV file.',
    )
    return ap


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(args) -> None:
    db_dir = Path(args.db_dir)
    if not db_dir.is_dir():
        print(f"error: '{db_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    show_rel = args.rel_field or (not args.rel_field and not args.max_field)
    show_max = args.max_field

    keys, dir_prefix, run_index, sorted_ids = load_metadata(db_dir)

    # Locate voltage and K columns
    u_idx = _find_key_index(keys, args.voltage_key or 'voltage', 'voltage')
    k_idx = _find_key_index(keys, args.k_key or 'k', 'K')

    rows = []
    for run_str in sorted_ids:
        run_id = int(run_str)
        param_values = run_index[run_str]
        U = float(param_values[u_idx])
        K = float(param_values[k_idx])
        pout_path = db_dir / f"{dir_prefix}{run_id}" / f"{args.prefix}.0"
        max_E_rel, max_E_max = parse_pout_max(pout_path)
        rows.append((U, K, max_E_rel, max_E_max))

    rows.sort(key=lambda r: r[0])  # sort by voltage

    if not rows:
        print("warning: no data found", file=sys.stderr)
        sys.exit(1)

    png_path = Path(args.png) if args.png else None
    plot_peak(rows, show_rel, show_max, png_path)

    if args.output:
        write_csv(Path(args.output), rows, show_rel, show_max)


def main() -> None:
    run(make_parser().parse_args())


if __name__ == '__main__':
    main()
