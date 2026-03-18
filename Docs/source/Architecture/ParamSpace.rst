.. _arch_param_space:

Defining parameter spaces
=========================

A ``parameter_space`` is a dictionary whose keys are parameter names.  Each
value is another dictionary with these fields:

``database``
   (optional) Identifier of the database this parameter is linked to.
   Parameters that carry ``"database"`` create a SLURM ``afterok`` dependency
   between the study and the named database, and they restrict the Cartesian
   product to only the combinations that exist in the database.

``target``
   Filename (relative to the run directory) of the file to modify.  Can be a
   ``*.inputs`` ParmParse file or a ``*.json`` file.

``uri``
   Address of the value to change within the target file.  For ``*.inputs``
   files this is a dot-separated ParmParse key string.  For ``*.json`` files
   this is a list of nested dictionary keys; see :ref:`arch_json_uri` for
   special syntax.

``values``
   List of values.  Each element becomes one point in the parameter space.
   A 2nd-order list (list of lists) drives *multiple simultaneous writes* to
   parallel targets.

``group``
   (optional) A string label.  Parameters that share the same ``"group"``
   value are **zipped together** — they vary simultaneously rather than
   independently.  All parameters in a group must have the same number of
   values.  Groups (and ungrouped parameters) are still combined with each
   other via the Cartesian product.

The Cartesian product of all ``values`` lists determines the number of runs.
Database-linked parameters restrict that product to matching combinations.

.. code-block:: python

   'parameter_space': {
       "pressure": {
           "target": "chemistry.json",
           "uri": ["gas", "law", "ideal_gas", "pressure"],
           "values": [1e5, 2e5, 3e5]        # factor 3
       },
       "geometry_radius": {
           "target": "master.inputs",
           "uri": "Rod.radius",
           "values": [1e-3, 2e-3]           # factor 2
       }
   }

The above yields 6 run directories (3 × 2).

.. rubric:: Linked parameter groups

Sometimes two parameters are physically coupled and should always vary
*together*.  Adding a ``"group"`` field to each causes them to be zipped
rather than crossed:

.. code-block:: python

   'parameter_space': {
       "pressure": {
           "group": "thermo",
           "target": "chemistry.json",
           "uri": ["gas", "law", "ideal_gas", "pressure"],
           "values": [1e5, 2e5, 3e5]        # \
       },                                    #  zipped: 3 pairs
       "temperature": {                      # /
           "group": "thermo",
           "target": "chemistry.json",
           "uri": ["gas", "temperature"],
           "values": [300, 400, 500]
       },
       "radius": {
           "target": "master.inputs",
           "uri": "Rod.radius",
           "values": [100e-6, 500e-6]        # factor 2
       }
   }

The ``"thermo"`` group produces 3 pairs ``(pressure, temperature)``:
``(1e5, 300)``, ``(2e5, 400)``, ``(3e5, 500)``.  Those 3 pairs are then
crossed with the 2 radii, giving **6 run directories** instead of the 18
that an unconstrained Cartesian product would produce.

All parameters in the same group must have the same number of values; a
mismatch raises a ``ValueError`` at configuration time.
