.. _example_monitor:

Monitoring jobs
===============

Use ``discharge-inception status`` for a structured per-run view:

.. code-block:: bash

   discharge-inception status ~/my_rod_study/pdiv_database/
   discharge-inception status ~/my_rod_study/plasma_simulations/

   # or inspect both in one call:
   discharge-inception status ~/my_rod_study/

Example output while the database is still running::

   ~/my_rod_study/pdiv_database/  (3 runs, job 98765)
     run     state
     ------  ---------
     run_0   completed
     run_1   running
     run_2   pending
     Summary: 1 completed, 1 running, 1 pending

For a raw queue listing use ``squeue`` directly::

   squeue -u $USER

The study job will remain in ``Pending`` state (dependency not yet satisfied)
until the database job finishes successfully.
