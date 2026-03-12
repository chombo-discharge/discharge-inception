.. _jobscripts_plasma:

Specifying the plasma simulation options
========================================

``Scripts/PlasmaJobscript.py`` is the jobscript for the **plasma stage**.  For each
parameter combination it:

1. Reads the database results produced by the inception stage.
2. Selects voltages that fall within the configured K-range.
3. Creates a per-voltage subdirectory for each selected voltage.
4. Submits the voltage SLURM array (one task per voltage).

The script does not need to be edited directly.  Runtime behaviour is controlled through
the ``job_script_options`` block in the run definition.

job_script_options reference
-----------------------------

All keys are read from ``parameters.json`` at runtime.

.. list-table::
   :header-rows: 1
   :widths: 20 12 18 50

   * - Key
     - Type
     - Default
     - Description
   * - ``plasma_polarity``
     - ``str``
     - both
     - ``'positive'`` selects K(+) voltages only; ``'negative'`` selects K(-) voltages
       only.  Omit the key (or set it to ``'both'``) to include both polarities.
   * - ``K_min``
     - ``float``
     - ``0``
     - Lower bound on the ionisation integral.  Database rows with K below this value
       are excluded.
   * - ``K_max``
     - ``float``
     - from ``.inputs``
     - Upper bound on the ionisation integral.  If not set, the value of
       ``DischargeInceptionStepper.limit_max_K`` from the ``.inputs`` file is used as
       the fallback.
   * - ``N_voltages``
     - ``int``
     - all rows
     - If set, interpolates *N* evenly-spaced voltage points per polarity instead of
       using the raw report rows from the database.
   * - ``particle_mode``
     - ``str``
     - ``'single'``
     - ``'single'`` -- launches one seed electron per task.  ``'sphere'`` -- distributes
       seed electrons over a sphere.
   * - ``num_particles``
     - ``int``
     - ``1``
     - Particle weight in ``'single'`` mode, or total particle count in ``'sphere'``
       mode.
   * - ``sphere_radius``
     - ``float``
     - --
     - Sphere radius in metres.  **Required** when ``particle_mode='sphere'``.
   * - ``sphere_center``
     - ``list[float]``
     - interpolated
     - Explicit sphere centre as ``[x, y, z]``.  Defaults to the K-weighted position
       read from the database.

Caveats
-------

Initial particle structure must exist in ``chemistry.json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The plasma jobscript injects the electron seed position (and weight or sphere
parameters) into each ``voltage_<i>/chemistry.json`` by traversing the JSON
tree with a **required** path match (``+["id"="e"]`` -> ``initial particles``
-> ``+["single particle"]`` or ``+["sphere distribution"]``).  A required match
raises a hard error if the target element is absent -- it will not auto-create
the structure.

The ``chemistry.json`` template in the study directory **must** therefore
already contain the appropriate ``initial particles`` block under the electron
species entry before any plasma runs are submitted.  The expected skeleton is:

.. code-block:: json

   {
     "plasma species": [
       {
         "id": "e",
         "initial particles": [
           {
             "single particle": {
               "position": [0, 0, 0],
               "weight": 1
             }
           }
         ]
       }
     ]
   }

For ``particle_mode='sphere'`` the inner element should instead be
``"sphere distribution"`` with at least the ``"center"``, ``"radius"``, and
``"num particles"`` fields.  The script overwrites the placeholder values at
runtime, but the enclosing structure must already exist.

Omitting this block produces the error::

   RuntimeError: missing list element has requirement

at ``config_util.set_nested_value`` when the voltage directories are created.

Parameter space and input overrides
-------------------------------------

The plasma stage supports the same ``parameter_space`` and ``input_overrides`` syntax
as the database stage.  See :ref:`arch_run_definition` for details.

Example
-------

The following snippet shows a ``job_script_options`` block inside a run definition:

.. code-block:: json

   {
     "run_name": "rod_plasma",
     "jobscript": "Scripts/PlasmaJobscript.py",
     "parameter_space": {
       "gas_pressure": [1e5, 2e5, 4e5]
     },
     "job_script_options": {
       "plasma_polarity": "positive",
       "K_min": 0.5,
       "K_max": 5.0,
       "N_voltages": 10,
       "particle_mode": "sphere",
       "num_particles": 500,
       "sphere_radius": 1e-4
     }
   }
