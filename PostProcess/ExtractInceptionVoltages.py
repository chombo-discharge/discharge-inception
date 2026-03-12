#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extract the six inception voltages (Minimum, Streamer, Townsend × ±) from every
run_N/report.txt in a pdiv_database directory.  Writes an xarray/NetCDF dataset
(or a CSV fallback) that is directly plottable.

Usage:
    python ExtractInceptionVoltages.py <db_dir> [options]

See --help for full option list.
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

# ---- voltage variable names ----
VOLTAGE_VARS = [
    "min_voltage_pos",
    "min_voltage_neg",
    "streamer_voltage_pos",
    "streamer_voltage_neg",
    "townsend_voltage_pos",
    "townsend_voltage_neg",
]

LABEL_MAP = {
    "Minimum inception voltage(+)":  "min_voltage_pos",
    "Minimum inception voltage(-)":  "min_voltage_neg",
    "Streamer inception voltage(+)": "streamer_voltage_pos",
    "Streamer inception voltage(-)": "streamer_voltage_neg",
    "Townsend inception voltage(+)": "townsend_voltage_pos",
    "Townsend inception voltage(-)": "townsend_voltage_neg",
}

DBL_MAX = 1.79769e+308

# Regex for a header voltage line such as:
#   # Minimum inception voltage(+)  = 55375.6,	 x = (-0.000234375,0.0138281)
_HEADER_RE = re.compile(
    r'^#\s+(?P<label>.+?)\s+=\s+(?P<voltage>[\d.eE+\-]+),\s*x\s*=\s*\((?P<pos>[^)]+)\)'
)


# ---- optional imports ----

def _try_import_xarray():
    try:
        import xarray as xr
        return xr
    except ImportError:
        return None


def _try_import_matplotlib():
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


# ---- metadata loading ----

def load_metadata(db_dir: Path):
    """
    Returns (keys, coord_values, run_index) where:
      keys        : list of parameter key names (ordered)
      coord_values: dict  key -> sorted list of unique values
      run_index   : dict  str(i) -> list of parameter values
    """
    index_path = db_dir / "index.json"
    if not index_path.exists():
        print(f"error: {index_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(index_path) as f:
        idx = json.load(f)

    keys = idx["keys"]
    run_index = idx["index"]  # {"0": [val0, val1, ...], ...}

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

    return keys, coord_values, run_index


# ---- report parsing ----

def parse_report(report_path: Path) -> dict:
    """
    Parse the six inception voltages from the header of report.txt.
    Returns dict mapping variable name -> float (NaN if DBL_MAX or not found).
    """
    result = {v: float("nan") for v in VOLTAGE_VARS}

    try:
        with open(report_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                # Stop at the data table (non-comment line)
                if line.startswith("#"):
                    m = _HEADER_RE.match(line)
                    if m:
                        label = m.group("label").strip()
                        var = LABEL_MAP.get(label)
                        if var is not None:
                            val = float(m.group("voltage"))
                            if val >= DBL_MAX:
                                val = float("nan")
                            result[var] = val
                else:
                    # Once we hit data rows, stop scanning
                    break
    except OSError as e:
        print(f"  warning: could not read {report_path}: {e}", file=sys.stderr)

    return result


# ---- dataset building ----

def build_dataset(keys, coord_values, run_index, db_dir: Path, prefix: str):
    """
    Returns a dict suitable for both xarray and CSV paths:
      {
        'keys': keys,
        'coord_values': coord_values,
        'shape': tuple of dimension sizes,
        'arrays': {var_name: np.ndarray of shape},   # NaN-filled, indexed by coords
        'rows': list of dicts for CSV (one per run),
      }
    """
    shape = tuple(len(coord_values[k]) for k in keys)
    arrays = {v: np.full(shape, float("nan")) for v in VOLTAGE_VARS}

    # Build lookup: value -> index within each dimension
    val_index = {k: {v: i for i, v in enumerate(coord_values[k])} for k in keys}

    rows = []  # for CSV
    summary = []  # for stdout

    for run_str, param_combo in sorted(run_index.items(), key=lambda x: int(x[0])):
        run_n = int(run_str)
        report_path = db_dir / f"{prefix}{run_n}" / "report.txt"

        voltages = parse_report(report_path)

        # Map param combo to N-D index
        idx = tuple(val_index[k][param_combo[i]] for i, k in enumerate(keys))
        for var in VOLTAGE_VARS:
            arrays[var][idx] = voltages[var]

        row = {k: param_combo[i] for i, k in enumerate(keys)}
        row.update(voltages)
        rows.append(row)

        summary.append((run_n, param_combo, voltages))

    return {
        "keys": keys,
        "coord_values": coord_values,
        "shape": shape,
        "arrays": arrays,
        "rows": rows,
        "summary": summary,
    }


# ---- output: NetCDF ----

def write_netcdf(data: dict, output_path: Path):
    xr = _try_import_xarray()
    if xr is None:
        print("error: xarray is not installed. Use --format csv or install xarray.", file=sys.stderr)
        sys.exit(1)

    keys = data["keys"]
    coord_values = data["coord_values"]
    arrays = data["arrays"]

    coords = {k: coord_values[k] for k in keys}
    data_vars = {var: (keys, arrays[var]) for var in VOLTAGE_VARS}

    ds = xr.Dataset(data_vars, coords=coords)
    ds.to_netcdf(output_path)
    print(f"Wrote NetCDF dataset to: {output_path}")
    print(ds)


# ---- output: CSV ----

def write_csv(data: dict, output_path: Path):
    keys = data["keys"]
    rows = data["rows"]
    fieldnames = keys + VOLTAGE_VARS

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Wrote CSV to: {output_path}")


# ---- summary table ----

def print_summary(data: dict):
    keys = data["keys"]
    summary = data["summary"]

    header_params = "  ".join(f"{k:>18}" for k in keys)
    header_v = "  ".join(f"{v:>22}" for v in VOLTAGE_VARS)
    print(f"#\n# {'Run':>5}  {header_params}  {header_v}")
    print("# " + "-" * (5 + 2 + 20 * len(keys) + 24 * len(VOLTAGE_VARS)))

    for run_n, param_combo, voltages in summary:
        param_str = "  ".join(f"{p:>18.6g}" for p in param_combo)
        volt_str = "  ".join(
            f"{voltages[v]:>22.6g}" if not np.isnan(voltages[v]) else f"{'nan':>22}"
            for v in VOLTAGE_VARS
        )
        print(f"{run_n:>5}  {param_str}  {volt_str}")
    print()


# ---- plotting ----

def _select_slice(ds, keys, plot_params, select_map):
    """
    For xarray dataset ds, fix all dims not in plot_params.
    Returns (sliced_ds, fixed_dict) where fixed_dict maps key -> value used.
    """
    fixed = {}
    for k in keys:
        if k in plot_params:
            continue
        if k in select_map:
            val = select_map[k]
        else:
            val = float(ds.coords[k].values[0])
            print(f"  warning: '{k}' not specified via --select; defaulting to first value {val!r}")
        fixed[k] = val
        ds = ds.sel({k: val}, method="nearest")
    return ds, fixed


def _fixed_label(fixed: dict) -> str:
    if not fixed:
        return ""
    parts = ", ".join(f"{k}={v:.4g}" for k, v in fixed.items())
    return f"({parts})"


def plot_1d(ds, keys, plot_param, select_map, voltage_filter):
    plt = _try_import_matplotlib()
    if plt is None:
        print("error: matplotlib is not installed. Cannot plot.", file=sys.stderr)
        sys.exit(1)

    ds_sliced, fixed = _select_slice(ds, keys, [plot_param], select_map)
    x = ds_sliced.coords[plot_param].values

    types = [
        ("Minimum",  "min_voltage_pos",      "min_voltage_neg"),
        ("Streamer", "streamer_voltage_pos",  "streamer_voltage_neg"),
        ("Townsend", "townsend_voltage_pos",  "townsend_voltage_neg"),
    ]
    type_names = {"min": "Minimum", "streamer": "Streamer", "townsend": "Townsend"}

    if voltage_filter != "all":
        types = [t for t in types if t[0].lower() == voltage_filter]

    fig, axes = plt.subplots(1, len(types), figsize=(6 * len(types), 5), squeeze=False)
    axes = axes[0]

    for ax, (title, pos_var, neg_var) in zip(axes, types):
        y_pos = ds_sliced[pos_var].values
        y_neg = ds_sliced[neg_var].values
        ax.plot(x, y_pos, marker="o", label="pos (+)")
        ax.plot(x, y_neg, marker="s", linestyle="--", label="neg (-)")
        ax.set_title(f"{title} inception voltage")
        ax.set_xlabel(plot_param)
        ax.set_ylabel("Voltage (V)")
        ax.legend()
        ax.grid(True, linestyle=":", linewidth=0.5)

    fig.suptitle(f"Inception voltages vs {plot_param}  {_fixed_label(fixed)}")
    fig.tight_layout()
    plt.show()


def plot_2d(ds, keys, plot_params, select_map, voltage_filter):
    plt = _try_import_matplotlib()
    if plt is None:
        print("error: matplotlib is not installed. Cannot plot.", file=sys.stderr)
        sys.exit(1)

    ds_sliced, fixed = _select_slice(ds, keys, plot_params, select_map)

    p1, p2 = plot_params
    x = ds_sliced.coords[p2].values
    y = ds_sliced.coords[p1].values

    types = [
        ("Minimum",  "min_voltage_pos",      "min_voltage_neg"),
        ("Streamer", "streamer_voltage_pos",  "streamer_voltage_neg"),
        ("Townsend", "townsend_voltage_pos",  "townsend_voltage_neg"),
    ]
    if voltage_filter != "all":
        types = [t for t in types if t[0].lower() == voltage_filter]

    ncols = len(types)
    fig, axes = plt.subplots(2, ncols, figsize=(6 * ncols, 10), squeeze=False)

    for col, (title, pos_var, neg_var) in enumerate(types):
        for row, (polarity, var) in enumerate([("Positive (+)", pos_var), ("Negative (-)", neg_var)]):
            ax = axes[row][col]
            # Transpose so p1 is rows (y-axis), p2 is cols (x-axis)
            z = ds_sliced[var].values
            if ds_sliced[var].dims[0] != p1:
                z = z.T
            mesh = ax.pcolormesh(x, y, z, shading="auto")
            cb = fig.colorbar(mesh, ax=ax)
            cb.set_label("Voltage (V)")
            ax.set_xlabel(p2)
            ax.set_ylabel(p1)
            ax.set_title(f"{title} — {polarity}")

    fig.suptitle(
        f"Inception voltages: {p1} × {p2}  {_fixed_label(fixed)}"
    )
    fig.tight_layout()
    plt.show()


# ---- main ----

def make_parser(add_help=True) -> argparse.ArgumentParser:
    """Return the configured argument parser (separated from main() for CLI reuse)."""
    ap = argparse.ArgumentParser(
        add_help=add_help,
        description="Extract inception voltages from a pdiv_database and write NetCDF/CSV."
    )
    ap.add_argument("db_dir", help="Path to a pdiv_database directory (must contain index.json)")
    ap.add_argument(
        "--output", default=None,
        help="Output file path (default: <db_dir>/inception_voltages.nc or .csv)"
    )
    ap.add_argument(
        "--format", choices=["netcdf", "csv", "auto"], default="auto",
        help="Output format: auto (default — netcdf if xarray is installed, else csv), "
             "netcdf (requires xarray), or csv."
    )
    ap.add_argument(
        "--plot", nargs="+", metavar="PARAM",
        help="Plot vs 1 parameter (line) or 2 parameters (heatmap)"
    )
    ap.add_argument(
        "--select", nargs="+", metavar="KEY=VALUE", default=[],
        help="Fix a parameter at a value when plotting (e.g. pressure=1e5)"
    )
    ap.add_argument(
        "--voltage", choices=["min", "streamer", "townsend", "all"], default="all",
        help="Which voltage type(s) to plot (default: all)"
    )
    return ap


def run(args) -> None:
    """Execute the pipeline given a pre-parsed Namespace."""
    ap = make_parser()

    # Validate --plot count
    if args.plot is not None and len(args.plot) > 2:
        ap.error("--plot accepts at most 2 parameters")

    db_dir = Path(args.db_dir)
    if not db_dir.is_dir():
        print(f"error: '{db_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    # Parse --select KEY=VALUE pairs
    select_map = {}
    for item in args.select:
        if "=" not in item:
            ap.error(f"--select argument must be KEY=VALUE, got: {item!r}")
        k, v = item.split("=", 1)
        try:
            select_map[k.strip()] = float(v.strip())
        except ValueError:
            ap.error(f"could not parse value in --select {item!r}")

    # Load metadata
    keys, coord_values, run_index = load_metadata(db_dir)
    index_path = db_dir / "index.json"
    with open(index_path) as f:
        idx_raw = json.load(f)
    prefix = idx_raw.get("prefix", "run_")

    print(f"# Database: {db_dir}")
    print(f"# Keys: {keys}")
    print(f"# Runs: {len(run_index)}")
    for k in keys:
        print(f"#   {k}: {coord_values[k]}")

    # Build dataset
    data = build_dataset(keys, coord_values, run_index, db_dir, prefix)

    # Print summary
    print_summary(data)

    # Resolve effective format
    fmt = args.format
    if fmt == "auto":
        fmt = "netcdf" if _try_import_xarray() is not None else "csv"
        if fmt == "csv":
            print("note: xarray not installed — writing CSV instead of NetCDF.")

    # Determine output path
    from discharge_inception.results import ensure_results_dir, link_metadata
    results_dir = ensure_results_dir(db_dir)
    ext = ".nc" if fmt == "netcdf" else ".csv"
    output_path = Path(args.output) if args.output else results_dir / f"inception_voltages{ext}"
    # If an explicit output path was given but has the wrong extension for the resolved
    # format (e.g. postprocess passed .nc but we fell back to csv), fix the extension.
    if args.output:
        output_path = output_path.with_suffix(ext)

    # Write output
    if fmt == "netcdf":
        write_netcdf(data, output_path)
    else:
        write_csv(data, output_path)

    link_metadata(db_dir, results_dir)

    # Optional plotting
    if args.plot:
        xr = _try_import_xarray()
        if xr is None:
            print("error: --plot requires xarray. Install xarray or use --format csv.", file=sys.stderr)
            sys.exit(1)

        # Build xarray dataset for plotting
        coords = {k: coord_values[k] for k in keys}
        data_vars = {var: (keys, data["arrays"][var]) for var in VOLTAGE_VARS}
        ds = xr.Dataset(data_vars, coords=coords)

        if len(args.plot) == 1:
            plot_param = args.plot[0]
            if plot_param not in keys:
                print(f"error: '{plot_param}' is not a known parameter. Known: {keys}", file=sys.stderr)
                sys.exit(1)
            plot_1d(ds, keys, plot_param, select_map, args.voltage)
        else:
            p1, p2 = args.plot
            for p in [p1, p2]:
                if p not in keys:
                    print(f"error: '{p}' is not a known parameter. Known: {keys}", file=sys.stderr)
                    sys.exit(1)
            plot_2d(ds, keys, [p1, p2], select_map, args.voltage)


def main():
    run(make_parser().parse_args())


if __name__ == "__main__":
    main()
