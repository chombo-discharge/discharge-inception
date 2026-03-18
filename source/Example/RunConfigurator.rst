.. _example_run_configurator:

Running the configurator
========================

.. code-block:: bash

   cd Exec/Rod/Studies
   inception run RadiusStudy.py \
       --output-dir ~/my_rod_study \
       --dim 2 \
       --verbose

The configurator does four things:

1. Creates the output directory tree (``pdiv_database/``, ``plasma_simulations/``,
   and all ``run_N/`` subdirectories).
2. Copies executables, input files, job scripts, and data files into place.
3. Submits a SLURM array job for the database (``pdiv_database/``).
4. Submits a second SLURM array job for the study (``plasma_simulations/``),
   chained to depend on the database job completing first.

See :ref:`arch_cli` for all available options.
