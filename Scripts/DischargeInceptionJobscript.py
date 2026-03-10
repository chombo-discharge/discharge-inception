#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DischargeInceptionJobscript — SLURM task script for the inception stepper.

This script is executed once per parameter combination in the inception
database stage (invoked as a SLURM task via ``GenericArrayJob.sh``).

Execution flow
--------------
1. **Navigate to run directory** — calls ``setup_jobscript_logging_and_dir``
   to change into the correct ``run_<i>/`` subdirectory for this SLURM task.

2. **Run inception stepper via MPI** — launches ``mpirun main <input_file>``
   (or the configured MPI wrapper) and waits for it to finish, propagating
   any nonzero exit code immediately.

3. **Validate voltage range against DischargeInceptionTagger.max_voltage** —
   reads the stepper's ``report.txt`` to find the highest voltage reached and
   compares it to the ``DischargeInceptionTagger.max_voltage`` field in the
   input file.

4. **Auto-correct and rerun if the stepper exceeded the tagger limit** — if
   the stepper's maximum voltage is above the tagger limit, the old
   ``report.txt`` is backed up, ``max_voltage`` is rounded up to the nearest
   kV and written back to the input file, and the stepper is rerun.

Author André Kapelrud, Robert Marskar
Copyright © 2026 SINTEF Energi AS
"""

import math
import os
import shutil
import subprocess
import sys
import time

# local imports
sys.path.append(os.getcwd())  # needed for local imports from slurm scripts
from ExtractElectronPositions import parse_report_file  # noqa: E402
from discharge_inception.config_util import (  # noqa: E402
    handle_combination, load_slurm_config,
    read_input_float_field, setup_jobscript_logging_and_dir,
)


def _run_solver(cmd: str) -> int:
    """Launch *cmd* in a subprocess and block until it exits.

    The process is started with ``shell=True`` so that MPI wrapper strings
    (e.g. ``mpirun -n 4 main input.inputs``) are passed verbatim to the
    shell.  The function polls every 0.5 s rather than using
    ``Popen.wait()`` so that the parent process remains responsive to
    signals.

    Parameters
    ----------
    cmd : str
        Full shell command string to execute, e.g.
        ``"mpirun main simulation.inputs"``.

    Returns
    -------
    int
        Exit code of the subprocess.  A nonzero value indicates failure.
    """
    p = subprocess.Popen(cmd, shell=True)
    while p.poll() is None:
        time.sleep(0.5)
    return p.returncode


def main():
    """Run the inception stepper, validate the voltage range, and rerun if needed."""
    log, _task_id, _run_dir, input_file = setup_jobscript_logging_and_dir()

    slurm = load_slurm_config()
    mpi = slurm.get('mpi', 'mpirun')

    cmd = f"{mpi} main {input_file}"
    log.info(f"cmdstr: '{cmd}'")

    # propagate nonzero exit code to calling jobscript
    return_code = _run_solver(cmd)
    if return_code != 0:
        sys.exit(return_code)

    # check that the maximum voltage is at or below the max_voltage used for the
    # DischargeInceptionTagger adaptive mesh refinement class:
    report_data = parse_report_file('report.txt',
                                    ['+/- Voltage', 'Max K(+)', 'Max K(-)'])

    # take last row to get the max voltage
    calculated_max_voltage = report_data[1][-1][0]
    log.info(f'DischargeInception found max voltage: {calculated_max_voltage}')

    orig_max_voltage = read_input_float_field(
        input_file, 'DischargeInceptionTagger.max_voltage'
    )
    if orig_max_voltage is None:
        raise RuntimeError(
            f"'{input_file}' does not contain "
            "'DischargeInceptionTagger.max_voltage' field"
        )

    if orig_max_voltage < calculated_max_voltage:
        log.info('renaming: report.txt -> report.txt.bak')
        shutil.move('report.txt', 'report.txt.bak')

        # round up to nearest kV
        new_max_voltage = math.ceil(calculated_max_voltage / 1000) * 1000
        log.info(f'Setting DischargeInceptionTagger.max_voltage = {new_max_voltage}')

        # update input file
        handle_combination(
            {
                "mesh_max_voltage": {
                    "target": input_file,
                    "uri": "DischargeInceptionTagger.max_voltage",
                }
            },
            dict(mesh_max_voltage=new_max_voltage),
        )

        log.info('Rerunning DischargeInception calculations')
        sys.exit(_run_solver(cmd))


if __name__ == '__main__':
    main()
