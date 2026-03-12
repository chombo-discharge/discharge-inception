.. _arch_cli:

The CLI
=======

Overview
--------

All functionality is accessed through the ``discharge-inception`` command.
Run the following to see every available subcommand:

.. code-block:: console

   $ discharge-inception --help

.. code-block:: text

   usage: discharge-inception [-h] command ...

   Parametric study configurator for chombo-discharge simulations.

   positional arguments:
     command
       run                      Configure and submit a parametric study.
       ls                       List runs and parameter settings in a study directory.
       slurm-status             Show Slurm job status for one or more study directories.
       postprocess              Run all post-processing scripts on a study directory.
       plasma-status            Show per-run plasma simulation status from plasma_event_log.csv.
       list-results             List all post-processed result files in a study directory.
       analyze-time-series      Extract, smooth, differentiate, and filter time-series data from a plasma log.
       extract-inception-voltages
                                Extract inception voltages from a pdiv_database and write NetCDF/CSV.
       gather-plasma-event-logs Gather plasma event logs from a database and write a CSV summary.
       plot-delta-e-rel         Batch-plot Delta E(rel) vs time for every run in a plasma database.
       plot-delta-e             Plot peak Delta E(rel) and/or Delta E(max) vs voltage for a run_* database.

   options:
     -h, --help            show this help message and exit

Each subcommand accepts its own ``--help`` flag, e.g.::

   discharge-inception extract-inception-voltages --help

``discharge-inception run``
---------------------------

Sets up directory structure and submits the initial SLURM array jobs.

.. code-block:: text

   usage: discharge-inception run [-h] [--output-dir OUTPUT_DIR] [--dim DIM]
                           [--verbose] [--logfile LOGFILE]
                           [--pdiv-only]
                           [--overwrite | --suffix SUFFIX]
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
     --pdiv-only           Set up and submit only the inception (PDIV) database jobs;
                           skip all plasma study setup and Slurm submission.
     --overwrite           Overwrite the output directory if it already exists.
     --suffix SUFFIX       Append SUFFIX to the output directory name to avoid
                           conflicting with an existing directory (mutually exclusive
                           with --overwrite).

``discharge-inception ls``
--------------------------

Prints a table of runs, parameter values, and completion status (``[done]`` if
``report.txt`` is present).

.. code-block:: text

   usage: discharge-inception ls [-h] study_dir [study_dir ...]

   positional arguments:
     study_dir   Study output directory containing index.json (e.g. pdiv_database/).

Example output::

   ~/my_rod_study/PDIV_DB  (2 runs)
     run  pressure  geometry_radius  K_max
     ---  --------  ---------------  -----
     run_0  100000  0.001            12  [done]
     run_1  200000  0.001            12

``discharge-inception slurm-status``
--------------------------------------

Queries SLURM (via ``sacct``/``squeue``) and prints a live status table for
every run in one or more study directories.

.. code-block:: text

   usage: discharge-inception slurm-status [-h] [--no-voltage] study_dir [study_dir ...]

   positional arguments:
     study_dir      Study directory (containing index.json) or parent directory
                    containing multiple studies.

   options:
     -h, --help     show this help message and exit
     --no-voltage   Skip inner voltage array queries (faster).

Accepts a **study directory** (one that contains ``index.json``) or a **parent
output directory** whose sub-directories are studies -- in the latter case all
studies are reported in one pass.

For inception-stepper databases the table shows the outer array-job state and,
for failed tasks, the exit code:

.. code-block:: console

   $ discharge-inception slurm-status study_results/pdiv_database/

.. code-block:: text

   study_results/pdiv_database/  (4 runs, job 98765)
     run     state
     ------  ---------
     run_0   completed
     run_1   completed
     run_2   running
     run_3   pending
     Summary: 2 completed, 1 running, 1 pending

For plasma studies the table also shows a compact summary of each run's inner
voltage array:

.. code-block:: console

   $ discharge-inception slurm-status study_results/plasma_simulations/

.. code-block:: text

   study_results/plasma_simulations/  (2 runs, job 98766)
     run     state      voltages
     ------  ---------  --------
     run_0   completed  7/7 done
     run_1   running    running (3/7 done)
     Summary: 1 completed, 1 running

Pass ``--no-voltage`` to skip the inner voltage queries when the study has many
runs and a fast summary is sufficient.  Multiple directories can be combined in
a single call::

   discharge-inception slurm-status study_results/pdiv_database/ study_results/plasma_simulations/
   discharge-inception slurm-status study_results/   # auto-discovers all sub-studies

``discharge-inception postprocess``
-------------------------------------

Orchestrates the full post-processing pipeline on a study root directory.
The command locates the PDIV database and plasma simulation directories, runs
each post-processing tool in the correct order, and writes all output under
``<study_root>/Results/``.

.. code-block:: text

   usage: discharge-inception postprocess [-h] [--pdiv-db DIRNAME]
                                          [--plasma-sim DIRNAME]
                                          [--run-prefix PREFIX]
                                          study_root

   positional arguments:
     study_root            Root directory of the parametric study.

   options:
     -h, --help            show this help message and exit
     --pdiv-db DIRNAME     Name of the PDIV database sub-directory.
                           (default: pdiv_database)
     --plasma-sim DIRNAME  Name of the plasma simulations sub-directory.
                           (default: plasma_simulations)
     --run-prefix PREFIX   Prefix used for individual run directories inside the
                           plasma simulation directory. Overridden automatically
                           by the value stored in index.json when present.
                           (default: run_)

.. note::

   See :ref:`postprocess_quickstart` for a step-by-step walkthrough of the full
   post-processing workflow.

Example::

   discharge-inception postprocess PressureStudy_1/

``discharge-inception plasma-status``
---------------------------------------

Reads ``plasma_event_log.csv`` from the Results mirror and prints a formatted
per-run status table.  Accepts either the ``plasma_simulations/`` directory
(in which case the CSV is located automatically under ``Results/``) or a direct
path to the CSV file.

.. code-block:: text

   usage: discharge-inception plasma-status [-h] [--filter STATUS] plasma_sim

   positional arguments:
     plasma_sim      Path to the plasma_simulations/ directory or directly to
                     plasma_event_log.csv.

   options:
     -h, --help      show this help message and exit
     --filter STATUS Show only runs whose status matches STATUS (e.g. inception,
                     completed, convergence_failure, abort).

Examples::

   # Basic call -- pass the plasma_simulations/ directory
   discharge-inception plasma-status PressureStudy_1/plasma_simulations/

   # Pass the CSV file directly
   discharge-inception plasma-status PressureStudy_1/Results/plasma_simulations/plasma_event_log.csv

   # Show only runs that reached inception
   discharge-inception plasma-status PressureStudy_1/plasma_simulations/ --filter inception

``discharge-inception list-results``
--------------------------------------

Lists all post-processed result files grouped by sub-folder under ``Results/``,
giving a quick overview of every file produced by ``postprocess``.

.. code-block:: text

   usage: discharge-inception list-results [-h] study_root

   positional arguments:
     study_root   Root directory of the parametric study.

   options:
     -h, --help   show this help message and exit

Example::

   discharge-inception list-results PressureStudy_1/

.. code-block:: text

   Results in PressureStudy_1/  (8 files in 4 folders)

     pdiv_database/
       inception_voltages.nc

     plasma_simulations/
       plasma_event_log.csv

     plasma_simulations/run_0/
       delta_e_rel.csv
       delta_e_rel.png
       peak_delta_e.csv
       peak_delta_e.png

     plasma_simulations/run_1/
       ...

.. note::

   See :ref:`postprocess_quickstart` -> *Inspecting results* for guidance on
   interpreting the output.

``discharge-inception plot-delta-e``
--------------------------------------

Produces a dual-axis plot of peak Delta E(rel) and Delta E(max) vs voltage for a single
``run_*`` database.  This command is typically called automatically by
``postprocess`` for each run directory, but can also be invoked standalone for
custom output paths or to regenerate individual plots.

.. code-block:: text

   usage: discharge-inception plot-delta-e [-h] [--rel-field REL_FIELD]
                                           [--max-field MAX_FIELD]
                                           [--png PNG] [--output OUTPUT]
                                           db_dir

   positional arguments:
     db_dir              Path to the run_* directory containing the plasma database.

   options:
     -h, --help          show this help message and exit
     --rel-field REL_FIELD
                         Name of the relative field column in the database.
     --max-field MAX_FIELD
                         Name of the maximum field column in the database.
     --png PNG           Output path for the PNG figure.
     --output OUTPUT     Output path for the CSV summary of peak values.

Example::

   discharge-inception plot-delta-e plasma_simulations/run_0/

``discharge-inception analyze-time-series``
-------------------------------------------

Extracts, optionally smooths, and differentiates time-series data from a
plasma simulation log.  See :ref:`postprocess_analyzetimeseries` for full
documentation of options and output columns.

.. code-block:: text

   usage: discharge-inception analyze-time-series [-h] [-i INPUT] [-o OUTPUT]
                                                  [--sg] [--sg-window SG_WINDOW]
                                                  [--sg-order SG_ORDER] [--lp]
                                                  [--lp-tau LP_TAU]

Example::

   discharge-inception analyze-time-series -i run_0/pout.0 -o run_0/pout.out --sg

``discharge-inception extract-inception-voltages``
---------------------------------------------------

Extracts the six inception voltages from every run in a ``pdiv_database``
directory and writes a NetCDF or CSV dataset.  See
:ref:`postprocess_extractinceptionvoltages` for full documentation.

.. code-block:: text

   usage: discharge-inception extract-inception-voltages [-h] [--output OUTPUT]
                                                         [--format {netcdf,csv}]
                                                         [--plot PARAM [PARAM ...]]
                                                         [--select KEY=VALUE ...]
                                                         [--voltage {min,streamer,townsend,all}]
                                                         db_dir

Example::

   discharge-inception extract-inception-voltages study_results/pdiv_database

``discharge-inception gather-plasma-event-logs``
-------------------------------------------------

Scans the tail of each run's ``pout.0`` log, classifies every run as
completed, inception, convergence failure, or abort, and writes a CSV
summary.  See :ref:`postprocess_gatherplasmaeventlogs` for full documentation.

.. code-block:: text

   usage: discharge-inception gather-plasma-event-logs [-h] [--output PATH]
                                                       [--tail N] [--plot PARAM]
                                                       [--no-output]
                                                       db_dir

Example::

   discharge-inception gather-plasma-event-logs study_results/plasma_database

``discharge-inception plot-delta-e-rel``
-----------------------------------------

Batch-plots Delta E(rel) vs time for every run in a plasma database, saving one
PNG per run.  See :ref:`postprocess_plotdeltaerel` for full documentation.

.. code-block:: text

   usage: discharge-inception plot-delta-e-rel [-h] [--prefix PREFIX]
                                               [--output-dir DIR]
                                               db_dir

Example::

   discharge-inception plot-delta-e-rel study_results/plasma_database --output-dir plots/
