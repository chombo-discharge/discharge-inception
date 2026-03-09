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
   from discharge_inception.config_util import (
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
