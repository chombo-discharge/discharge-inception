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
# discharge-inception status
# ---------------------------------------------------------------------------

def cmd_status(args) -> None:
    from discharge_inception.slurm_status import cmd_status as _cmd
    _cmd(args)


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

    # --- discharge-inception status -------------------------------------------------
    status_p = subparsers.add_parser(
        'status', help='Show Slurm job status for one or more study directories.')
    status_p.add_argument(
        'study_dirs', nargs='+', type=Path, metavar='study_dir',
        help='Study directory (containing index.json) or parent directory '
             'containing multiple studies.')
    status_p.add_argument(
        '--no-voltage', action='store_true',
        help='Skip inner voltage array queries (faster).')

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

    args = parser.parse_args()

    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'ls':
        cmd_ls(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'analyze-time-series':
        cmd_analyze_time_series(args)
    elif args.command == 'extract-inception-voltages':
        cmd_extract_inception_voltages(args)
    elif args.command == 'gather-plasma-event-logs':
        cmd_gather_plasma_event_logs(args)
    elif args.command == 'plot-delta-e-rel':
        cmd_plot_delta_e_rel(args)


if __name__ == '__main__':
    main()
