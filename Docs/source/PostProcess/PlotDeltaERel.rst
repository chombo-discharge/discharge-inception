.. _postprocess_plotdeltaerel:

Plotting relative electric field change over time
=================================================

Overview
--------

``PlotDeltaERel.py`` is a batch plotting tool that produces one PNG figure per
run in a plasma simulation database.  For each run it reads the corresponding
``{prefix}{run_id}.0`` log file, extracts the simulation time and the relative
electric field change :math:`\Delta` E(rel) at every reported time step, and saves a labelled
PNG file.

.. note::

   This script targets an older database layout in which the log files sit
   directly inside the database root directory (e.g. ``pout0.0``, ``pout1.0``,
   ...) rather than in per-run sub-directories.  The file prefix can be changed
   with ``--prefix``.

The figure for each run shows:

* **x-axis** — simulation time in nanoseconds
* **y-axis** — :math:`\Delta` E(rel) (%)
* **title** — the sweep-parameter key/value pairs for that run as read from
  ``index.json``

Output PNGs are named ``plt_0.png``, ``plt_1.png``, ... and written to
*db_dir* by default (or to a custom directory via ``--output-dir``).

**Required dependencies**: ``numpy`` and ``matplotlib``.


Options
-------

.. option:: db_dir

   *Positional (required).* Path to the plasma simulation database directory.
   The directory must contain an ``index.json`` file.

.. option:: --prefix PREFIX

   Prefix for the log filenames (default: ``pout``).  The script opens
   ``<db_dir>/<PREFIX><run_id>.0`` for each run.

.. option:: --output-dir DIR

   Directory in which output PNG files are saved (default: same as *db_dir*).
   The directory is created if it does not exist.


Example
-------

Plot :math:`\Delta` E(rel) for all runs in a database, saving PNGs alongside the log files::

   python PostProcess/PlotDeltaERel.py results/plasma_db

Use a non-default log prefix and write the figures to a dedicated plots folder::

   python PostProcess/PlotDeltaERel.py \
       results/plasma_db \
       --prefix run \
       --output-dir results/plasma_db/plots
