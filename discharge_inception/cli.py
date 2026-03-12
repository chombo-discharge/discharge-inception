#!/usr/bin/env python
"""
Author André Kapelrud, Robert Marskar
Copyright © 2026 SINTEF Energi AS

Top-level CLI entry point.  Dispatches 'run' and 'ls' subcommands.
"""

import argparse
import importlib
import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path

_PP_DIR = Path(__file__).parent.parent / 'PostProcess'


def _import_pp(name: str):
    """Import a PostProcess module by filename stem, adding the directory to sys.path once."""
    if str(_PP_DIR) not in sys.path:
        sys.path.insert(0, str(_PP_DIR))
    return importlib.import_module(name)


# ---------------------------------------------------------------------------
# discharge-inception post-process subcommands
# ---------------------------------------------------------------------------

def cmd_analyze_time_series(args) -> None:
    _import_pp('AnalyzeTimeSeries').run(args)


def cmd_extract_inception_voltages(args) -> None:
    _import_pp('ExtractInceptionVoltages').run(args)


def cmd_gather_plasma_event_logs(args) -> None:
    _import_pp('GatherPlasmaEventLogs').run(args)


def cmd_plot_delta_e_rel(args) -> None:
    _import_pp('PlotDeltaERel').run(args)


def cmd_plot_delta_e(args) -> None:
    _import_pp('PlotDeltaE').run(args)


def cmd_postprocess(args) -> None:
    study_root = Path(args.study_root).resolve()
    pdiv_db    = study_root / args.pdiv_db
    plasma_sim = study_root / args.plasma_sim

    # Results directories mirror the study layout under <study_root>/Results/
    pdiv_results   = study_root / 'Results' / args.pdiv_db
    plasma_results = study_root / 'Results' / args.plasma_sim

    # --- ExtractInceptionVoltages on pdiv_database ---
    if pdiv_db.is_dir():
        print(f"[postprocess] extract-inception-voltages  {pdiv_db}")
        pdiv_results.mkdir(parents=True, exist_ok=True)
        mod = _import_pp('ExtractInceptionVoltages')
        ns  = mod.make_parser().parse_args([
            str(pdiv_db),
            '--output', str(pdiv_results / 'inception_voltages.nc'),
        ])
        try:
            mod.run(ns)
        except SystemExit as e:
            if e.code:
                print(f"  warning: extract-inception-voltages exited with code {e.code}")
    else:
        print(f"[postprocess] skipping pdiv database ('{pdiv_db}' not found)")

    # --- GatherPlasmaEventLogs on plasma_simulations ---
    if plasma_sim.is_dir():
        print(f"[postprocess] gather-plasma-event-logs    {plasma_sim}")
        plasma_results.mkdir(parents=True, exist_ok=True)
        mod = _import_pp('GatherPlasmaEventLogs')
        ns  = mod.make_parser().parse_args([
            str(plasma_sim),
            '--output', str(plasma_results / 'plasma_event_log.csv'),
        ])
        try:
            mod.run(ns)
        except SystemExit as e:
            if e.code:
                print(f"  warning: gather-plasma-event-logs exited with code {e.code}")
    else:
        print(f"[postprocess] skipping plasma simulations ('{plasma_sim}' not found)")
        return

    # --- Per-run plots ---
    index_file = plasma_sim / 'index.json'
    if not index_file.exists():
        print(f"[postprocess] skipping per-run plots: no index.json in '{plasma_sim}'")
        return

    with open(index_file) as f:
        index = json.load(f)
    prefix  = index.get('prefix', args.run_prefix)
    run_ids = sorted(index.get('index', {}).keys(), key=int)

    for run_id in run_ids:
        run_dir     = plasma_sim / f'{prefix}{int(run_id)}'
        run_results = plasma_results / f'{prefix}{int(run_id)}'
        if not run_dir.is_dir():
            print(f"[postprocess] skipping '{run_dir}': directory not found")
            continue
        run_results.mkdir(parents=True, exist_ok=True)

        print(f"[postprocess] plot-delta-e-rel             {run_dir}")
        mod = _import_pp('PlotDeltaERel')
        ns  = mod.make_parser().parse_args([
            str(run_dir),
            '--png',    str(run_results / 'delta_e_rel.png'),
            '--output', str(run_results / 'delta_e_rel.csv'),
        ])
        try:
            mod.run(ns)
        except SystemExit as e:
            if e.code:
                print(f"  warning: plot-delta-e-rel exited with code {e.code}")

        print(f"[postprocess] plot-delta-e                 {run_dir}")
        mod = _import_pp('PlotDeltaE')
        ns  = mod.make_parser().parse_args([
            str(run_dir),
            '--png',    str(run_results / 'peak_delta_e.png'),
            '--output', str(run_results / 'peak_delta_e.csv'),
        ])
        try:
            mod.run(ns)
        except SystemExit as e:
            if e.code:
                print(f"  warning: plot-delta-e exited with code {e.code}")


def cmd_list_results(args) -> None:
    from discharge_inception.results import list_results, get_results_dir
    study_dir = Path(args.study_dir)
    grouped = list_results(study_dir)
    if not grouped:
        print(f"No results found under '{get_results_dir(study_dir)}'")
        return
    total = sum(len(v) for v in grouped.values())
    print(f"Results in {study_dir}/  ({total} file{'s' if total != 1 else ''} "
          f"in {len(grouped)} folder{'s' if len(grouped) != 1 else ''})\n")
    for folder, files in sorted(grouped.items()):
        print(f"  {folder}/")
        for f in files:
            print(f"    {f}")
        print()


# ---------------------------------------------------------------------------
# discharge-inception ls
# ---------------------------------------------------------------------------

def _format_val(v) -> str:
    """Format a single parameter value concisely."""
    if isinstance(v, float):
        return f'{v:.6g}'
    if isinstance(v, list):
        return '[' + ', '.join(_format_val(x) for x in v) + ']'
    return str(v)


def _print_study(study_dir: Path) -> None:
    index_path = study_dir / 'index.json'
    if not index_path.is_file():
        print(f"error: no index.json in '{study_dir}'", file=sys.stderr)
        return

    with open(index_path) as f:
        index = json.load(f)

    # 'keys' is written by the configurator; 'key' by PlasmaJobscript voltage index
    keys = index.get('keys') or index.get('key') or []
    prefix = index.get('prefix', 'run_')
    runs = index.get('index', {})

    n = len(runs)
    print(f"{study_dir}  ({n} run{'s' if n != 1 else ''})")

    if not runs:
        print("  (empty)")
        print()
        return

    # Build rows: [(label, [formatted_values], has_report), ...]
    rows = []
    for i, vals in sorted(runs.items(), key=lambda x: int(x[0])):
        label = f'{prefix}{int(i)}'
        values = vals if isinstance(vals, list) else [vals]
        formatted = [_format_val(v) for v in values]
        has_report = (study_dir / label / 'report.txt').is_file()
        rows.append((label, formatted, has_report))

    # Column widths
    header = ['run'] + list(keys)
    col_widths = [len(h) for h in header]
    for label, values, _ in rows:
        col_widths[0] = max(col_widths[0], len(label))
        for j, v in enumerate(values):
            if j + 1 < len(col_widths):
                col_widths[j + 1] = max(col_widths[j + 1], len(v))

    sep = '  '
    header_line = sep.join(f'{h:<{col_widths[j]}}' for j, h in enumerate(header))
    rule        = sep.join('-' * w for w in col_widths)
    print('  ' + header_line)
    print('  ' + rule)
    for label, values, has_report in rows:
        cells = [label] + values
        line = sep.join(f'{c:<{col_widths[j]}}' for j, c in enumerate(cells))
        status = '  ✓' if has_report else ''
        print('  ' + line + status)
    print()


def cmd_ls(args) -> None:
    for study_dir in args.study_dirs:
        _print_study(Path(study_dir))


# ---------------------------------------------------------------------------
# discharge-inception slurm-status
# ---------------------------------------------------------------------------

def cmd_status(args) -> None:
    from discharge_inception.slurm_status import cmd_status as _cmd
    _cmd(args)


# ---------------------------------------------------------------------------
# discharge-inception plasma-status
# ---------------------------------------------------------------------------

def cmd_plasma_status(args) -> None:
    import csv
    from discharge_inception.results import get_results_dir

    path = Path(args.plasma_sim).resolve()

    # Accept either a CSV file directly or a plasma_simulations directory
    if path.is_file():
        csv_path = path
    else:
        csv_path = get_results_dir(path) / 'plasma_event_log.csv'

    if not csv_path.exists():
        print(f"error: no plasma_event_log.csv found at '{csv_path}'", file=sys.stderr)
        print("  Run 'discharge-inception gather-plasma-event-logs' or "
              "'discharge-inception postprocess' first.", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("No data in CSV.")
        return

    # Identify parameter columns (everything between run_id and final_step)
    all_fields = list(rows[0].keys())
    fixed_tail = ['final_step', 'final_time', 'final_dt',
                  'inception', 'convergence_failures', 'other_abort', 'status']
    param_keys = [f for f in all_fields if f not in (['run_id'] + fixed_tail)]

    # Apply optional status filter
    if args.filter:
        rows = [r for r in rows if r['status'] == args.filter]
        if not rows:
            print(f"No runs with status '{args.filter}'.")
            return

    # Count by status for summary line
    from collections import Counter
    counts = Counter(r['status'] for r in rows)

    # Column widths (dynamic)
    param_w  = max((max(len(k) for k in param_keys) if param_keys else 0), 12)
    status_w = max(len('status'), max(len(r['status']) for r in rows))
    time_w   = 16
    dt_w     = 16

    sep = '  '
    param_header = sep.join(f'{k:>{param_w}}' for k in param_keys)
    print(f"\n# CSV: {csv_path}")
    print(f"# {'run':>5}  {param_header}  {'status':>{status_w}}"
          f"  {'final_time':>{time_w}}  {'final_dt':>{dt_w}}")
    rule_w = 5 + 2 + (param_w + 2) * len(param_keys) + status_w + 2 + time_w + 2 + dt_w
    print('# ' + '-' * rule_w)

    for r in rows:
        params = sep.join(f'{r[k]:>{param_w}}' for k in param_keys)
        t  = r['final_time'] if r['final_time'] else '—'
        dt = r['final_dt']   if r['final_dt']   else '—'
        try:
            t  = f'{float(t):>{time_w}.6g}'
        except (ValueError, TypeError):
            t  = f'{t:>{time_w}}'
        try:
            dt = f'{float(dt):>{dt_w}.6g}'
        except (ValueError, TypeError):
            dt = f'{dt:>{dt_w}}'
        print(f"{r['run_id']:>5}  {params}  {r['status']:>{status_w}}  {t}  {dt}")

    print()
    summary = ', '.join(f"{v} {k}" for k, v in sorted(counts.items()))
    print(f"# {len(rows)} run(s): {summary}")
    print()


# ---------------------------------------------------------------------------
# discharge-inception run
# ---------------------------------------------------------------------------

def _resolve_output_dir(output_dir: Path, overwrite: bool, suffix: bool) -> Path:
    if not output_dir.exists():
        return output_dir

    if overwrite:
        import shutil
        shutil.rmtree(output_dir)
        return output_dir

    if suffix:
        n = 1
        while True:
            candidate = Path(str(output_dir) + f'_{n}')
            if not candidate.exists():
                return candidate
            n += 1

    # Neither flag given — tell user and exit cleanly
    print(f"error: output directory already exists: '{output_dir}'", file=sys.stderr)
    print("  Use --overwrite to delete it or --suffix to create a numbered copy.",
          file=sys.stderr)
    sys.exit(1)


def cmd_run(args) -> None:
    from discharge_inception import configurator

    log = logging.getLogger('discharge-inception')
    formatter = logging.Formatter('%(asctime)s | %(levelname)s :: %(message)s')
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    log.addHandler(sh)

    doroll = os.path.isfile(args.logfile)
    fh = logging.handlers.RotatingFileHandler(
        args.logfile, backupCount=5, encoding='utf-8')
    fh.setFormatter(formatter)
    log.addHandler(fh)
    log.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    if doroll:
        fh.doRollover()

    output_dir = _resolve_output_dir(args.output_dir, args.overwrite, args.suffix)
    if output_dir != args.output_dir:
        log.info(f"Output directory renamed to '{output_dir}'")
    configurator.setup(log, output_dir, args.run_definition, dim=args.dim,
                       verbose=args.verbose, pdiv_only=args.pdiv_only)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='discharge-inception',
        description='Parametric study configurator for chombo-discharge simulations.')
    subparsers = parser.add_subparsers(dest='command', metavar='command')
    subparsers.required = True

    # --- discharge-inception run ----------------------------------------------------
    run_p = subparsers.add_parser(
        'run', help='Configure and submit a parametric study.')
    run_p.add_argument(
        'run_definition', type=Path,
        help='Parameter space definition (.json or .py with top_object).')
    run_p.add_argument(
        '--output-dir', default='study_results', type=Path,
        help='Output directory for study result files. (default: study_results)')
    run_p.add_argument(
        '--dim', default=3, type=int,
        help='Dimensionality of simulations. Must match chombo-discharge compilation. (default: 3)')
    run_p.add_argument(
        '--verbose', action='store_true', help='Increase verbosity.')
    run_p.add_argument(
        '--logfile', default='configurator.log',
        help='Log file; rotated automatically each invocation. (default: configurator.log)')
    run_p.add_argument(
        '--pdiv-only', action='store_true',
        help='Set up and submit only the inception (PDIV) database jobs; '
             'skip all plasma study setup and Slurm submission.')
    conflict_group = run_p.add_mutually_exclusive_group()
    conflict_group.add_argument(
        '--overwrite', action='store_true',
        help='Delete and recreate output directory if it already exists.')
    conflict_group.add_argument(
        '--suffix', action='store_true',
        help='Append _1, _2, … to output directory name if it already exists.')

    # --- discharge-inception ls -----------------------------------------------------
    ls_p = subparsers.add_parser(
        'ls', help='List runs and parameter settings in a study directory.')
    ls_p.add_argument(
        'study_dirs', nargs='+', type=Path, metavar='study_dir',
        help='Study output directory containing index.json (e.g. pdiv_database/).')

    # --- discharge-inception slurm-status -------------------------------------------
    status_p = subparsers.add_parser(
        'slurm-status', help='Show Slurm job status for one or more study directories.')
    status_p.add_argument(
        'study_dirs', nargs='+', type=Path, metavar='study_dir',
        help='Study directory (containing index.json) or parent directory '
             'containing multiple studies.')
    status_p.add_argument(
        '--no-voltage', action='store_true',
        help='Skip inner voltage array queries (faster).')

    # --- discharge-inception postprocess --------------------------------------------
    pp_p = subparsers.add_parser(
        'postprocess',
        help='Run all post-processing scripts on a study directory.')
    pp_p.add_argument(
        'study_root', type=Path,
        help='Top-level study directory (e.g. PressureStudy_1/).')
    pp_p.add_argument(
        '--pdiv-db', default='pdiv_database', metavar='DIRNAME',
        help='Subdirectory name of the pdiv database (default: pdiv_database).')
    pp_p.add_argument(
        '--plasma-sim', default='plasma_simulations', metavar='DIRNAME',
        help='Subdirectory name of the plasma simulations (default: plasma_simulations).')
    pp_p.add_argument(
        '--run-prefix', default='run_', metavar='PREFIX',
        help='Run directory prefix (default: run_). Overridden by prefix in index.json.')

    # --- discharge-inception plasma-status ------------------------------------------
    ps_p = subparsers.add_parser(
        'plasma-status',
        help='Show per-run plasma simulation status from plasma_event_log.csv.')
    ps_p.add_argument(
        'plasma_sim', type=Path,
        help='plasma_simulations/ directory, or path to plasma_event_log.csv directly.')
    ps_p.add_argument(
        '--filter', default=None,
        metavar='STATUS',
        help='Show only runs with this status '
             '(completed, inception, convergence_failure, abort, not_found).')

    # --- discharge-inception list-results -------------------------------------------
    lr_p = subparsers.add_parser(
        'list-results',
        help='List all post-processed result files in a study directory.')
    lr_p.add_argument(
        'study_dir', type=Path,
        help='Study directory (containing index.json and Results/).')

    # --- discharge-inception analyze-time-series ------------------------------------
    pp_mod = _import_pp('AnalyzeTimeSeries')
    subparsers.add_parser(
        'analyze-time-series',
        parents=[pp_mod.make_parser(add_help=False)],
        help='Extract, smooth, differentiate, and filter time-series data from a plasma log.')

    # --- discharge-inception extract-inception-voltages -----------------------------
    pp_mod = _import_pp('ExtractInceptionVoltages')
    subparsers.add_parser(
        'extract-inception-voltages',
        parents=[pp_mod.make_parser(add_help=False)],
        help='Extract inception voltages from a pdiv_database and write NetCDF/CSV.')

    # --- discharge-inception gather-plasma-event-logs -------------------------------
    pp_mod = _import_pp('GatherPlasmaEventLogs')
    subparsers.add_parser(
        'gather-plasma-event-logs',
        parents=[pp_mod.make_parser(add_help=False)],
        help='Gather plasma event logs from a database and write a CSV summary.')

    # --- discharge-inception plot-delta-e-rel ---------------------------------------
    pp_mod = _import_pp('PlotDeltaERel')
    subparsers.add_parser(
        'plot-delta-e-rel',
        parents=[pp_mod.make_parser(add_help=False)],
        help='Batch-plot ΔE(rel) vs time for every run in a plasma database.')

    # --- discharge-inception plot-delta-e -------------------------------------------
    pp_mod = _import_pp('PlotDeltaE')
    subparsers.add_parser(
        'plot-delta-e',
        parents=[pp_mod.make_parser(add_help=False)],
        help='Plot peak ΔE(rel) and/or ΔE(max) vs voltage for a run_* database.')

    args = parser.parse_args()

    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'ls':
        cmd_ls(args)
    elif args.command == 'slurm-status':
        cmd_status(args)
    elif args.command == 'plasma-status':
        cmd_plasma_status(args)
    elif args.command == 'analyze-time-series':
        cmd_analyze_time_series(args)
    elif args.command == 'extract-inception-voltages':
        cmd_extract_inception_voltages(args)
    elif args.command == 'gather-plasma-event-logs':
        cmd_gather_plasma_event_logs(args)
    elif args.command == 'plot-delta-e-rel':
        cmd_plot_delta_e_rel(args)
    elif args.command == 'plot-delta-e':
        cmd_plot_delta_e(args)
    elif args.command == 'postprocess':
        cmd_postprocess(args)
    elif args.command == 'list-results':
        cmd_list_results(args)


if __name__ == '__main__':
    main()
