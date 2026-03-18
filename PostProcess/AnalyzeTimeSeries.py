#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyse time-series data from a block-wise ASCII plasma simulation log (``pout.0``).

The script reads every ``Driver::Time step report`` block from the log, extracts
eight physical fields, optionally smooths the energy and charge columns with a
Savitzky–Golay filter, computes ohmic and electrode currents as finite-difference
derivatives of the corresponding charge columns, optionally low-pass filters those
derivatives with a bidirectional exponential moving average, writes the results to
an aligned 10-column ``.dat`` file with a commented column header, and displays a
2 × 4 Matplotlib figure of all derived quantities vs time.

Usage::

    python AnalyzeTimeSeries.py [options]

See ``--help`` for the full option list.

Output columns
--------------
  1. Time
  2. dt
  3. Delta E(max)          (Savitzky–Golay smoothed if ``--sg``)
  4. Delta E(rel)          (Savitzky–Golay smoothed if ``--sg``)
  5. Q (ohmic)             (Savitzky–Golay smoothed if ``--sg``)
  6. Q (electrode)         (Savitzky–Golay smoothed if ``--sg``)
  7. Sum (phi_optical)
  8. Sum (src_optical)
  9. I (ohmic)             dQ_ohmic/dt  (low-pass filtered if ``--lp``)
 10. I (electrode)         dQ_electrode/dt  (low-pass filtered if ``--lp``)

Authors:
    André Kapelrud, Robert Marskar

Copyright © 2026 SINTEF Energi AS
"""

import argparse
import math
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---- Optional SciPy import (only needed if --sg is used) ----
def _import_savgol():
    """Import and return ``scipy.signal.savgol_filter``, exiting with an error if unavailable."""
    try:
        from scipy.signal import savgol_filter
        return savgol_filter
    except Exception:
        print("Error: Savitzky–Golay smoothing requested (--sg) but SciPy is not available.", file=sys.stderr)
        print("Install SciPy or run without --sg.", file=sys.stderr)
        sys.exit(1)

# --------- Regex patterns ----------
NUM = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'

# Keys match the log labels (with spaces exactly as in the new input)
PATTERNS = {
    "Time": re.compile(rf'^\s*Time\s*=\s*(?P<val>{NUM})'),
    "dt": re.compile(rf'^\s*dt\s*=\s*(?P<val>{NUM})'),
    "Delta E(max)": re.compile(rf'^\s*Delta\s*E\(max\)\s*=\s*(?P<val>{NUM})'),
    "Delta E(rel)": re.compile(rf'^\s*Delta\s*E\(rel\)\s*=\s*(?P<val>{NUM})'),
    "Q (ohmic)": re.compile(rf'^\s*Q\s*\(\s*ohmic\s*\)\s*=\s*(?P<val>{NUM})'),
    "Q (electrode)": re.compile(rf'^\s*Q\s*\(\s*electrode\s*\)\s*=\s*(?P<val>{NUM})'),
    "Sum (phi_optical)": re.compile(rf'^\s*Sum\s*\(\s*phi_optical\s*\)\s*=\s*(?P<val>{NUM})'),
    "Sum (src_optical)": re.compile(rf'^\s*Sum\s*\(\s*src_optical\s*\)\s*=\s*(?P<val>{NUM})'),
}

# Output column order (matches requirements)
FIELDS = [
    "Time",
    "dt",
    "Delta E(max)",
    "Delta E(rel)",
    "Q (ohmic)",
    "Q (electrode)",
    "Sum (phi_optical)",
    "Sum (src_optical)",
    "I (ohmic)",
    "I (electrode)",
]

BLOCK_START = re.compile(r'^\s*Driver::Time step report\b')

COMMENT_HEADER = [
    "# Data is organized as follows:",
    "# Column 1:  Time",
    "# Column 2:  Time step (dt)",
    "# Column 3:  Delta E(max) %          (Savitzky–Golay smoothed if --sg)",
    "# Column 4:  Delta E(rel) %          (Savitzky–Golay smoothed if --sg)",
    "# Column 5:  Q (ohmic)               (Savitzky–Golay smoothed if --sg)",
    "# Column 6:  Q (electrode)           (Savitzky–Golay smoothed if --sg)",
    "# Column 7:  Sum (phi_optical)",
    "# Column 8:  Sum (src_optical)",
    "# Column 9:  I (ohmic)               (from Column 5; low-pass if --lp)",
    "# Column 10: I (electrode)           (from Column 6; low-pass if --lp)",
]

# ---------- Parsing ----------
def parse_file(in_path: str) -> List[Dict[str, float]]:
    """
    Parse a block-wise ASCII simulation log and return one record per time step.

    Each block starts with a ``Driver::Time step report`` sentinel line.  Within
    a block the function matches every line against the compiled ``PATTERNS`` dict
    and records the named floating-point values.  Incomplete blocks (e.g. the last
    block in a still-running simulation) are included as long as they contain at
    least one recognised field.

    Parameters
    ----------
    in_path : str
        Path to the input ASCII log file (typically ``pout.0``).

    Returns
    -------
    list of dict
        One dict per block; keys are a subset of ``PATTERNS`` keys, values are
        floats.  Missing fields are simply absent from the dict.
    """
    rows: List[Dict[str, float]] = []
    current: Dict[str, float] = {}

    def flush_current():
        nonlocal current
        if current:
            rows.append(current)
            current = {}

    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if BLOCK_START.search(line):
                flush_current()
                continue
            if PATTERNS["Time"].search(line) and "Time" in current:
                flush_current()
            for key, pat in PATTERNS.items():
                m = pat.search(line)
                if m:
                    try:
                        current[key] = float(m.group("val"))
                    except ValueError:
                        pass
                    break

    flush_current()
    return rows

# ---------- Utility: Savitzky–Golay smoothing with NaN handling ----------
def _odd_leq(n: int) -> int:
    """Return *n* if it is odd, otherwise return the next smaller odd integer (≥ 1)."""
    return n if n % 2 == 1 else max(1, n - 1)

def _choose_window(n: int, req_window: int, polyorder: int) -> Optional[int]:
    """
    Choose a valid Savitzky–Golay window length given the series length and polynomial order.

    Parameters
    ----------
    n : int
        Number of data points.
    req_window : int
        Requested window length (will be capped and made odd as needed).
    polyorder : int
        Polynomial order; window must be strictly greater than this value.

    Returns
    -------
    int or None
        A valid odd window length, or ``None`` if no valid window exists for the
        given *n* and *polyorder*.
    """
    if n <= polyorder:
        return None
    W = min(req_window, n)
    W = _odd_leq(W)
    if W <= polyorder:
        W = polyorder + 1 if (polyorder + 1) % 2 == 1 else polyorder + 2
        if W > n:
            return None
    return W

def savgol_smooth_with_nans(x: List[Optional[float]],
                            window_length: int,
                            polyorder: int) -> List[Optional[float]]:
    """
    Apply a Savitzky–Golay filter to *x*, tolerating ``None`` and ``NaN`` values.

    Non-finite positions are linearly interpolated before filtering and then
    restored to ``NaN`` in the output so that gaps are preserved.  If the series
    is too short or contains too few finite values to support the requested
    filter, the raw (unsmoothed) finite values are returned unchanged.

    Parameters
    ----------
    x : list of float or None
        Input signal, may contain ``None`` or ``NaN`` entries.
    window_length : int
        Desired Savitzky–Golay window (will be adjusted to be odd and ≤ ``len(x)``).
    polyorder : int
        Polynomial order for the Savitzky–Golay fit.

    Returns
    -------
    list of float or None
        Smoothed signal of the same length as *x*; ``NaN`` where input was non-finite.
    """
    arr = np.asarray(x, dtype=float)
    n = arr.size
    if n == 0:
        return x
    valid = np.isfinite(arr)
    n_valid = int(valid.sum())
    if n_valid <= polyorder:
        return [float('nan') if not np.isfinite(v) else v for v in arr]

    W = _choose_window(n, window_length, polyorder)
    if W is None or W < 3:
        return [float('nan') if not np.isfinite(v) else v for v in arr]

    idx = np.arange(n)
    arr_filled = np.interp(idx, idx[valid], arr[valid]) if n_valid < n else arr

    savgol_filter = _import_savgol()
    try:
        smoothed = savgol_filter(arr_filled, window_length=W, polyorder=polyorder, mode="interp")
    except Exception:
        smoothed = arr_filled

    smoothed[~valid] = np.nan
    return smoothed.tolist()

# ---------- Derivative (finite differences) ----------
def _safe_sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Return ``a - b``, or ``None`` if either operand is ``None``."""
    if a is None or b is None:
        return None
    return a - b

def _safe_div(num: Optional[float], denom: Optional[float]) -> Optional[float]:
    """
    Return ``num / denom``, or ``None`` if either operand is ``None``, non-finite,
    or if *denom* is zero.
    """
    if num is None or denom is None:
        return None
    if not (math.isfinite(num) and math.isfinite(denom) and denom != 0.0):
        return None
    return num / denom

def compute_derivative(values: List[Optional[float]],
                       times: List[Optional[float]],
                       dts: List[Optional[float]]) -> List[float]:
    """
    Compute the time derivative of *values* using finite differences.

    Central differences are used for interior points; one-sided (forward/backward)
    differences are used at the boundaries.  If the time difference between
    adjacent points cannot be determined from *times*, the corresponding entry in
    *dts* is used as a fallback.  Non-finite or missing values produce ``NaN`` in
    the output.

    Parameters
    ----------
    values : list of float or None
        The signal to differentiate (e.g. Q (ohmic)).
    times : list of float or None
        Simulation time at each sample.
    dts : list of float or None
        Reported time-step size at each sample (fallback when ``times`` differ by
        zero or are unavailable).

    Returns
    -------
    list of float
        Derivative ``dvalue/dt`` at each sample; ``NaN`` where the derivative
        cannot be computed.
    """
    n = len(values)
    out = [float('nan')] * n
    if n == 0:
        return out

    def delta_t(i: int, j: int, prefer_dt_index: Optional[int] = None) -> Optional[float]:
        if not (0 <= i < n and 0 <= j < n):
            return None
        ti, tj = times[i], times[j]
        if ti is not None and tj is not None:
            dt_val = ti - tj
            if math.isfinite(dt_val) and dt_val != 0.0:
                return dt_val
        if prefer_dt_index is not None:
            dt_alt = dts[prefer_dt_index]
            if math.isfinite(dt_alt) and dt_alt > 0.0:
                return dt_alt
        return None

    for i in range(n):
        vi = values[i]
        if vi is None or not math.isfinite(vi):
            out[i] = float('nan')
            continue

        d = None
        if n == 1:
            d = None
        elif i == 0:
            num = _safe_sub(values[1], values[0])
            denom = delta_t(1, 0, prefer_dt_index=0)
            d = _safe_div(num, denom)
        elif i == n - 1:
            num = _safe_sub(values[n - 1], values[n - 2])
            denom = delta_t(n - 1, n - 2, prefer_dt_index=n - 1)
            d = _safe_div(num, denom)
        else:
            num = _safe_sub(values[i + 1], values[i - 1])
            denom = delta_t(i + 1, i - 1)
            d = _safe_div(num, denom)
            if d is None:
                num = _safe_sub(values[i], values[i - 1])
                denom = delta_t(i, i - 1, prefer_dt_index=i)
                d = _safe_div(num, denom)

        out[i] = d if d is not None else float('nan')
    return out

# ---------- Low-pass filter: bidirectional exponential (handles nonuniform Δt) ----------
def _segments_finite(x: np.ndarray, t: np.ndarray) -> List[Tuple[int, int]]:
    """
    Return the index ranges of contiguous finite segments in *x* and *t*.

    Parameters
    ----------
    x : np.ndarray
        Signal array.
    t : np.ndarray
        Time array of the same length.

    Returns
    -------
    list of (int, int)
        Each tuple ``(start, end)`` is the inclusive index range of a contiguous
        segment where both ``x`` and ``t`` are finite.
    """
    finite = np.isfinite(x) & np.isfinite(t)
    if not finite.any():
        return []
    segs = []
    n = len(x)
    i = 0
    while i < n:
        if not finite[i]:
            i += 1
            continue
        s = i
        while i + 1 < n and finite[i + 1]:
            i += 1
        e = i
        segs.append((s, e))
        i += 1
    return segs

def lowpass_ema_bidirectional(values: List[Optional[float]],
                              times: List[Optional[float]],
                              tau: float) -> List[float]:
    """
    Apply a bidirectional exponential moving average (EMA) low-pass filter.

    A forward EMA pass followed by a backward EMA pass are averaged to give
    zero-phase filtering.  The per-step smoothing coefficient is computed as
    ``alpha = 1 - exp(-dt/tau)`` so that the filter adapts correctly to
    non-uniform time steps.  Each contiguous finite segment is filtered
    independently; ``NaN`` gaps between segments are preserved.

    Parameters
    ----------
    values : list of float or None
        Input signal (e.g. ``I (ohmic)``).
    times : list of float or None
        Simulation time at each sample.
    tau : float
        EMA time constant in the same units as *times*.  Must be positive and
        finite; if not, the input is returned unchanged.

    Returns
    -------
    list of float
        Filtered signal of the same length as *values*.
    """
    if tau is None or not math.isfinite(tau) or tau <= 0.0:
        return [float(v) if (isinstance(v, (int, float)) and math.isfinite(v)) else float('nan') for v in values]

    x = np.asarray(values, dtype=float)
    t = np.asarray(times, dtype=float)
    n = x.size
    y = np.full(n, np.nan, dtype=float)

    for s, e in _segments_finite(x, t):
        xs = x[s:e+1].copy()
        ts = t[s:e+1].copy()
        m = e - s + 1
        if m == 1:
            y[s] = xs[0]
            continue

        fwd = np.empty_like(xs)
        fwd[0] = xs[0]
        for i in range(1, m):
            dt = ts[i] - ts[i - 1]
            alpha = 1.0 if (not math.isfinite(dt) or dt <= 0.0) else (1.0 - math.exp(-dt / tau))
            fwd[i] = (1.0 - alpha) * fwd[i - 1] + alpha * xs[i]

        bwd = np.empty_like(xs)
        bwd[-1] = xs[-1]
        for i in range(m - 2, -1, -1):
            dt = ts[i + 1] - ts[i]
            alpha = 1.0 if (not math.isfinite(dt) or dt <= 0.0) else (1.0 - math.exp(-dt / tau))
            bwd[i] = (1.0 - alpha) * bwd[i + 1] + alpha * xs[i]

        y[s:e+1] = 0.5 * (fwd + bwd)

    return y.tolist()

# ---------- Writer (aligned, scientific) ----------
def write_dat_aligned_with_comments(out_path: str,
                                    rows: List[Dict[str, float]],
                                    use_sg: bool,
                                    sg_window: int,
                                    sg_order: int,
                                    use_lp: bool,
                                    lp_tau: Optional[float],
                                    col_gap: int = 2):
    """
    Apply all post-processing steps and write the 10-column ``.dat`` output file.

    Processing order:

    1. Extract the eight raw columns from *rows*.
    2. Optionally smooth columns 3–6 (Delta E and Q) with Savitzky–Golay.
    3. Compute currents I (ohmic) and I (electrode) as ``dQ/dt``.
    4. Optionally low-pass filter the current columns with a bidirectional EMA.
    5. Format all values in scientific notation and write an aligned file with
       the ``COMMENT_HEADER`` prepended.

    Parameters
    ----------
    out_path : str
        Destination ``.dat`` file path.
    rows : list of dict
        Parsed time-step records as returned by :func:`parse_file`.
    use_sg : bool
        Apply Savitzky–Golay smoothing to columns 3–6.
    sg_window : int
        Savitzky–Golay window length (adjusted internally to be odd and valid).
    sg_order : int
        Savitzky–Golay polynomial order.
    use_lp : bool
        Apply bidirectional EMA low-pass filter to the derivative columns.
    lp_tau : float or None
        EMA time constant (seconds).  Required when *use_lp* is ``True``.
    col_gap : int
        Number of spaces between adjacent columns (default: 2).

    Returns
    -------
    dict
        Mapping of column name → ``np.ndarray`` for all columns, suitable for
        passing directly to :func:`plot_2x4`.
    """
    # Collect raw arrays
    T   = [rec.get("Time") for rec in rows]
    dT  = [rec.get("dt") for rec in rows]
    Emax = [rec.get("Delta E(max)") for rec in rows]
    Erel = [rec.get("Delta E(rel)") for rec in rows]
    Qo   = [rec.get("Q (ohmic)") for rec in rows]
    Qe   = [rec.get("Q (electrode)") for rec in rows]
    Sphi = [rec.get("Sum (phi_optical)") for rec in rows]
    Ssrc = [rec.get("Sum (src_optical)") for rec in rows]

    # Optional Savitzky–Golay smoothing on columns 3–6 (E and Q only)
    if use_sg:
        Emax_s = savgol_smooth_with_nans(Emax, sg_window, sg_order)
        Erel_s = savgol_smooth_with_nans(Erel, sg_window, sg_order)
        Qo_s   = savgol_smooth_with_nans(Qo,   sg_window, sg_order)
        Qe_s   = savgol_smooth_with_nans(Qe,   sg_window, sg_order)
    else:
        Emax_s, Erel_s, Qo_s, Qe_s = Emax, Erel, Qo, Qe

    # Derivatives (columns 9–10) follow the Q order: ohmic, electrode
    dQo_dt = compute_derivative(Qo_s, T, dT)
    dQe_dt = compute_derivative(Qe_s, T, dT)

    if use_lp:
        dQo_dt = lowpass_ema_bidirectional(dQo_dt, T, lp_tau)
        dQe_dt = lowpass_ema_bidirectional(dQe_dt, T, lp_tau)

    # Compose output rows in the exact order of FIELDS
    rows_data: List[List[Optional[float]]] = []
    for i, _ in enumerate(rows):
        rows_data.append([
            T[i],
            dT[i],
            Emax_s[i],
            Erel_s[i],
            Qo_s[i],
            Qe_s[i],
            Sphi[i],
            Ssrc[i],
            dQo_dt[i],
            dQe_dt[i],
        ])

    # Format and write
    formatted_rows: List[List[str]] = []
    for vals in rows_data:
        svals = []
        for v in vals:
            if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
                svals.append("nan")
            else:
                svals.append(f"{v:.8e}")
        formatted_rows.append(svals)

    widths = []
    for j in range(len(FIELDS)):
        max_len = max((len(r[j]) for r in formatted_rows), default=3)
        widths.append(max_len)

    sep = " " * col_gap
    with open(out_path, "w", encoding="utf-8") as g:
        for line in COMMENT_HEADER:
            g.write(line + "\n")
        g.write("\n")
        for r in formatted_rows:
            g.write(sep.join(f"{val:>{w}}" for val, w in zip(r, widths)) + "\n")

    # Return arrays needed for plotting
    return {
        "Time": np.array(T, dtype=float),
        "Delta E(max)": np.array(Emax_s, dtype=float),
        "Delta E(rel)": np.array(Erel_s, dtype=float),
        "Q (ohmic)": np.array(Qo_s, dtype=float),
        "Q (electrode)": np.array(Qe_s, dtype=float),
        "Sum (phi_optical)": np.array(Sphi, dtype=float),
        "Sum (src_optical)": np.array(Ssrc, dtype=float),
        "I (ohmic)": np.array(dQo_dt, dtype=float),
        "I (electrode)": np.array(dQe_dt, dtype=float),
    }

# ---------- Plotting ----------
def plot_2x4(time: np.ndarray, series: Dict[str, np.ndarray]) -> None:
    """
    Display a 2 × 4 Matplotlib figure of all derived quantities vs simulation time.

    Each subplot corresponds to one output column (columns 3–10).  All panels
    share the x-axis.  The two optical-sum columns (7 and 8) use a logarithmic
    y-axis; all others use a linear scale.  If ``matplotlib`` is not available a
    warning is printed and the function returns without error.

    Parameters
    ----------
    time : np.ndarray
        1-D array of simulation times (column 1 of the output).
    series : dict
        Mapping of column name → ``np.ndarray``.  Must contain keys
        ``"Delta E(max)"``, ``"Delta E(rel)"``, ``"Q (ohmic)"``,
        ``"Q (electrode)"``, ``"Sum (phi_optical)"``, ``"Sum (src_optical)"``,
        ``"I (ohmic)"``, and ``"I (electrode)"``.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"Warning: matplotlib not available ({e}). Skipping plots.", file=sys.stderr)
        return

    # Order and labels correspond to output columns 3..10
    labels = [
        "Delta E(max)",
        "Delta E(rel)",
        "Q (ohmic)",
        "Q (electrode)",
        "Sum (phi_optical)",
        "Sum (src_optical)",
        "I (ohmic)",
        "I (electrode)",
    ]

    # Units for y-axis labels (per your specification)
    units = {
        "Delta E(max)": "%",
        "Delta E(rel)": "%",
        "Q (ohmic)": "(C",
        "Q (electrode)": "C",
        "Sum (phi_optical)": "1",
        "Sum (src_optical)": "1/s",
        "I (ohmic)": "A",
        "I (electrode)": "A",
    }

    fig, axes = plt.subplots(2, 4, figsize=(24, 12), sharex=True)
    axes = axes.ravel()

    # Same style for all — no markers
    line_kwargs = dict(linestyle='-', linewidth=1.5)

    for ax, lab in zip(axes, labels):
        y = np.asarray(series[lab], dtype=float)

        # Columns 7 & 8 (Sum ...) should be in log-scale
        if lab in ("Sum (phi_optical)", "Sum (src_optical)"):
            # avoid log of non-positive values
            y_plot = np.where(y > 0, y, np.nan)
            ax.set_yscale('log')
        else:
            y_plot = y

        ax.plot(time, y_plot, **line_kwargs)
        ax.set_ylabel(f"{lab} [{units[lab]}]")
        ax.grid(True, which='both', linestyle=':', linewidth=0.5)

    for ax in axes[4:]:
        ax.set_xlabel("Time")

    fig.tight_layout()
    plt.show()

# ---------- Read .dat output ----------

def read_dat(path) -> dict:
    """
    Load a ``.dat`` file written by :func:`write_dat_aligned_with_comments` into a
    dict of numpy arrays.

    Column names are taken from the module-level :data:`FIELDS` list, which defines
    the fixed column order for all files produced by this module.

    Parameters
    ----------
    path : str or Path
        Path to the ``.dat`` file (``pout.out`` by convention).

    Returns
    -------
    dict mapping column name → ``np.ndarray``
        One entry per column present in the file.  Returns an empty dict if the
        file cannot be read or contains no numeric rows.
    """
    try:
        data = np.loadtxt(str(path), comments='#')
    except (OSError, ValueError):
        return {}
    if data.ndim == 0:
        return {}
    if data.ndim == 1:
        # Single row: reshape to (1, ncols)
        data = data.reshape(1, -1)
    n_cols = data.shape[1]
    return {FIELDS[i]: data[:, i] for i in range(min(n_cols, len(FIELDS)))}


# ---------- Main ----------

def make_parser(add_help=True) -> argparse.ArgumentParser:
    """Return the configured argument parser (separated from main() for CLI reuse)."""
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description="Extract, (optionally) smooth, differentiate, and (optionally) low-pass filter; write aligned .dat with commented header; then plot."
    )
    # (1) -i no longer required; default to pout.0
    ap.add_argument("-i", "--input", help="Path to the input ASCII log file", default="pout.0")
    ap.add_argument("-o", "--output", help="Path to the output .dat file", default="pout.out")

    # Savitzky–Golay options (columns 3–6)
    ap.add_argument("--sg", action="store_true", help="Apply Savitzky–Golay smoothing to columns 3–6 before derivatives")
    ap.add_argument("--sg-window", type=int, default=9, help="Savitzky–Golay window length (odd; reduced if needed)")
    ap.add_argument("--sg-order", type=int, default=3, help="Savitzky–Golay polynomial order (< window)")

    # Low-pass on derivatives (columns 9–10)
    ap.add_argument("--lp", action="store_true", help="Apply low-pass filter to derivative columns 9–10")
    ap.add_argument("--lp-tau", type=float, default=None, help="Low-pass time constant τ (seconds) for bidirectional EMA")

    return ap


def run(args) -> None:
    """Execute the pipeline given a pre-parsed Namespace."""
    in_path = args.input
    if not os.path.isfile(in_path):
        print(f"Error: input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out_path = args.output
    else:
        from discharge_inception.results import ensure_results_dir, link_metadata
        input_path = Path(in_path)
        results_dir = ensure_results_dir(input_path)
        out_path = str(results_dir / 'pout.out')
        link_metadata(input_path.parent, results_dir)

    rows = parse_file(in_path)
    if not rows:
        print("Warning: no records found. Check that the input contains the expected fields.", file=sys.stderr)

    if args.lp and (args.lp_tau is None or not math.isfinite(args.lp_tau) or args.lp_tau <= 0.0):
        print("Error: --lp requires a positive --lp-tau (seconds).", file=sys.stderr)
        sys.exit(1)
    if args.sg and args.sg_order >= args.sg_window:
        print("Error: --sg-order must be < --sg-window.", file=sys.stderr)
        sys.exit(1)

    series = write_dat_aligned_with_comments(
        out_path=out_path,
        rows=rows,
        use_sg=args.sg,
        sg_window=args.sg_window,
        sg_order=args.sg_order,
        use_lp=args.lp,
        lp_tau=args.lp_tau,
    )
    print(f"Wrote {len(rows)} rows to: {out_path}")

    # ---- Plot at end of main ----
    time = series["Time"]
    plot_2x4(time, series)


def main():
    """Parse command-line arguments and run the full extract → smooth → differentiate → write → plot pipeline."""
    run(make_parser().parse_args())

if __name__ == "__main__":
    main()
