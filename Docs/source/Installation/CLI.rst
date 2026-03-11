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
       run                   Configure and submit a parametric study.
       ls                    List runs and parameter settings in a study directory.
       analyze-time-series   Extract, smooth, differentiate, and filter time-series
                             data from a plasma log.
       extract-inception-voltages
                             Extract inception voltages from a pdiv_database and
                             write NetCDF/CSV.
       gather-plasma-event-logs
                             Gather plasma event logs from a database and write a
                             CSV summary.
       plot-delta-e-rel      Batch-plot Delta E(rel) vs time for every run in a plasma
                             database.

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
