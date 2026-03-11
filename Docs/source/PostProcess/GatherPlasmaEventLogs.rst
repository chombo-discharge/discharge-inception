.. _postprocess_gatherplasmaeventlogs:

Identifying discharge inception events from plasma logs
=======================================================

Overview
--------

``GatherPlasmaEventLogs.py`` scans a plasma simulation database directory and
reads the tail of each run's ``pout.0`` log file to extract final simulation
state and event information.  It writes a structured CSV file and always prints
a human-readable summary table to standard output.

The following information is extracted for every run:

* **final_step** — last reported time-step number
* **final_time** — last reported simulation time
* **final_dt** — last reported time-step size
* **inception** — whether a discharge inception event was detecte d
* **convergence_failures** — number of Poisson solver convergence failures
* **other_abort** — whether any other unexpected abort was found
* **status** — derived run outcome: ``completed``, ``inception``,
  ``convergence_failure``, ``abort``, or ``not_found``

Status is assigned with the following priority (highest first):
``not_found`` -> ``inception`` -> ``convergence_failure`` -> ``abort`` ->
``completed``.

The script reads ``index.json`` (required) and ``structure.json`` (optional,
used to preserve the intended parameter ordering) from the database root
directory.

.. note::

   **Optional dependency**

   ``matplotlib`` — required only when ``--plot`` is used.  If it is absent
   the script exits with an error when plotting is requested.  Install with::

      pip install matplotlib

   No optional packages are needed for basic CSV extraction.


Options
-------

.. option:: db_dir

   *Positional (required).* Path to the plasma simulation database directory.
   The directory must contain an ``index.json`` file.

.. option:: --output PATH

   Path for the output CSV file.  Defaults to
   ``<db_dir>/plasma_event_log.csv``.

.. option:: --tail N

   Number of lines to read from the end of each ``pout.0`` file (default:
   ``50``).

.. option:: --plot PARAM

   Generate an interactive Matplotlib scatter plot of final simulation time
   vs. *PARAM*, colour-coded by run status.  *PARAM* must match a key defined
   in ``index.json``.  Requires ``matplotlib``.

.. option:: --no-output

   Skip writing the CSV file.  Only the summary table is printed to stdout.


Example
-------

Gather event logs from a completed database and write the default CSV::

   python PostProcess/GatherPlasmaEventLogs.py results/plasma_db

Read only the last 100 lines of each log and write to a custom path::

   python PostProcess/GatherPlasmaEventLogs.py \
       results/plasma_db \
       --tail 100 \
       --output results/event_summary.csv

Print the summary table without writing any file, then show a scatter plot of
final time vs the ``voltage`` parameter::

   python PostProcess/GatherPlasmaEventLogs.py \
       results/plasma_db \
       --no-output \
       --plot voltage
