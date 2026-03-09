.. _example_run_configurator:

Running the configurator
========================

.. code-block:: bash

   cd Exec/Rod/Studies/PressureStudy
   discharge-inception run Runs.py \
       --output-dir ~/my_rod_study \
       --dim 2 \
       --verbose

The configurator does four things:

1. Creates the output directory tree (``PDIV_DB/``, ``study0/``, and all
   ``run_N/`` subdirectories).
2. Copies executables, input files, job scripts, and data files into place.
3. Submits a SLURM array job for the database (``PDIV_DB/``).
4. Submits a second SLURM array job for the study (``study0/``), chained to
   depend on the database job completing first.

See :ref:`arch_cli` for all available options.
