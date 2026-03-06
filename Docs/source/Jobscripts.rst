Writing Jobscripts
******************

.. contents::
   :local:
   :depth: 2

.. _jobscripts_where_fit:

Where jobscripts fit
====================

``discharge-ps run`` sets up the directory structure and submits SLURM array
jobs, but the actual simulation work is done by *jobscripts* — Python scripts
that run inside each SLURM task.  ``GenericArrayJob.sh`` is the SLURM entry
point; it activates the environment and then calls
``python ./jobscript_symlink``, which resolves to the specific jobscript for
that stage.

See :ref:`arch_call_chain` for a full picture of how the pieces connect.

.. _jobscripts_generic_array:

GenericArrayJob.sh — the SLURM wrapper
=======================================

``Util/GenericArrayJob.sh`` is the **only** ``#SBATCH`` script in the project.
It contains no hardcoded resource requests (nodes, tasks, time, account).
Instead, resource values are injected at submission time by the Python
jobscripts via ``build_sbatch_resource_args()``, which reads ``slurm.toml``
(see :ref:`arch_slurm_config`).

The only ``#SBATCH`` directives it does contain redirect stdout/stderr to
per-array-task log files:

.. code-block:: bash
   :caption: Util/GenericArrayJob.sh

   #!/bin/bash
   # Generic SLURM array job launcher for discharge-parametric-studies.
   #
   # Resource requests (account, partition, ntasks, time) are intentionally
   # absent here so the script is portable across clusters. Supply them via:
   #   - sbatch CLI arguments:  sbatch --account=X --ntasks=N --time=HH:MM:SS ...
   #   - SLURM environment variables: export SBATCH_ACCOUNT=X before submitting
   #   - The Python job scripts read slurm.toml and pass these automatically
   #     when they invoke sbatch themselves (e.g. for the voltage sub-array).

   #SBATCH --output=R-%x.%A-%a.out
   #SBATCH --error=R-%x.%A-%a.err

   set -o errexit
   set -o nounset

   # Load cluster modules listed in slurm.toml (requires DISCHARGE_PS_SLURM_CONFIG
   # to be set and exported before submitting the job). Uses the system python3
   # (before venv activation) to parse the TOML. The block is skipped entirely on
   # systems without the 'module' command or without the config file.
   if command -v module > /dev/null 2>&1 \
           && [ -n "${DISCHARGE_PS_SLURM_CONFIG:-}" ] \
           && [ -f "${DISCHARGE_PS_SLURM_CONFIG}" ]; then
       while IFS= read -r mod; do
           [ -n "$mod" ] && module load "$mod"
       done < <(python3 -c "
   import sys, tomllib
   with open(sys.argv[1], 'rb') as f:
       c = tomllib.load(f)
   for m in c.get('slurm', {}).get('modules', []):
       print(m)
   " "${DISCHARGE_PS_SLURM_CONFIG}")
   fi

   if [ -n "${DISCHARGE_PS_VENV:-}" ]; then
       source "$DISCHARGE_PS_VENV/bin/activate"
   fi

   python ./jobscript_symlink
   exit $?

``GenericArrayJob.sh`` must be listed as a ``job_script_dependency`` in every
run definition entry so the configurator copies it into the stage directory
(see :ref:`arch_run_definition`).

.. _jobscripts_setup_helper:

Standard jobscript setup — the helper
======================================

Every jobscript begins by calling two helpers from ``discharge_ps.config_util``:

.. code-block:: python

   from discharge_ps.config_util import setup_jobscript_logging_and_dir, load_slurm_config

``setup_jobscript_logging_and_dir(prefix=None)``
   Reads ``$SLURM_ARRAY_TASK_ID``, sets up a ``logging`` instance, locates the
   run directory for this task (using ``index.json`` for leaf-level scripts or
   ``prefix`` from ``structure.json`` for study scripts), changes into it, and
   finds the ``*.inputs`` file.

   Returns a 4-tuple ``(log, task_id, run_dir, input_file)``.

   * ``log`` — configured ``logging.Logger``
   * ``task_id`` — integer SLURM array task index
   * ``run_dir`` — ``pathlib.Path`` to the current run directory
   * ``input_file`` — filename of the ``*.inputs`` file in that directory

   Pass ``prefix`` explicitly when reading it from ``structure.json`` (study
   scripts) rather than using the default ``"run_"`` prefix.

``load_slurm_config(stage=None)``
   Reads ``slurm.toml`` (via ``DISCHARGE_PS_SLURM_CONFIG``) and returns the
   merged configuration dict for the requested stage.  Keys at
   ``[slurm.<stage>]`` override top-level ``[slurm]`` defaults.

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
   Author André Kapelrud
   Copyright © 2025 SINTEF Energi AS
   """

   import sys
   import subprocess

   from discharge_ps.config_util import setup_jobscript_logging_and_dir, load_slurm_config


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

.. _jobscripts_database:

Writing a database jobscript
=============================

A database jobscript runs the solver, inspects the results, and conditionally
reruns with updated parameters.  The example below closely follows the actual
``DischargeInceptionJobscript.py``:

.. code-block:: python
   :caption: DischargeInceptionJobscript.py
   :linenos:

   #!/usr/bin/env python

   import sys
   import math
   import shutil
   import subprocess
   import time

   sys.path.append(os.getcwd())  # needed for local ParseReport import
   from ParseReport import parse_report_file

   from discharge_ps.config_util import (
       setup_jobscript_logging_and_dir, load_slurm_config,
       handle_combination, read_input_float_field,
   )

   if __name__ == '__main__':

       # Step 1: Navigate to run directory
       log, task_id, run_dir, input_file = setup_jobscript_logging_and_dir()

       # Step 2: Load SLURM config
       slurm = load_slurm_config()
       mpi = slurm.get('mpi', 'mpirun')

       # Step 3: Run the inception solver
       cmd = (f"{mpi} main {input_file} app.mode=inception "
              f"Random.seed={task_id:d} Driver.max_steps=0 Driver.plot_interval=-1")
       log.info(f"cmdstr: '{cmd}'")
       p = subprocess.Popen(cmd, shell=True)
       while p.poll() is None:
           time.sleep(0.5)
       if p.returncode != 0:
           sys.exit(p.returncode)

       # Step 4: Parse results from report.txt
       report_data = parse_report_file('report.txt',
                                       ['+/- Voltage', 'Max K(+)', 'Max K(-)'])
       calculated_max_voltage = report_data[1][-1][0]
       log.info(f'DischargeInception found max voltage: {calculated_max_voltage}')

       # Step 5: Check if a rerun is needed
       orig_max_voltage = read_input_float_field(
           input_file, 'DischargeInceptionTagger.max_voltage')
       if orig_max_voltage is None:
           raise RuntimeError(f"missing 'DischargeInceptionTagger.max_voltage'")

       if orig_max_voltage < calculated_max_voltage:
           shutil.move('report.txt', 'report.txt.0')

           new_max_voltage = math.ceil(calculated_max_voltage / 1000) * 1000
           log.info(f'Setting DischargeInceptionTagger.max_voltage = {new_max_voltage}')

           # Step 6: Inject updated parameter and rerun (see arch_json_uri)
           handle_combination({
               "mesh_max_voltage": {
                   "target": input_file,
                   "uri": "DischargeInceptionTagger.max_voltage"
               }
           }, dict(mesh_max_voltage=new_max_voltage))

           log.info('Rerunning DischargeInception calculations')
           p = subprocess.Popen(cmd, shell=True)
           while p.poll() is None:
               time.sleep(0.5)
           sys.exit(p.returncode)

**Step 3** — ParmParse overrides (``app.mode=inception``, etc.) appended after
the ``*.inputs`` filename take precedence over the file contents — a common
pattern when a single binary supports multiple execution modes.

**Step 5** — ``read_input_float_field(file, key)`` reads a float value from a
``*.inputs`` file.  Returns ``None`` if the key is absent.

**Step 6** — ``handle_combination(pspace, comb_dict)`` writes parameter values
to their target files.  The ``pspace`` dict mirrors the parameter space syntax
from the run definition (see :ref:`arch_param_space` and :ref:`arch_json_uri`).

.. _jobscripts_study:

Writing a study jobscript
==========================

A study jobscript must:

1. Read ``structure.json`` to get the run prefix (the prefix may differ from
   the default ``"run_"``).
2. Navigate to the matching database run and parse its results.
3. Create per-voltage subdirectories and inject parameters.
4. Submit a child SLURM array for the voltage sweep.

The outline below follows ``PlasmaJobscript.py``:

.. code-block:: python
   :caption: PlasmaJobscript.py (outline)
   :linenos:

   import json
   from pathlib import Path
   from subprocess import Popen, PIPE
   from discharge_ps.config_util import (
       setup_jobscript_logging_and_dir, load_slurm_config,
       build_sbatch_resource_args, handle_combination,
       copy_files, backup_file, backup_dir, DEFAULT_OUTPUT_DIR_PREFIX
   )

   if __name__ == '__main__':

       # Step 1: Read structure.json to get the prefix, then set up
       with open('structure.json') as f:
           structure = json.load(f)
       prefix = structure.get('output_dir_prefix', DEFAULT_OUTPUT_DIR_PREFIX)
       log, task_id, run_dir, input_file = setup_jobscript_logging_and_dir(prefix=prefix)

       # Step 2: Navigate to the matching database run using index.json
       #         (see arch_output_dir for the index.json format)
       with open('../inception_stepper/structure.json') as f:
           db_structure = json.load(f)
       db_path = Path('..') / db_structure['identifier']

       with open(db_path / 'index.json') as f:
           db_index = json.load(f)

       with open('parameters.json') as f:
           parameters = json.load(f)

       db_run_path = find_database_run(parameters, db_structure, db_index)

       # Step 3: Parse database results
       table = extract_voltage_table(db_run_path / 'report.txt', ...)

       # Step 4: Create voltage_<i>/ subdirectories and inject parameters
       #         (uses handle_combination — see arch_json_uri)
       create_voltage_directories(table, structure, input_file, parameters)

       # Step 5: Submit child SLURM array using build_sbatch_resource_args
       slurm = load_slurm_config()
       sbatch_args = (['--array=0-{}'.format(len(table) - 1),
                       '--job-name="{}_voltage"'.format(structure['identifier'])]
                      + build_sbatch_resource_args(slurm, stage='plasma'))
       cmdstr = 'sbatch ' + ' '.join(sbatch_args) + ' GenericArrayJob.sh'
       p = Popen(cmdstr, shell=True, stdout=PIPE, encoding='utf-8')
       ...

**Step 1** — Pass the ``prefix`` read from ``structure.json`` to
``setup_jobscript_logging_and_dir`` so it can find the correct run directory
even when the study uses a custom ``output_dir_prefix``.

**Step 2** — ``index.json`` maps integer task IDs to parameter tuples; see
:ref:`arch_output_dir` for the full format.  The ``inception_stepper@`` symlink
in the study directory points directly to the database stage directory.

**Step 4** — ``create_voltage_directories()`` iterates the voltage table, calls
``copy_files()`` to populate each ``voltage_<i>/`` directory, and calls
``handle_combination()`` to inject the voltage and particle-position parameters.

**Step 5** — ``build_sbatch_resource_args(slurm, stage='plasma')`` returns a
list of ``sbatch`` flag strings built from the ``[slurm.plasma]`` section of
``slurm.toml`` — see :ref:`arch_slurm_config`.

.. _jobscripts_handle_combination:

Parameter injection with ``handle_combination()``
==================================================

``handle_combination(pspace, comb_dict)`` is the same function the configurator
uses to write parameter values into ``*.inputs`` and ``*.json`` files.  Calling
it from a jobscript lets you inject runtime-computed values (e.g. voltages from
a database result) using the same URI syntax as the run definition.

*  **``*.inputs`` target** — ``uri`` is a dot-separated ParmParse key:

   .. code-block:: python

      handle_combination(
          {"voltage": {"target": input_file, "uri": "plasma.voltage"}},
          {"voltage": 42000.0}
      )

*  **``*.json`` target** — ``uri`` is a list traversing the JSON hierarchy;
   see :ref:`arch_param_space` and :ref:`arch_json_uri` for syntax details.

The *fake pspace / comb_dict* pattern from ``PlasmaJobscript.py`` lets you
write multiple fields in one call:

.. code-block:: python

   comb_dict = dict(
       voltage=row[0],
       sphere_dist_props=[center_pos, tip_radius],
   )
   pspace = {
       "voltage": {
           "target": voltage_dir / input_file,
           "uri": "plasma.voltage",
       },
       "sphere_dist_props": {
           "target": voltage_dir / 'chemistry.json',
           'uri': [
               'plasma species',
               '+["id"="e"]',
               'initial particles',
               '+["sphere distribution"]',
               'sphere distribution',
               ['center', 'radius']   # two simultaneous writes
           ]
       },
   }
   handle_combination(pspace, comb_dict)
