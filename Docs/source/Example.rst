Example — Rod Case
******************

.. contents::
   :local:
   :depth: 2

This chapter walks through the complete workflow for the ``Exec/Rod``
parametric study, from compilation through post-processing.

The Rod case demonstrates the **two-level database → study pipeline**:

1. A discharge-inception database sweeps over pressures and rod radii to
   compute inception voltages.
2. A full plasma simulation study uses those inception voltages as its input,
   creating a sub-hierarchy of per-voltage runs.

.. _example_prereqs:

Prerequisites
=============

Before starting, ensure the following are available:

* ``discharge-ps`` is installed — see :doc:`Installation`.
* ``DISCHARGE_HOME`` is set and points to a compiled
  `chombo-discharge <https://chombo-discharge.github.io/>`_ installation —
  see :ref:`install_prereqs`.
* A SLURM scheduler is available on the machine — see :ref:`install_prereqs`.
* Both environment variables are exported — see :ref:`install_env_vars`:

  .. code-block:: bash

     export DISCHARGE_PS_VENV=/path/to/repo/.venv
     export DISCHARGE_PS_SLURM_CONFIG=/path/to/repo/slurm.toml

.. _example_compile:

Compiling the executable
========================

.. code-block:: bash

   cd Exec/Rod
   make -j4

This produces a single binary in ``Exec/Rod/``:

.. code-block:: text

   main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex   (or main3d... for 3-D)

The binary handles **both** pipeline stages.  The active mode is selected at
runtime via ``app.mode`` in the ``.inputs`` file (``inception`` or ``plasma``).
The ``{N}`` in the filename is replaced by the dimensionality supplied via
``--dim``.

.. note::

   Both pipeline stages share the same ``chemistry.json`` as their single
   source of truth for gas properties and transport data.  In ``inception``
   mode, α and η are computed via ``ItoKMCJSON::computeAlpha/computeEta``,
   which derives them from the reaction network in ``chemistry.json`` — the
   same path used by ``plasma`` mode.  No separate ``transport_data.txt`` is
   needed.

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
the command line — ParmParse arguments appended after the input filename take
precedence over the file:

.. code-block:: bash

   mpirun -n 4 ./main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex master.inputs \
       app.mode=plasma \
       plasma.voltage=40E3

Any ``master.inputs`` key can be overridden this way.

.. note::

   The ``plasma.voltage`` key sets the constant applied voltage (in V) for the
   ItoKMC plasma simulation.  The inception sweep does not use this value.

.. _example_param_space:

Inspecting the parameter space definition
==========================================

Open ``Exec/Rod/Studies/PressureStudy/Runs.py`` to inspect or adjust the
parameter space.  The top-level structure is:

.. code-block:: python

   top_object = dict(
       databases=[inception_stepper],
       studies=[plasma_study_1]
   )

Both entries point to the flat ``Exec/Rod/`` directory:

.. code-block:: python

   rod_dir = '../../'

**Database** (``inception_stepper``) — computes inception voltages over a grid
of pressures and rod radii.  ``app.mode=inception`` is injected on the command
line by ``DischargeInceptionJobscript.py`` at runtime, so it is not part of the
parameter space here.  Pressure is written into ``chemistry.json`` so both
stages always use the same gas conditions:

.. code-block:: python

   'parameter_space': {
       "pressure": {
           "target": "chemistry.json",
           "uri": ["gas", "law", "ideal_gas", "pressure"]
       },
       "geometry_radius": {
           "target": "master.inputs",
           "uri": "Rod.radius",
       },
       'K_max': {
           "target": "master.inputs",
           "uri": "DischargeInceptionStepper.limit_max_K"
       }
   }

**Study** (``plasma_study_1``) — runs plasma simulations using the database
results.  ``app.mode`` is set to ``plasma`` via its own parameter entry so the
same binary runs the full ItoKMC simulation.  Parameters marked with
``"database": "inception_stepper"`` declare a SLURM dependency: study jobs will
not start until all database jobs have completed.  The applied voltage comes
from the inception results and is set per voltage sub-run:

.. code-block:: python

   'parameter_space': {
       "app_mode": {
           "target": "master.inputs",
           "uri": "app.mode",
           "values": ["plasma"]
       },
       "geometry_radius": {
           "database": "inception_stepper",
           "target": "master.inputs",
           "uri": "Rod.radius",
           "values": [1e-3]
       },
       "pressure": {
           "database": "inception_stepper",
           "target": "chemistry.json",
           "uri": ["gas", "law", "ideal_gas", "pressure"],
           "values": [1e5]
       },
       "K_min": {"values": [6]},
       "K_max": {
           "database": "inception_stepper",
           "values": [12.0]
       },
       ...
   }

See :ref:`arch_param_space` and :ref:`arch_db_study` for a full explanation of
parameter space syntax and database dependencies.

.. _example_run_configurator:

Running the configurator
========================

.. code-block:: bash

   cd Exec/Rod/Studies/PressureStudy
   discharge-ps run Runs.py \
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

.. _example_output_layout:

Output directory layout
========================

Just after submission (before any SLURM job has run), the layout looks like:

.. code-block:: text

   $ ls -R --file-type ~/my_rod_study
   .:
   PDIV_DB/  study0/

   ./PDIV_DB:
   array_job_id  DischargeInceptionJobscript.py  GenericArrayJob.sh
   index.json    master.inputs                   ParseReport.py
   main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex
   run_0/  structure.json  chemistry.json  electron_transport_data.dat  detachment_rate.dat
   jobscript_symlink@

   ./PDIV_DB/run_0:
   chk/  master.inputs  parameters.json  plt/  pout.*  main@
   chemistry.json  electron_transport_data.dat  detachment_rate.dat

   ./study0:
   array_job_id  chemistry.json  GenericArrayJob.sh  inception_stepper@
   index.json    master.inputs   PlasmaJobscript.py
   main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex
   run_0/  structure.json  jobscript_symlink@

   ./study0/run_0:
   chemistry.json  detachment_rate.dat  electron_transport_data.dat
   master.inputs   parameters.json      main@

Key points:

* ``jobscript_symlink@`` in ``PDIV_DB/`` points to
  ``DischargeInceptionJobscript.py``; in ``study0/`` it points to
  ``PlasmaJobscript.py``.  ``GenericArrayJob.sh`` calls
  ``python ./jobscript_symlink`` without knowing which script it is.

* ``study0/inception_stepper@`` is a symlink to ``../PDIV_DB``, giving the
  plasma study jobscript direct access to inception results.

* ``run_N/main@`` in both stages points to the executable in the parent stage
  directory.  Both stages use the same binary.

* ``master.inputs`` in ``PDIV_DB/run_N/`` has ``app.mode = inception``; in
  ``study0/run_N/`` it has ``app.mode = plasma``.  The configurator writes
  this automatically.

See :ref:`arch_output_dir` for a full description of every metadata file.

.. _example_monitor:

Monitoring jobs
===============

.. code-block:: bash

   squeue -u $USER

   # Check the submitted job IDs
   cat ~/my_rod_study/PDIV_DB/array_job_id    # database job ID
   cat ~/my_rod_study/study0/array_job_id     # study job ID (depends on above)

The study job will remain in ``Pending`` state (dependency not yet satisfied)
until the database job finishes successfully.

.. _example_inspect:

Inspecting results
==================

Use ``discharge-ps ls`` to see a table of runs with their parameter values and
completion status:

.. code-block:: bash

   discharge-ps ls ~/my_rod_study/PDIV_DB/

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

.. _example_postprocess:

Post-processing
===============

Scripts in ``PostProcess/`` summarise and plot the study results:

.. code-block:: bash

   cd ~/my_rod_study/study0
   bash /path/to/PostProcess/Summarize.sh

Or run the analysis scripts directly:

.. code-block:: bash

   python /path/to/PostProcess/Gather.py
   python /path/to/PostProcess/PlotDeltaERel.py
