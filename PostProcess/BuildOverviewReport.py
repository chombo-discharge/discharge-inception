#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate a multi-page PDF overview report (``overview_report.pdf``) that aggregates
all post-processing results for an inception study into a single scannable booklet.

PDF structure
-------------
  Page 1    : Cover / summary (study name, date, run counts, parameter keys)
  Page 2    : SLURM job status for both stages
  Page 3    : Plasma termination map (colour-coded per-run status table)
  Page 4    : ΔE(rel) vs K — overview (all runs on one axes)
  Page 5    : Time-series compact grid (ΔE(rel) and ΔE(max) thumbnail per run)
  Pages 6…N : Time-series per run (full 2×4 panel)
  Page N+1  : PDIV inception voltages

Each section renders a placeholder page with a "data not available" notice when its
source file is missing rather than raising an exception.

Authors:
    André Kapelrud, Robert Marskar

Copyright © 2026 SINTEF Energi AS
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# matplotlib — required (non-interactive Agg backend for off-screen PDF rendering)
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Patch
except ImportError as _mpl_exc:
    print(f"error: matplotlib is required for BuildOverviewReport ({_mpl_exc}).",
          file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Optional: xarray (for reading NetCDF inception voltages)
# ---------------------------------------------------------------------------
try:
    import xarray as xr
    _XARRAY_AVAILABLE = True
except ImportError:
    _XARRAY_AVAILABLE = False
    xr = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Optional: AnalyzeTimeSeries (for read_dat helper)
# ---------------------------------------------------------------------------
_PP_DIR = Path(__file__).parent
if str(_PP_DIR) not in sys.path:
    sys.path.insert(0, str(_PP_DIR))

try:
    from AnalyzeTimeSeries import read_dat as _read_dat, FIELDS as _ATS_FIELDS  # noqa: E402
    _ATS_AVAILABLE = True
except ImportError:
    _ATS_AVAILABLE = False
    _read_dat = None
    _ATS_FIELDS = []

# ---------------------------------------------------------------------------
# Optional: GatherPlasmaEventLogs (for parse_pout status extraction)
# ---------------------------------------------------------------------------
try:
    from GatherPlasmaEventLogs import parse_pout as _gpl_parse_pout  # noqa: E402
    _GPL_AVAILABLE = True
except ImportError:
    _GPL_AVAILABLE = False
    _gpl_parse_pout = None

# ---------------------------------------------------------------------------
# Optional: slurm_status (for SLURM job status page)
# ---------------------------------------------------------------------------
_PKG_ROOT = _PP_DIR.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

try:
    from discharge_inception.slurm_status import (  # noqa: E402
        read_job_id, get_task_states, classify_state,
    )
    _SLURM_AVAILABLE = True
except ImportError:
    _SLURM_AVAILABLE = False

# ---------------------------------------------------------------------------
# Voltage variable names (mirrors ExtractInceptionVoltages.VOLTAGE_VARS)
# ---------------------------------------------------------------------------
_VOLTAGE_VARS = [
    "min_voltage_pos",
    "min_voltage_neg",
    "streamer_voltage_pos",
    "streamer_voltage_neg",
    "townsend_voltage_pos",
    "townsend_voltage_neg",
]

_VOLTAGE_TYPES = [
    ("Minimum",  "min_voltage_pos",      "min_voltage_neg"),
    ("Streamer", "streamer_voltage_pos",  "streamer_voltage_neg"),
    ("Townsend", "townsend_voltage_pos",  "townsend_voltage_neg"),
]

# ---------------------------------------------------------------------------
# Colour maps
# ---------------------------------------------------------------------------
_STATUS_HEX = {
    "completed":           "#2ca02c",
    "inception":           "#1f77b4",
    "convergence_failure": "#ff7f0e",
    "abort":               "#d62728",
    "not_found":           "#7f7f7f",
}

_SLURM_HEX = {
    "COMPLETED":  "#2ca02c",
    "RUNNING":    "#ff7f0e",
    "PENDING":    "#ff7f0e",
    "FAILED":     "#d62728",
    "CANCELLED":  "#d62728",
    "UNKNOWN":    "#7f7f7f",
}

_WHITE = (1.0, 1.0, 1.0, 1.0)


def _fmt_val(v) -> str:
    """Format a parameter value compactly."""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _get_pout_status(pout_path: Path) -> str:
    """
    Return a status string for *pout_path* using :func:`GatherPlasmaEventLogs.parse_pout`
    when available, otherwise a minimal local fallback.
    """
    if _GPL_AVAILABLE:
        return _gpl_parse_pout(pout_path, tail_n=50)["status"]
    # Minimal fallback
    if not pout_path.exists():
        return "not_found"
    from collections import deque
    _inc = ("ItoKMCBackgroundEvaluator -- stopping because",
            "ItoKMCBackgroundEvaluator -- abort because")
    try:
        with open(pout_path, encoding="utf-8", errors="replace") as f:
            tail = list(deque(f, 50))
    except OSError:
        return "not_found"
    has_time = inception = convergence = abort = False
    for line in tail:
        s = line.strip()
        if re.match(r"^Time\s*=", s) or "Time step report" in s:
            has_time = True
        if any(s.startswith(p) for p in _inc):
            inception = True
        elif "Poisson solve did not converge" in s:
            convergence = True
        elif "abort" in s.lower() or "stopping because" in s.lower():
            abort = True
    if not has_time:
        return "not_found"
    if inception:
        return "inception"
    if convergence:
        return "convergence_failure"
    if abort:
        return "abort"
    return "completed"


def _rgba(hex_color: str, alpha: float = 0.35) -> tuple:
    """Return an RGBA tuple for *hex_color* with the given *alpha*."""
    r, g, b, _ = mcolors.to_rgba(hex_color)
    return (r, g, b, alpha)


# ---------------------------------------------------------------------------
# Shared helper: placeholder page
# ---------------------------------------------------------------------------

def _placeholder_page(pdf: PdfPages, title: str, message: str) -> None:
    """Render a page that announces missing data rather than crashing."""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis("off")
    ax.text(0.5, 0.60, title,
            ha="center", va="center", fontsize=18, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.44, message,
            ha="center", va="center", fontsize=11, color="gray", style="italic",
            wrap=True, transform=ax.transAxes)
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 1: Cover
# ---------------------------------------------------------------------------

def _page_cover(pdf: PdfPages, study_root: Path,
                plasma_runs: int, pdiv_runs: int,
                plasma_keys: list, pdiv_keys: list) -> None:
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis("off")

    y = 0.88
    ax.text(0.5, y, "Inception Study Overview",
            ha="center", va="top", fontsize=26, fontweight="bold",
            transform=ax.transAxes)
    y -= 0.09
    ax.text(0.5, y, str(study_root),
            ha="center", va="top", fontsize=10, color="#555555",
            transform=ax.transAxes)
    y -= 0.055
    ax.text(0.5, y, f"Generated: {date.today().isoformat()}",
            ha="center", va="top", fontsize=10, color="#777777",
            transform=ax.transAxes)

    # Horizontal rule (uses axes-fraction coordinates via ax.plot)
    y -= 0.04
    ax.plot([0.08, 0.92], [y, y], color="#333333", linewidth=0.8,
            transform=ax.transAxes)
    y -= 0.02

    # Run-count table
    rows = [
        ("Component",           "Runs",         "Parameter keys"),
        ("pdiv_database",       str(pdiv_runs),  ", ".join(pdiv_keys) or "—"),
        ("plasma_simulations",  str(plasma_runs), ", ".join(plasma_keys) or "—"),
    ]
    col_x = [0.12, 0.40, 0.53]
    row_dy = 0.065

    for i, row in enumerate(rows):
        y_row = y - i * row_dy
        weight = "bold" if i == 0 else "normal"
        size   = 12 if i == 0 else 11
        for text, cx in zip(row, col_x):
            ax.text(cx, y_row, text,
                    ha="left", va="top", fontsize=size, fontweight=weight,
                    transform=ax.transAxes)
        if i == 0:
            ax.plot([0.08, 0.92], [y_row - 0.045, y_row - 0.045],
                    color="#999999", linewidth=0.5, transform=ax.transAxes)

    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 2: SLURM status
# ---------------------------------------------------------------------------

def _slurm_table(ax, stage_name: str, stage_dir: Path) -> None:
    """Render a SLURM task-state table (or a descriptive message) into *ax*."""
    ax.axis("off")
    ax.set_title(stage_name, fontsize=11, fontweight="bold", pad=8)

    if not stage_dir.is_dir():
        ax.text(0.5, 0.5, "Directory not found",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="gray", style="italic")
        return

    if not _SLURM_AVAILABLE:
        ax.text(0.5, 0.5, "slurm_status module unavailable",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="gray", style="italic")
        return

    job_id = read_job_id(stage_dir / "logs")
    if job_id is None:
        ax.text(0.5, 0.5, "No job ID found\n(not yet submitted or logs/ missing)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="gray", style="italic")
        return

    task_states = get_task_states(job_id)
    ax.set_title(f"{stage_name}  (job {job_id})", fontsize=11, fontweight="bold", pad=8)

    if not task_states:
        ax.text(0.5, 0.5,
                f"Job {job_id} — no task data\n(off-cluster or job too old for sacct)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="gray", style="italic")
        return

    n_tasks = len(task_states)
    # When there are many tasks, show a summary table instead of individual rows
    if n_tasks > 30:
        counts: dict[str, int] = defaultdict(int)
        for state_raw, _ in task_states.values():
            counts[classify_state(state_raw)] += 1
        cell_text   = [[s, str(c)] for s, c in sorted(counts.items())]
        cell_colors = [[_rgba(_SLURM_HEX.get(s, "#7f7f7f")), _WHITE]
                       for s, _ in sorted(counts.items())]
        col_labels  = ["State", "Count"]
    else:
        cell_text   = []
        cell_colors = []
        for idx in sorted(task_states.keys()):
            state_raw, exitcode = task_states[idx]
            classified = classify_state(state_raw)
            cell_text.append([str(idx), classified,
                               exitcode if (exitcode and exitcode != "0:0") else ""])
            cell_colors.append([_WHITE, _rgba(_SLURM_HEX.get(classified, "#7f7f7f")), _WHITE])
        col_labels = ["Task", "State", "Exit"]

    tbl = ax.table(cellText=cell_text, colLabels=col_labels,
                   cellColours=cell_colors, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8 if n_tasks > 15 else 9)
    tbl.auto_set_column_width(list(range(len(col_labels))))


def _page_slurm_status(pdf: PdfPages, study_root: Path,
                       pdiv_db: str, plasma_sim: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 8.5))
    fig.suptitle("SLURM Job Status", fontsize=14, fontweight="bold")

    _slurm_table(axes[0], pdiv_db,    study_root / pdiv_db)
    _slurm_table(axes[1], plasma_sim,  study_root / plasma_sim)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 3: Plasma termination map
# ---------------------------------------------------------------------------

def _parse_aligned_csv(path: Path) -> list:
    """
    Read a fixed-width or tab-separated CSV (as written by GatherPlasmaEventLogs /
    ExtractInceptionVoltages).  Auto-detects the delimiter: uses ``\\t`` when tabs
    are present in the header line, otherwise falls back to splitting on two or more
    consecutive spaces.  Returns a list of dicts (empty on failure).
    """
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if not ln.startswith("#")]
    except OSError:
        return []
    if len(lines) < 2:
        return []

    def _split(line: str) -> list:
        if "\t" in line:
            return [x.strip() for x in line.split("\t") if x.strip()]
        return [x for x in re.split(r"  +", line.strip()) if x]

    header = _split(lines[0])
    return [
        dict(zip(header, _split(ln)))
        for ln in lines[1:]
        if ln.strip()
    ]


def _page_termination_map(pdf: PdfPages, plasma_sim: Path) -> None:
    """
    Scan ``plasma_sim/run_N/voltage_M/pout.0`` directly to build a per-voltage
    termination status table.  Columns: run, voltage, [outer params], [inner params],
    status.
    """
    o_keys, o_prefix, o_index, o_run_ids = _load_index(plasma_sim)
    if not o_run_ids:
        _placeholder_page(pdf, "Plasma Termination Map",
                          f"No index.json found in\n{plasma_sim}")
        return

    # Discover inner (voltage) keys from the first run that has an index
    i_keys: list = []
    for rid in o_run_ids:
        ik, _, _, _ = _load_index(plasma_sim / f"{o_prefix}{int(rid)}")
        if ik:
            i_keys = ik
            break

    rows = []
    for run_id in o_run_ids:
        run_dir     = plasma_sim / f"{o_prefix}{int(run_id)}"
        outer_vals  = o_index.get(run_id, [])
        if not isinstance(outer_vals, list):
            outer_vals = [outer_vals]
        outer_params = dict(zip(o_keys, outer_vals))

        ik, i_prefix, i_index, i_run_ids = _load_index(run_dir)

        if not i_run_ids:
            # Flat layout: pout.0 directly in run_dir
            status = _get_pout_status(run_dir / "pout.0")
            row = {"run": f"{o_prefix}{int(run_id)}", "voltage": "—"}
            row.update({k: _fmt_val(v) for k, v in outer_params.items()})
            row["status"] = status
            rows.append(row)
            continue

        for volt_id in i_run_ids:
            volt_dir    = run_dir / f"{i_prefix}{int(volt_id)}"
            inner_vals  = i_index.get(volt_id, [])
            if not isinstance(inner_vals, list):
                inner_vals = [inner_vals]
            inner_params = dict(zip(ik, inner_vals))

            status = _get_pout_status(volt_dir / "pout.0")
            row = {
                "run":     f"{o_prefix}{int(run_id)}",
                "voltage": f"{i_prefix}{int(volt_id)}",
            }
            row.update({k: _fmt_val(v) for k, v in outer_params.items()})
            row.update({k: _fmt_val(v) for k, v in inner_params.items()})
            row["status"] = status
            rows.append(row)

    if not rows:
        _placeholder_page(pdf, "Plasma Termination Map",
                          "No simulation directories found.")
        return

    # Build display column list (deduped, preserving order)
    seen: set = set()
    display_cols: list = []
    for col in ["run", "voltage"] + o_keys + i_keys + ["status"]:
        if col not in seen:
            seen.add(col)
            display_cols.append(col)

    cell_text   = [[str(r.get(c, "")) for c in display_cols] for r in rows]
    cell_colors = []
    status_idx  = display_cols.index("status")
    for r in rows:
        status = r.get("status", "not_found")
        row_colors = [_WHITE] * len(display_cols)
        row_colors[status_idx] = _rgba(_STATUS_HEX.get(status, "#7f7f7f"))
        cell_colors.append(row_colors)

    n_rows  = len(rows)
    fig_h   = max(4.5, min(22.0, 0.35 * n_rows + 2.5))
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.axis("off")
    ax.set_title("Plasma Termination Map", fontsize=14, fontweight="bold", pad=12)

    tbl = ax.table(
        cellText=cell_text,
        colLabels=display_cols,
        cellColours=cell_colors,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7 if n_rows > 25 else 9)
    tbl.auto_set_column_width(list(range(len(display_cols))))

    legend_patches = [
        Patch(facecolor=_rgba(c, 0.8), label=s)
        for s, c in _STATUS_HEX.items()
    ]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=8,
              bbox_to_anchor=(1.0, 1.05), ncol=len(legend_patches),
              framealpha=0.8)

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 4: ΔE(rel) vs K
# ---------------------------------------------------------------------------

def _read_peak_delta_e_csv(path: Path) -> list:
    """Read a peak_delta_e.csv file. Returns list of dicts (empty on failure)."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if not ln.startswith("#")]
        if not lines:
            return []
        header = re.split(r"  +", lines[0].strip())
        return [
            dict(zip(header, re.split(r"  +", ln.strip())))
            for ln in lines[1:]
            if ln.strip()
        ]
    except OSError:
        return []


def _page_delta_e_vs_k(pdf: PdfPages, plasma_results: Path,
                       run_ids: list, prefix: str,
                       plasma_params: dict) -> None:
    """
    One subplot per run_N.  Each subplot plots peak ΔE(rel) vs U [V] on the bottom
    x-axis with K values shown on a matching top x-axis, mirroring
    :func:`PlotDeltaE.plot_peak`.
    """
    # Collect (U, K, ΔE_rel) triples per run
    run_data: dict = {}
    for run_id in run_ids:
        csv_path = plasma_results / f"{prefix}{int(run_id)}" / "peak_delta_e.csv"
        pts = []
        for row in _read_peak_delta_e_csv(csv_path):
            try:
                u = float(row["U_V"])
                k = float(row.get("K", "nan"))
                y = float(row["peak_delta_e_rel_pct"])
                pts.append((u, k, y))
            except (ValueError, KeyError):
                pass
        if pts:
            run_data[run_id] = sorted(pts)  # sort by U

    if not run_data:
        _placeholder_page(pdf, "ΔE(rel) vs Voltage",
                          "No peak_delta_e.csv files found.")
        return

    n     = len(run_data)
    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(5 * ncols, 4.5 * nrows),
                             squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")

    for i, (run_id, pts) in enumerate(
            sorted(run_data.items(), key=lambda kv: int(kv[0]))):
        r, c = divmod(i, ncols)
        ax = axes[r][c]
        ax.axis("on")

        Us = [p[0] for p in pts]
        Ks = [p[1] for p in pts]
        ys = [p[2] for p in pts]

        ax.plot(Us, ys, marker="o", markersize=4, linewidth=1.2)
        ax.set_xlabel("$U$ [V]", fontsize=8)
        ax.set_ylabel("Peak $\\Delta E_\\mathrm{rel}$ [%]", fontsize=8)
        outer_params = plasma_params.get(run_id, {})
        title = f"{prefix}{int(run_id)}"
        if outer_params:
            title += "\n" + ", ".join(f"{k}={_fmt_val(v)}"
                                      for k, v in outer_params.items())
        ax.set_title(title, fontsize=8)
        ax.grid(True, linestyle=":", linewidth=0.5)
        ax.tick_params(labelsize=7)

        # Top x-axis: K values at matching U tick positions
        ax_top = ax.twiny()
        ax_top.set_xlim(ax.get_xlim())
        ax_top.set_xticks(Us)
        ax_top.set_xticklabels(
            [f"{k:.3g}" for k in Ks], rotation=45, ha="left", fontsize=6)
        ax_top.set_xlabel("$K$", fontsize=8)

    fig.suptitle("Peak ΔE(rel) vs Voltage", fontsize=12, fontweight="bold")
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _page_delta_e_vs_k_combined(pdf: PdfPages, plasma_results: Path,
                                  run_ids: list, prefix: str) -> None:
    """
    Single axes combining all runs — peak ΔE(rel) vs K, one curve per run,
    labelled by run number.
    """
    run_data: dict = {}
    for run_id in run_ids:
        csv_path = plasma_results / f"{prefix}{int(run_id)}" / "peak_delta_e.csv"
        pts = []
        for row in _read_peak_delta_e_csv(csv_path):
            try:
                k = float(row.get("K", "nan"))
                y = float(row["peak_delta_e_rel_pct"])
                if not (k != k):  # skip NaN K values
                    pts.append((k, y))
            except (ValueError, KeyError):
                pass
        if pts:
            run_data[run_id] = sorted(pts)  # sort by K

    if not run_data:
        _placeholder_page(pdf, "ΔE(rel) vs K — all runs",
                          "No peak_delta_e.csv files found.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for run_id in sorted(run_data, key=lambda r: int(r)):
        pts = run_data[run_id]
        Ks = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(Ks, ys, marker="o", markersize=4, linewidth=1.2,
                label=f"{prefix}{int(run_id)}")

    ax.set_xlabel("$K$", fontsize=10)
    ax.set_ylabel("Peak $\\Delta E_\\mathrm{rel}$ [%]", fontsize=10)
    ax.set_title("Peak ΔE(rel) vs K — all runs", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=":", linewidth=0.5)
    ax.tick_params(labelsize=8)

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 5: Time-series compact grid
# ---------------------------------------------------------------------------

def _collect_run_voltage_data(run_results_dir: Path,
                               inner_keys: list = None,
                               inner_index: dict = None,
                               inner_prefix: str = "") -> list:
    """
    Return a list of ``(volt_label, data_dict)`` for all ``pout.out`` files inside
    *run_results_dir*, one entry per voltage subdirectory.

    When *inner_keys* and *inner_index* are supplied the label for each voltage
    entry is formatted as ``"key=val, ..."`` from the actual parameter values rather
    than the bare subdirectory name.

    Voltage subdirectories are discovered by globbing ``*/pout.out``.  Falls back
    to a single ``pout.out`` directly in *run_results_dir* when no subdirectories
    are present.  Entries with no usable data are silently dropped.
    """
    if not _ATS_AVAILABLE:
        return []
    entries = []
    nested = sorted(run_results_dir.glob("*/pout.out"))
    sources = [(p.parent.name, p) for p in nested] if nested else [
        (run_results_dir.name, run_results_dir / "pout.out")
    ]
    for subdir_name, dat_path in sources:
        if not dat_path.exists():
            continue
        d = _read_dat(dat_path)
        if not d or "Time" not in d:
            continue
        # Build a human-readable label from inner parameter values when available
        label = subdir_name
        if inner_keys and inner_index and inner_prefix:
            if subdir_name.startswith(inner_prefix):
                volt_id_str = subdir_name[len(inner_prefix):]
                vals = inner_index.get(volt_id_str)
                if vals is not None:
                    if not isinstance(vals, list):
                        vals = [vals]
                    label = ", ".join(
                        f"{k}={_fmt_val(v)}" for k, v in zip(inner_keys, vals)
                    )
        entries.append((label, d))
    return entries


def _page_timeseries_grid(pdf: PdfPages, plasma_results: Path,
                          run_ids: list, prefix: str,
                          plasma_params: dict) -> None:
    """Compact overview: one subplot per run_N, all voltage curves overlaid."""
    if not _ATS_AVAILABLE:
        _placeholder_page(pdf, "Time Series — Compact Grid",
                          "AnalyzeTimeSeries module not available.")
        return

    # Collect per-run data: [(title_str, [(volt_label, data), ...]), ...]
    run_data = []
    for run_id in run_ids:
        run_label    = f"{prefix}{int(run_id)}"
        outer_params = plasma_params.get(run_id, {})
        title = run_label
        if outer_params:
            title += "\n" + ", ".join(f"{k}={_fmt_val(v)}"
                                      for k, v in outer_params.items())
        # Curve labels use bare subdirectory names (voltage_0, voltage_1, …)
        volt_data = _collect_run_voltage_data(plasma_results / run_label)
        if volt_data:
            run_data.append((title, volt_data))

    if not run_data:
        _placeholder_page(pdf, "Time Series — Compact Grid",
                          "No pout.out files found.")
        return

    ncols = min(4, len(run_data))
    nrows = (len(run_data) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(4 * ncols, 4 * nrows),
                             squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")

    for i, (title, volt_data) in enumerate(run_data):
        r, c = divmod(i, ncols)
        ax = axes[r][c]
        ax.axis("on")
        for volt_label, d in volt_data:
            t = d["Time"]
            ax.plot(t, d["Delta E(rel)"], linewidth=0.9, label=volt_label)
        ax.set_title(title, fontsize=7)
        ax.set_xlabel("Time", fontsize=7)
        ax.set_ylabel("ΔE(rel) [%]", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, linestyle=":", linewidth=0.4)
        if len(volt_data) > 1:
            ax.legend(fontsize=5, ncol=1)

    fig.suptitle("Time Series — Compact Overview", fontsize=12, fontweight="bold")
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page N+1: PDIV inception voltages
# ---------------------------------------------------------------------------

def _plot_pdiv_xarray(pdf: PdfPages, nc_path: Path, pdiv_keys: list) -> None:
    """Render PDIV voltage page from a NetCDF dataset (requires xarray)."""
    if not _XARRAY_AVAILABLE:
        _placeholder_page(pdf, "PDIV Inception Voltages",
                          "xarray not installed — cannot read .nc file.")
        return
    try:
        ds = xr.open_dataset(nc_path)
    except Exception as exc:
        _placeholder_page(pdf, "PDIV Inception Voltages",
                          f"Could not open {nc_path}:\n{exc}")
        return

    coords = list(ds.coords)
    if not coords:
        ds.close()
        _placeholder_page(pdf, "PDIV Inception Voltages",
                          "Dataset has no coordinate dimensions.")
        return

    sweep_param = coords[0]
    x = ds.coords[sweep_param].values

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle("PDIV Inception Voltages", fontsize=13, fontweight="bold")

    for ax, (title, pos_var, neg_var) in zip(axes, _VOLTAGE_TYPES):
        if pos_var in ds:
            ax.plot(x, ds[pos_var].values, marker="o", label="pos (+)")
        if neg_var in ds:
            ax.plot(x, ds[neg_var].values, marker="s", linestyle="--", label="neg (−)")
        ax.set_title(title)
        ax.set_xlabel(sweep_param)
        ax.set_ylabel("Voltage [V]")
        ax.legend(fontsize=8)
        ax.grid(True, linestyle=":", linewidth=0.5)

    ds.close()
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _plot_pdiv_csv(pdf: PdfPages, csv_path: Path, pdiv_keys: list) -> None:
    """Render PDIV voltage page from a CSV fallback file."""
    rows = _parse_aligned_csv(csv_path)
    if not rows:
        _placeholder_page(pdf, "PDIV Inception Voltages",
                          f"inception_voltages.csv is empty or unreadable.")
        return

    all_keys = list(rows[0].keys())
    # Determine sweep parameter: prefer pdiv_keys[0], else first non-voltage column
    sweep_param = None
    if pdiv_keys:
        for k in pdiv_keys:
            if k in rows[0]:
                sweep_param = k
                break
    if sweep_param is None:
        non_volt = [k for k in all_keys if k not in _VOLTAGE_VARS]
        sweep_param = non_volt[0] if non_volt else None

    if sweep_param is None:
        _placeholder_page(pdf, "PDIV Inception Voltages",
                          "Cannot determine sweep parameter from CSV header.")
        return

    x_vals = []
    for row in rows:
        try:
            x_vals.append(float(row[sweep_param]))
        except (ValueError, KeyError):
            x_vals.append(float("nan"))

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle("PDIV Inception Voltages", fontsize=13, fontweight="bold")

    for ax, (title, pos_var, neg_var) in zip(axes, _VOLTAGE_TYPES):
        for var, label, style in [(pos_var, "pos (+)", "-"), (neg_var, "neg (−)", "--")]:
            if var in rows[0]:
                ys = []
                for row in rows:
                    try:
                        ys.append(float(row[var]))
                    except (ValueError, KeyError):
                        ys.append(float("nan"))
                ax.plot(x_vals, ys, marker="o", linestyle=style, label=label)
        ax.set_title(title)
        ax.set_xlabel(sweep_param)
        ax.set_ylabel("Voltage [V]")
        ax.legend(fontsize=8)
        ax.grid(True, linestyle=":", linewidth=0.5)

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _page_pdiv_voltages(pdf: PdfPages, pdiv_results: Path,
                        pdiv_keys: list) -> None:
    nc_path  = pdiv_results / "inception_voltages.nc"
    csv_path = pdiv_results / "inception_voltages.csv"

    if nc_path.exists():
        _plot_pdiv_xarray(pdf, nc_path, pdiv_keys)
        return
    if csv_path.exists():
        _plot_pdiv_csv(pdf, csv_path, pdiv_keys)
        return

    _placeholder_page(pdf, "PDIV Inception Voltages",
                      "No inception_voltages.nc or inception_voltages.csv found.")


# ---------------------------------------------------------------------------
# Metadata helper
# ---------------------------------------------------------------------------

def _load_index(study_dir: Path) -> tuple:
    """Load ``index.json`` from *study_dir*. Returns (keys, prefix, run_index, sorted_ids)."""
    index_path = study_dir / "index.json"
    if not index_path.exists():
        return [], "run_", {}, []
    try:
        with open(index_path) as f:
            idx = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], "run_", {}, []
    keys      = idx.get("keys") or idx.get("key") or []
    prefix    = idx.get("prefix", "run_")
    run_index = idx.get("index", {})
    sorted_ids = sorted(run_index.keys(), key=int)
    return keys, prefix, run_index, sorted_ids


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(args) -> None:
    """Build the overview PDF given a pre-parsed :class:`argparse.Namespace`."""
    study_root    = Path(args.study_root).resolve()
    pdiv_db       = study_root / args.pdiv_db
    plasma_sim    = study_root / args.plasma_sim
    pdiv_results  = study_root / "Results" / args.pdiv_db
    plasma_results = study_root / "Results" / args.plasma_sim
    output = (Path(args.output) if args.output
              else study_root / "Results" / "overview_report.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)

    matplotlib.rcParams["figure.dpi"] = args.dpi

    # Metadata
    pdiv_keys,   _, pdiv_index,   _             = _load_index(pdiv_db)
    plasma_keys, plasma_prefix, plasma_index, plasma_run_ids = _load_index(plasma_sim)
    pdiv_runs   = len(pdiv_index)
    plasma_runs = len(plasma_index)

    # Per-run parameter maps for detail pages
    plasma_params: dict = {}
    for run_id, vals in plasma_index.items():
        if isinstance(vals, list):
            plasma_params[run_id] = dict(zip(plasma_keys, vals))
        else:
            plasma_params[run_id] = {}

    print(f"[overview-report] writing PDF → {output}")
    with PdfPages(str(output)) as pdf:
        # Page 1: Cover
        _page_cover(pdf, study_root, plasma_runs, pdiv_runs, plasma_keys, pdiv_keys)

        # Page 2: SLURM status
        _page_slurm_status(pdf, study_root, args.pdiv_db, args.plasma_sim)

        # Page 3: Plasma termination map (scans run_N/voltage_M/pout.0 directly)
        _page_termination_map(pdf, plasma_sim)

        # Page 4: ΔE(rel) vs Voltage — one panel per run_N
        _page_delta_e_vs_k(pdf, plasma_results, plasma_run_ids, plasma_prefix,
                           plasma_params)

        # Page 4b: ΔE(rel) vs K — all runs on one graph
        _page_delta_e_vs_k_combined(pdf, plasma_results, plasma_run_ids,
                                     plasma_prefix)

        # Page 5: Time-series compact grid — one subplot per run_N
        _page_timeseries_grid(pdf, plasma_results,
                              plasma_run_ids, plasma_prefix, plasma_params)

        # Page N+1: PDIV inception voltages
        _page_pdiv_voltages(pdf, pdiv_results, pdiv_keys)

    print(f"[overview-report] done — {output}")


def make_parser(add_help: bool = True) -> argparse.ArgumentParser:
    """Return the configured argument parser (separated from main() for CLI reuse)."""
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description=(
            "Generate a multi-page PDF overview report for an inception study. "
            "Output: <study_root>/Results/overview_report.pdf"
        ),
    )
    ap.add_argument(
        "study_root", type=Path,
        help="Top-level study directory.",
    )
    ap.add_argument(
        "--pdiv-db", default="pdiv_database", metavar="DIRNAME",
        help="Subdirectory name of the pdiv database (default: pdiv_database).",
    )
    ap.add_argument(
        "--plasma-sim", default="plasma_simulations", metavar="DIRNAME",
        help="Subdirectory name of the plasma simulations (default: plasma_simulations).",
    )
    ap.add_argument(
        "--output", default=None, metavar="FILE",
        help="Output PDF path (default: <study_root>/Results/overview_report.pdf).",
    )
    ap.add_argument(
        "--dpi", type=int, default=150,
        help="Figure DPI (default: 150).",
    )
    return ap


def main() -> None:
    """Parse command-line arguments and build the overview report."""
    run(make_parser().parse_args())


if __name__ == "__main__":
    main()
