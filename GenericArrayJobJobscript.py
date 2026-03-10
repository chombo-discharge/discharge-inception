#!/usr/bin/env python
"""
Author André Kapelrud, Robert Marskar
Copyright © 2026 SINTEF Energi AS
"""

import sys
import subprocess

# local imports
from discharge_inception.config_util import setup_jobscript_logging_and_dir, load_slurm_config


if __name__ == '__main__':

    log, task_id, run_dir, input_file = setup_jobscript_logging_and_dir()

    slurm = load_slurm_config()
    mpi = slurm.get('mpi', 'mpirun')

    cmd = f"{mpi} main {input_file} Random.seed={task_id:d}"
    log.info(f"cmdstr: '{cmd}'")
    p = subprocess.Popen(cmd, shell=True)

    while True:
        res = p.poll()
        if res is not None:
            break
