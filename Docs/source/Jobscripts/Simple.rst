.. _jobscripts_simple:

Writing a simple jobscript
==========================

The simplest jobscript navigates to its run directory and launches the solver.
The example below matches the actual ``GenericArrayJobJobscript.py`` used for
the leaf-level voltage runs:

.. code-block:: python
   :caption: GenericArrayJobJobscript.py
   :linenos:

   #!/usr/bin/env python
   """
   Author André Kapelrud, Robert Marskar
   Copyright © 2026 SINTEF Energi AS
   """

   import sys
   import subprocess

   from discharge_inception.config_util import setup_jobscript_logging_and_dir, load_slurm_config


   if __name__ == '__main__':

       # Step 1: Set up logging, navigate to run directory, find *.inputs file
       log, task_id, run_dir, input_file = setup_jobscript_logging_and_dir()

       # Step 2: Load SLURM / MPI configuration from slurm.toml
       slurm = load_slurm_config()
       mpi = slurm.get('mpi', 'mpirun')

       # Step 3: Build and launch the MPI command
       cmd = f"{mpi} main {input_file} Random.seed={task_id:d}"
       log.info(f"cmdstr: '{cmd}'")
       p = subprocess.Popen(cmd, shell=True)

       while True:
           res = p.poll()
           if res is not None:
               break

**Step 1** — ``setup_jobscript_logging_and_dir()`` reads
``$SLURM_ARRAY_TASK_ID``, uses ``index.json`` to find the matching
``run_<N>/`` directory, changes into it, and returns the logger, task id,
directory path, and input filename.

**Step 2** — ``load_slurm_config()`` reads ``slurm.toml`` and returns the
merged configuration dict.  Retrieve the MPI launcher with
``slurm.get('mpi', 'mpirun')``.

**Step 3** — Build a shell command string and run it with ``subprocess.Popen``.
The ``main`` symlink in the run directory points to the executable in the
parent stage directory.
