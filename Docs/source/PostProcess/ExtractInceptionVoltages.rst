.. _postprocess_extractinceptionvoltages:

Extracting partial discharge inception voltages
================================================

Overview
--------

``ExtractInceptionVoltages.py`` scans a ``pdiv_database`` directory and collects
the six inception voltages written by DischargeInceptionStepper into each run's
``report.txt`` file.  It assembles these values into a structured dataset indexed
by the sweep parameters and writes either a NetCDF file (default) or a CSV file.
A summary table is always printed to standard output.

The six voltage quantities extracted are:

* **Minimum inception voltage** — positive and negative polarity
* **Streamer inception voltage** — positive and negative polarity
* **Townsend inception voltage** — positive and negative polarity

Values that the solver could not compute (stored internally as ``DBL_MAX``) are
replaced with ``NaN`` in the output.

The script reads ``index.json`` (required) and ``structure.json`` (optional, used
to preserve the intended coordinate ordering) from the database root directory.

.. note::

   **Optional dependencies**

   * ``xarray`` — required for the default NetCDF output format and for all
     plotting functionality.  If it is not installed, use ``--format csv`` to
     produce a plain CSV file instead.  Install with::

        pip install xarray netcdf4

   * ``matplotlib`` — required only when ``--plot`` is used.  If it is absent
     the script exits with an error when plotting is requested.  Install with::

        pip install matplotlib

   Neither package is needed for basic CSV extraction.


Options
-------

.. option:: db_dir

   *Positional (required).* Path to the ``pdiv_database`` directory.  The
   directory must contain an ``index.json`` file.

.. option:: --output PATH

   Path for the output file.  Defaults to ``<db_dir>/inception_voltages.nc``
   (NetCDF) or ``<db_dir>/inception_voltages.csv`` (CSV).

.. option:: --format {netcdf,csv}

   Output format.  ``netcdf`` (default) writes a multi-dimensional xarray/NetCDF
   dataset.  ``csv`` writes a flat table with one row per run.  Use ``csv`` when
   ``xarray`` is not available.

.. option:: --plot PARAM [PARAM]

   Generate an interactive Matplotlib figure after writing the output file.
   Supply one parameter name for a line plot (inception voltage vs. that
   parameter) or two parameter names for a pair of heat-maps.  Parameters must
   match keys defined in ``index.json``.  Requires both ``xarray`` and
   ``matplotlib``.

.. option:: --select KEY=VALUE [KEY=VALUE ...]

   When plotting, fix one or more sweep parameters at the given values so that a
   lower-dimensional slice can be displayed.  For each dimension not listed in
   ``--plot`` and not covered by ``--select``, the script defaults to the first
   available coordinate value and prints a warning.  Example:
   ``--select pressure=1e5 temperature=300``.

.. option:: --voltage {min,streamer,townsend,all}

   Filter which voltage type(s) appear in the plot.  Defaults to ``all``.  Has
   no effect on the written output file.


Example
-------

Extract all inception voltages from a completed database into a NetCDF file,
then display a line plot of all three voltage types against the ``gap_distance``
parameter::

   python PostProcess/ExtractInceptionVoltages.py \
       results/pdiv_database \
       --plot gap_distance

To run without ``xarray`` installed, write a CSV instead::

   python PostProcess/ExtractInceptionVoltages.py \
       results/pdiv_database \
       --format csv \
       --output results/inception_voltages.csv

For a two-parameter sweep over ``gap_distance`` and ``pressure``, produce heat-maps
showing only the streamer inception voltage::

   python PostProcess/ExtractInceptionVoltages.py \
       results/pdiv_database \
       --plot gap_distance pressure \
       --voltage streamer
