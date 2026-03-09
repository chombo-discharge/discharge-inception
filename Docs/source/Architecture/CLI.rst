.. _arch_cli:

The CLI
=======

``discharge-inception run``
---------------------------

Sets up directory structure and submits the initial SLURM array jobs.

.. code-block:: text

   usage: discharge-inception run [-h] [--output-dir OUTPUT_DIR] [--dim DIM]
                           [--verbose] [--logfile LOGFILE]
                           run_definition

   positional arguments:
     run_definition        Parameter space definition (.json or .py with top_object).

   options:
     -h, --help            show this help message and exit
     --output-dir OUTPUT_DIR
                           Output directory for study result files. (default: study_results)
     --dim DIM             Dimensionality of simulations. Must match chombo-discharge
                           compilation. (default: 3)
     --verbose             Increase verbosity.
     --logfile LOGFILE     Log file; rotated automatically each invocation.
                           (default: configurator.log)

``discharge-inception ls``
--------------------------

Prints a table of runs, parameter values, and completion status (✓ if
``report.txt`` is present).

.. code-block:: text

   usage: discharge-inception ls [-h] study_dir [study_dir ...]

   positional arguments:
     study_dir   Study output directory containing index.json (e.g. pdiv_database/).

Example output::

   ~/my_rod_study/PDIV_DB  (2 runs)
     run  pressure  geometry_radius  K_max
     ---  --------  ---------------  -----
     run_0  100000  0.001            12  ✓
     run_1  200000  0.001            12
