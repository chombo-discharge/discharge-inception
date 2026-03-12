.. _postprocess_quickstart:

Quickstart
==========

After simulations have finished, a single command runs all post-processing
scripts in the correct order:

.. code-block:: console

   $ discharge-inception postprocess <db_dir>/

Here ``<db_dir>`` is the root folder of your study (the directory that contains
``pdiv_database/`` and ``plasma_simulations/`` as sub-directories).

The command searches for those sub-directories under ``<db_dir>``, runs each
tool in sequence, and writes all output under ``<db_dir>/Results/``, mirroring
the layout of the simulation directories.

Overview
--------

``postprocess`` runs the following steps in order:

1. **ExtractInceptionVoltages** on ``pdiv_database/`` ->
   ``Results/pdiv_database/inception_voltages.nc``

2. **GatherPlasmaEventLogs** on ``plasma_simulations/`` ->
   ``Results/plasma_simulations/plasma_event_log.csv``

3. For every ``run_N`` sub-directory in ``plasma_simulations/``:

   a. **PlotDeltaERel** -> ``Results/plasma_simulations/run_N/delta_e_rel.png``
      and ``Results/plasma_simulations/run_N/delta_e_rel.csv``
   b. **PlotDeltaE** -> ``Results/plasma_simulations/run_N/peak_delta_e.png``
      and ``Results/plasma_simulations/run_N/peak_delta_e.csv``

.. note::

   Individual tools can also be run directly -- see their own pages for
   standalone usage and additional options.

Optional flags let you override the default directory names and run prefix:

- ``--pdiv-db DIRNAME`` (default: ``pdiv_database``)
- ``--plasma-sim DIRNAME`` (default: ``plasma_simulations``)
- ``--run-prefix PREFIX`` (default: ``run_``, overridden automatically by the
  ``prefix`` key in ``index.json`` when present)

Inspecting results
------------------

After post-processing completes, use ``list-results`` to get an overview of
every output file:

.. code-block:: console

   $ discharge-inception list-results <db_dir>/

Example output:

.. code-block:: text

   Results in <db_dir>/  (8 files in 4 folders)

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

All output lives under ``<db_dir>/Results/``, mirroring the layout of the
simulation directories.  The ``plasma_event_log.csv`` gives a per-run status
summary; use ``plasma-status`` for a quick formatted view:

.. code-block:: console

   $ discharge-inception plasma-status <db_dir>/plasma_simulations/

For more detail on the individual post-processing tools, see
:ref:`postprocess_gatherplasmaeventlogs` and the pages for each tool linked in
the sidebar.
