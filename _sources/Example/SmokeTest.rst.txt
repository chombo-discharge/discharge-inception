.. _example_smoke_test:

Running a smoke test
====================

Verify the binary works before submitting any SLURM jobs.  The default
``master.inputs`` sets ``app.mode = inception``:

.. code-block:: bash

   cd Exec/Rod
   mpirun -n 4 ./main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex master.inputs

This runs a stationary inception-voltage sweep on the default rod geometry at
1 atm.  Results are written to ``report.txt``; plot files go to ``plt/``.

To test plasma mode instead, override the mode (and optionally the voltage) on
the command line -- ParmParse arguments appended after the input filename take
precedence over the file:

.. code-block:: bash

   mpirun -n 4 ./main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex master.inputs \
       app.mode=plasma \
       plasma.voltage=40E3

Any ``master.inputs`` key can be overridden this way.

.. note::

   The ``plasma.voltage`` key sets the constant applied voltage (in V) for the
   ItoKMC plasma simulation.  The inception sweep does not use this value.
