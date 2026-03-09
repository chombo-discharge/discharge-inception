.. _example_inspect:

Inspecting results
==================

Use ``discharge-inception ls`` to see a table of runs with their parameter values and
completion status:

.. code-block:: bash

   discharge-inception ls ~/my_rod_study/PDIV_DB/

Example output::

   ~/my_rod_study/PDIV_DB  (2 runs)
     run     pressure  geometry_radius  K_max
     -------  --------  ---------------  -----
     run_0    100000    0.001            12  ✓
     run_1    200000    0.001            12

The ✓ mark indicates that ``report.txt`` is present in that run directory.

To inspect the exact parameters for a specific run:

.. code-block:: bash

   cat ~/my_rod_study/PDIV_DB/run_0/parameters.json

.. code-block:: json

   {
       "pressure": 100000.0,
       "geometry_radius": 0.001,
       "K_max": 12.0
   }

``index.json`` at the stage level maps run indices to parameter tuples — useful
for scripts that need to iterate all runs:

.. code-block:: bash

   cat ~/my_rod_study/PDIV_DB/index.json

.. code-block:: json

   {
       "prefix": "run_",
       "keys": ["pressure", "geometry_radius", "K_max"],
       "index": {
           "0": [100000.0, 0.001, 12.0],
           "1": [200000.0, 0.001, 12.0]
       }
   }
