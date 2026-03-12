.. _arch_dummy_params:

Dummy parameters
================

A *dummy* parameter has no ``target`` or ``uri`` -- only a ``name`` and a
``values`` list (and optionally ``database``).  It passes configuration options
to jobscripts through ``parameters.json`` without modifying any simulation
input files.

A dummy parameter with a **single value** does not expand the parameter space
(contributes a factor of 1 to run count):

.. code-block:: python

   main_study = {
       ...
       "parameter_space": {
           "K_min": {
               "values": [6.0]    # single value -- does not add runs
           },
       }
   }

The value is still written to ``index.json``, ``structure.json``, and
``parameters.json``, making it available to jobscripts at runtime.
