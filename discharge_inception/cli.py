#!/usr/bin/env python
"""
Author André Kapelrud
Copyright © 2025 SINTEF Energi AS

Top-level CLI entry point.  Dispatches 'run' and 'ls' subcommands.
"""

import argparse
import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path


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
# discharge-inception run
# ---------------------------------------------------------------------------

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

    configurator.setup(log, args.output_dir, args.run_definition, dim=args.dim,
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

    # --- discharge-inception ls -----------------------------------------------------
    ls_p = subparsers.add_parser(
        'ls', help='List runs and parameter settings in a study directory.')
    ls_p.add_argument(
        'study_dirs', nargs='+', type=Path, metavar='study_dir',
        help='Study output directory containing index.json (e.g. pdiv_database/).')

    args = parser.parse_args()

    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'ls':
        cmd_ls(args)


if __name__ == '__main__':
    main()
