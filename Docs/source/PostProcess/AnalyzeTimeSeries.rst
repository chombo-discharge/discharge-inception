.. _postprocess_analyzetimeseries:

Analysing simulation time-series output
========================================

Overview
--------

``AnalyzeTimeSeries.py`` reads a block-wise ASCII plasma simulation log
(typically ``pout.0``) and produces a clean, aligned 10-column ``.dat`` file
together with an interactive Matplotlib figure.

For every ``Driver::Time step report`` block the script extracts eight physical
fields:

.. list-table::
   :header-rows: 1
   :widths: 10 20 70

   * - Column
     - Name
     - Description
   * - 1
     - Time
     - Simulation time
   * - 2
     - dt
     - Time-step size
   * - 3
     - Delta E(max)
     - Maximum relative electric field change (%)
   * - 4
     - Delta E(rel)
     - Mean relative electric field change (%)
   * - 5
     - Q (ohmic)
     - Ohmic charge (C)
   * - 6
     - Q (electrode)
     - Electrode charge (C)
   * - 7
     - Sum (phi_optical)
     - Integrated optical ionisation source (dimensionless)
   * - 8
     - Sum (src_optical)
     - Integrated optical source rate (1/s)

Two further columns are derived by finite differentiation of the charge columns:

.. list-table::
   :header-rows: 1
   :widths: 10 20 70

   * - Column
     - Name
     - Description
   * - 9
     - I (ohmic)
     - Ohmic current dQ\ :sub:`ohmic`/dt  (A)
   * - 10
     - I (electrode)
     - Electrode current dQ\ :sub:`electrode`/dt  (A)

The processing pipeline is:

1. Parse all time-step blocks from the log.
2. Optionally smooth columns 3-6 with a **Savitzky-Golay** filter (``--sg``).
3. Compute columns 9-10 as finite-difference derivatives of the (possibly
   smoothed) Q columns.
4. Optionally apply a **bidirectional exponential moving average** low-pass
   filter to columns 9-10 (``--lp``).
5. Write the aligned ``.dat`` file with a commented column header.
6. Display a 2 x 4 Matplotlib figure of columns 3--10 vs time.

The output file always begins with commented lines documenting the column
layout, and all values are written in 8-digit scientific notation.

.. note::

   **Optional dependencies**

   * ``scipy`` — required when ``--sg`` is used.  Install with::

        pip install scipy

   * ``matplotlib`` — required for the interactive plot.  If absent, a warning
     is printed and the script continues without plotting.  Install with::

        pip install matplotlib

   Neither package is needed to write the ``.dat`` file without smoothing.


Options
-------

.. option:: -i PATH, --input PATH

   Path to the input ASCII log file.  Defaults to ``pout.0`` in the current
   working directory.

.. option:: -o PATH, --output PATH

   Path for the output ``.dat`` file.  Defaults to the input file's directory
   with the extension replaced by ``.out`` (e.g. ``run_0/pout.out`` when the
   input is ``run_0/pout.0``).

.. option:: --sg

   Apply Savitzky-Golay smoothing to columns 3-6 (Delta E and Q columns)
   before computing the derivative columns.  Requires ``scipy``.

.. option:: --sg-window N

   Savitzky-Golay window length (default: ``9``).  Must be odd and greater
   than ``--sg-order``; the value is automatically reduced if necessary to fit
   the data length.

.. option:: --sg-order N

   Savitzky-Golay polynomial order (default: ``3``).  Must be strictly less
   than ``--sg-window``.

.. option:: --lp

   Apply a bidirectional exponential moving average low-pass filter to the
   derivative columns 9-10 after differentiation.  Requires ``--lp-tau``.

.. option:: --lp-tau TAU

   EMA time constant :math:`\tau` in seconds (default: none).  Required when ``--lp`` is
   set.  Smaller values pass more high-frequency content; larger values smooth
   more aggressively.


Example
-------

Extract and write the default output without any filtering::

   python PostProcess/AnalyzeTimeSeries.py -i run_0/pout.0 -o run_0/pout.out

Apply Savitzky-Golay smoothing (window 15, order 3) before differentiating::

   python PostProcess/AnalyzeTimeSeries.py \
       -i run_0/pout.0 \
       -o run_0/pout.out \
       --sg --sg-window 15 --sg-order 3

Smooth the Q columns and then low-pass filter the resulting currents with a
time constant of 1 ns::

   python PostProcess/AnalyzeTimeSeries.py \
       -i run_0/pout.0 \
       --sg \
       --lp --lp-tau 1e-9
