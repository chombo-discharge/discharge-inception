"""
Robert Marskar
Copyright © 2026 SINTEF Energi AS

Slurm job status reporting for discharge-inception studies.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ARRAY_TASK_PAT = re.compile(r'^\d+_(\d+)$')

_STATE_MAP = {
    'PENDING':       'PENDING',
    'RUNNING':       'RUNNING',
    'COMPLETED':     'COMPLETED',
    'FAILED':        'FAILED',
    'CANCELLED':     'CANCELLED',
    'TIMEOUT':       'FAILED',
    'NODE_FAIL':     'FAILED',
    'OUT_OF_MEMORY': 'FAILED',
    'PREEMPTED':     'PENDING',
}


def classify_state(state: str) -> str:
    return _STATE_MAP.get(state.split()[0].rstrip('+'), 'UNKNOWN')


def read_job_id(logs_dir: Path) -> 'int | None':
    p = logs_dir / 'array_job_id'
    if not p.is_file():
        return None
    try:
        return int(p.read_text().strip())
    except (ValueError, OSError):
        return None


def query_sacct(job_id: int) -> 'dict[int, tuple[str, str]]':
    """Query sacct for array task states. Returns {task_idx: (state, exitcode)}."""
    try:
        result = subprocess.run(
            ['sacct', '-j', str(job_id),
             '--format=JobID,State,ExitCode',
             '-P', '--noheader'],
            capture_output=True, text=True, timeout=15
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}

    tasks = {}
    for line in result.stdout.splitlines():
        parts = line.split('|')
        if len(parts) < 3:
            continue
        job_id_raw = parts[0]
        state = parts[1].strip()
        exitcode = parts[2].strip()
        m = ARRAY_TASK_PAT.match(job_id_raw)
        if m:
            tasks[int(m.group(1))] = (state, exitcode)
    return tasks


def query_squeue(job_id: int) -> 'dict[int, str]':
    """Query squeue for pending/running array tasks. Returns {task_idx: state}."""
    try:
        result = subprocess.run(
            ['squeue', '-j', str(job_id), '-h', '-r', '-o', '%i %T'],
            capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}

    tasks = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        m = ARRAY_TASK_PAT.match(parts[0])
        if m:
            tasks[int(m.group(1))] = parts[1]
    return tasks


def get_task_states(job_id: int) -> 'dict[int, tuple[str, str]]':
    """Merge sacct and squeue into {task_idx: (state, exitcode_str)}."""
    sacct_data = query_sacct(job_id)
    sq_data = query_squeue(job_id)

    if not sacct_data:
        # Job may not be in sacct history yet (just submitted)
        return {idx: (state, '') for idx, state in sq_data.items()}

    # sacct takes priority; squeue fills tasks not yet visible in sacct
    merged = dict(sacct_data)
    for idx, state in sq_data.items():
        if idx not in merged:
            merged[idx] = (state, '')
    return merged


def _infer_outer_state(run_dir: Path, is_plasma: bool) -> 'tuple[str, str]':
    """Infer run state from filesystem markers when sacct/squeue have no data."""
    if is_plasma:
        if (run_dir / 'logs' / 'array_job_id').is_file():
            return ('COMPLETED', '0:0')
    else:
        if (run_dir / 'report.txt').is_file():
            return ('COMPLETED', '0:0')
    return ('UNKNOWN', '')


def _infer_voltage_state(voltage_dir: Path) -> 'tuple[str, str]':
    """Infer voltage task state from pout.0 when sacct/squeue have no data."""
    pout = voltage_dir / 'pout.0'
    if not pout.exists():
        return ('UNKNOWN', '')
    try:
        data = pout.read_bytes()[-2048:].decode('utf-8', errors='replace')
        if 'Driver::run -- ending run' in data:
            return ('COMPLETED', '0:0')
        return ('FAILED', '1:0')
    except OSError:
        return ('UNKNOWN', '')


def get_run_count(study_dir: Path) -> 'tuple[int, str, dict]':
    """Read index.json. Returns (n_runs, prefix, index_dict)."""
    index_path = study_dir / 'index.json'
    if not index_path.is_file():
        return 0, 'run_', {}
    try:
        with open(index_path) as f:
            index = json.load(f)
        prefix = index.get('prefix', 'run_')
        runs = index.get('index', {})
        return len(runs), prefix, runs
    except (OSError, json.JSONDecodeError):
        return 0, 'run_', {}


def is_plasma_study(study_dir: Path, prefix: str, index: dict) -> bool:
    """True if the first run directory contains logs/array_job_id."""
    if not index:
        return False
    first_idx = sorted(int(k) for k in index)[0]
    run_dir = study_dir / f'{prefix}{first_idx}'
    return (run_dir / 'logs' / 'array_job_id').is_file()


@dataclass
class StudyStatus:
    study_dir: Path
    job_id: 'int | None'
    run_count: int
    prefix: str
    task_states: 'dict[int, tuple[str, str]]'
    is_plasma: bool
    voltage_task_states: 'dict[int, dict[int, tuple[str, str]]]' = field(default_factory=dict)


def collect_study_status(study_dir: Path, skip_voltage: bool = False) -> StudyStatus:
    n_runs, prefix, index = get_run_count(study_dir)
    job_id = read_job_id(study_dir / 'logs')
    task_states = get_task_states(job_id) if job_id is not None else {}
    plasma = is_plasma_study(study_dir, prefix, index)

    for idx in range(n_runs):
        if idx not in task_states:
            run_dir = study_dir / f'{prefix}{idx}'
            task_states[idx] = _infer_outer_state(run_dir, plasma)

    voltage_task_states: dict[int, dict[int, tuple[str, str]]] = {}
    if plasma and not skip_voltage and index:
        for k in index:
            idx = int(k)
            run_dir = study_dir / f'{prefix}{idx}'
            inner_job_id = read_job_id(run_dir / 'logs')
            vtasks = get_task_states(inner_job_id) if inner_job_id is not None else {}
            i = 0
            while (vdir := run_dir / f'voltage_{i}').is_dir():
                if i not in vtasks:
                    vtasks[i] = _infer_voltage_state(vdir)
                i += 1
            voltage_task_states[idx] = vtasks

    return StudyStatus(
        study_dir=study_dir,
        job_id=job_id,
        run_count=n_runs,
        prefix=prefix,
        task_states=task_states,
        is_plasma=plasma,
        voltage_task_states=voltage_task_states,
    )


def print_study_status(status: StudyStatus) -> None:
    job_info = f'job {status.job_id}' if status.job_id is not None else 'no job submitted'
    n = status.run_count
    print(f"{status.study_dir}  ({n} run{'s' if n != 1 else ''}, {job_info})")

    if n == 0:
        print('  (empty)')
        print()
        return

    sorted_indices = sorted(range(n))
    sep = '  '

    def _classify(state_raw: str) -> tuple[str, str]:
        """Return (classified, lower) for a raw sacct/squeue state string."""
        c = classify_state(state_raw) if state_raw != 'unknown' else 'UNKNOWN'
        return c, c.lower()

    if status.is_plasma:
        # --- outer run column widths ---
        col_w = [len('run'), len('state')]
        for idx in sorted_indices:
            label = f'{status.prefix}{idx}'
            col_w[0] = max(col_w[0], len(label))
            state_raw, _ = status.task_states.get(idx, ('unknown', ''))
            col_w[1] = max(col_w[1], len(_classify(state_raw)[1]))

        # --- voltage sub-row label width (4-space indent, own alignment) ---
        vcol_w = len('voltage')
        for idx in sorted_indices:
            for vidx in status.voltage_task_states.get(idx, {}):
                vcol_w = max(vcol_w, len(f'voltage_{vidx}'))

        header_line = sep.join(f'{h:<{col_w[j]}}' for j, h in enumerate(['run', 'state']))
        rule        = sep.join('-' * w for w in col_w)
        print('  ' + header_line)
        print('  ' + rule)

        for idx in sorted_indices:
            label = f'{status.prefix}{idx}'
            state_raw, _ = status.task_states.get(idx, ('unknown', ''))
            _, state_str = _classify(state_raw)
            print('  ' + sep.join(f'{c:<{col_w[j]}}' for j, c in enumerate([label, state_str])).rstrip())

            for vidx, (vstate_raw, vexitcode) in sorted(
                status.voltage_task_states.get(idx, {}).items()
            ):
                vlabel = f'voltage_{vidx}'
                vclassified, vstate_str = _classify(vstate_raw)
                if vexitcode and vexitcode != '0:0' and vclassified in ('FAILED', 'UNKNOWN'):
                    vstate_str += f' ({vexitcode})'
                print(f'    {vlabel:<{vcol_w}}{sep}{vstate_str}')

        counts: dict[str, int] = {}
        for idx in sorted_indices:
            state_raw, _ = status.task_states.get(idx, ('unknown', ''))
            counts[_classify(state_raw)[1]] = counts.get(_classify(state_raw)[1], 0) + 1

    else:
        # --- non-plasma: flat table, optional exit column ---
        rows = []
        any_nonzero_exit = False
        for idx in sorted_indices:
            label = f'{status.prefix}{idx}'
            state_raw, exitcode = status.task_states.get(idx, ('unknown', ''))
            classified, state_str = _classify(state_raw)
            show_exit = exitcode and exitcode != '0:0' and classified in ('FAILED', 'UNKNOWN')
            if show_exit:
                any_nonzero_exit = True
            rows.append((label, state_str, exitcode if show_exit else ''))

        headers = ['run', 'state', 'exit'] if any_nonzero_exit else ['run', 'state']
        col_w = [len(h) for h in headers]
        for label, state_str, exit_str in rows:
            col_w[0] = max(col_w[0], len(label))
            col_w[1] = max(col_w[1], len(state_str))
            if any_nonzero_exit:
                col_w[2] = max(col_w[2], len(exit_str))

        header_line = sep.join(f'{h:<{col_w[j]}}' for j, h in enumerate(headers))
        rule        = sep.join('-' * w for w in col_w)
        print('  ' + header_line)
        print('  ' + rule)

        for label, state_str, exit_str in rows:
            cells = [label, state_str] + ([exit_str] if any_nonzero_exit else [])
            print('  ' + sep.join(f'{c:<{col_w[j]}}' for j, c in enumerate(cells)).rstrip())

        counts = {}
        for _, state_str, _ in rows:
            counts[state_str] = counts.get(state_str, 0) + 1

    order = ['completed', 'running', 'pending', 'failed', 'cancelled', 'unknown']
    parts = [f'{counts[s]} {s}' for s in order if s in counts]
    if parts:
        print('  Summary: ' + ', '.join(parts))
    print()


def cmd_status(args) -> None:
    dirs = []
    for p in args.study_dirs:
        p = Path(p)
        if (p / 'index.json').is_file():
            dirs.append(p)
        elif p.is_dir():
            children = sorted(
                s for s in p.iterdir()
                if s.is_dir() and (s / 'index.json').is_file()
            )
            if children:
                dirs.extend(children)
            else:
                print(f"warning: no study directories found in '{p}'", file=sys.stderr)
        else:
            print(f"error: '{p}' is not a directory", file=sys.stderr)

    for d in dirs:
        status = collect_study_status(d, skip_voltage=args.no_voltage)
        print_study_status(status)
