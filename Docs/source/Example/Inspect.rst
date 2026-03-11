.. _example_inspect:

Inspecting results
==================

Use ``discharge-inception ls`` to see a table of runs with their parameter values and
completion status:

.. code-block:: bash

   discharge-inception ls ~/my_rod_study/pdiv_database/

Example output::

   ~/my_rod_study/pdiv_database  (3 runs)
     run     geometry_radius  pressure
     -------  ---------------  --------
     run_0    0.0001           100000  [done]
     run_1    0.0005           100000  [done]
     run_2    0.001            100000

The [done] mark indicates that ``report.txt`` is present in that run directory.

To inspect the exact parameters for a specific run:

.. code-block:: bash

   cat ~/my_rod_study/pdiv_database/run_0/parameters.json

.. code-block:: json

   {
       "geometry_radius": 0.0001,
       "pressure": 100000.0
   }

``index.json`` at the stage level maps run indices to parameter tuples — useful
for scripts that need to iterate all runs:

.. code-block:: bash

   cat ~/my_rod_study/pdiv_database/index.json

.. code-block:: json

   {
       "prefix": "run_",
       "keys": ["geometry_radius", "pressure"],
       "index": {
           "0": [0.0001, 100000.0],
           "1": [0.0005, 100000.0],
           "2": [0.001, 100000.0]
       }
   }
