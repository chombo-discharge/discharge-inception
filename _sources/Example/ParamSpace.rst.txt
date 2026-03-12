.. _example_param_space:

Inspecting the parameter space definition
==========================================

Open ``Exec/Rod/Studies/RadiusStudy.py`` to inspect or adjust the parameter space.
The top-level structure is:

.. code-block:: python

   top_object = dict(
       databases=[inception_stepper],
       studies=[plasma_study]
   )

Both entries point to the flat ``Exec/Rod/`` directory:

.. code-block:: python

   rod_dir = '../'

**Database** (``inception_stepper``) -- computes inception voltages.  The free
parameters are determined by the plasma study entries that carry
``"database": "inception_stepper"`` (see below).  Fixed settings that apply to
every database run are collected in ``input_overrides``:

.. code-block:: python

   'input_overrides': {
       'mode': {
           'target': 'master.inputs',
           'uri': 'app.mode',
           'value': "inception"
       },
       "limit_max_K": {
           "target": "master.inputs",
           "uri": "DischargeInceptionStepper.limit_max_K",
           "value": 12
       },
       "max_steps": {
           "target": "master.inputs",
           "uri": "Driver.max_steps",
           "value": 0
       },
       "plot_interval": {
           "target": "master.inputs",
           "uri": "Driver.plot_interval",
           "value": -1
       },
   }

**Study** (``plasma_study``) -- runs plasma simulations using the database
results.  ``app.mode`` is set to ``plasma`` via ``input_overrides``.  Parameters
marked with ``"database": "inception_stepper"`` declare a SLURM dependency: study
jobs will not start until the corresponding database job has completed, and the
configurator ensures that each study run is paired with the matching database entry.

Plasma-only parameters (no ``"database"`` key) are swept independently:

.. code-block:: python

   'input_overrides': {
       'mode': {
           'target': 'master.inputs',
           'uri': 'app.mode',
           'value': "plasma"
       },
       "max_steps": {
           "target": "master.inputs",
           "uri": "Driver.max_steps",
           "value": 500
       },
   },
   'job_script_options': {
       'K_min': 6,
       'K_max': 12.0,
       'plasma_polarity': 'positive',
   },
   'parameter_space': {
       "geometry_radius": {
           "database": "inception_stepper",
           "target": "master.inputs",
           "uri": "Rod.radius",
           "values": [100E-6, 500E-6, 1e-3]
       },
       "pressure": {
           "database": "inception_stepper",
           "target": "chemistry.json",
           "uri": ["gas", "law", "ideal_gas", "pressure"],
           "values": [1e5]
       },
       "photoionization": {
           "target": "chemistry.json",
           "uri": [
               "photoionization",
               [
                   '+["reaction"=<chem_react>"Y + (O2) -> e + O2+"]',
                   '*["reaction"=<chem_react>"Y + (O2) -> (null)"]'
               ],
               "efficiency"
           ],
           "values": [[1.0, 0.0]]
       },
   }

The ``photoionization`` entry uses the ``<chem_react>`` match expression to
locate reaction entries in ``chemistry.json`` by their reaction string.  The
``+`` prefix requires the match to exist; ``*`` creates the entry if absent.
A Python list at any level of the ``uri`` produces multiple parallel writes --
here both reactions are written in a single parameter sweep step.

See :ref:`arch_param_space`, :ref:`arch_json_uri`, and :ref:`arch_db_study` for
a full explanation of parameter space syntax, JSON URI conventions, and database
dependencies.
