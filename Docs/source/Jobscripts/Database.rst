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

   from discharge_inception.config_util import (
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
