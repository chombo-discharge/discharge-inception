Quickstart — Rod Case
=====================

This guide walks through the complete workflow for the ``Exec/Rod`` parametric study — from compilation through post-processing.
The Rod case demonstrates the two-level database → study pipeline: a discharge-inception database is computed first, and its results feed a full plasma simulation study.

Prerequisites
-------------

Before starting, ensure the following are available:

* ``discharge-ps`` must be installed. See :doc:`../Prerequisites/Installation` for instructions.
* ``DISCHARGE_HOME`` must be set and point to a compiled `chombo-discharge <https://chombo-discharge.github.io/>`_ installation.
* A SLURM scheduler must be available. See :doc:`../Prerequisites/Example` for a local install example.

Compile
-------

.. code-block:: bash

    cd Exec/Rod
    make -j4

This builds a single executable directly in ``Exec/Rod/``:

* ``main{N}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex`` — handles **both** the inception-voltage database step and the full plasma simulation step.
  The active mode is selected at runtime via the ``App.mode`` parameter in the ``.inputs`` file (``inception`` or ``plasma``).

The ``{N}`` in the filename is replaced at runtime by the dimensionality specified with ``--dim``.

.. note::

    Both pipeline stages share the same ``chemistry.json`` as their single source of truth for gas properties and transport data.
    In ``inception`` mode, alpha and eta are computed via ``ItoKMCJSON::computeAlpha/computeEta``, which derives them from the reaction network in ``chemistry.json`` — the same path used by the ``plasma`` mode.
    No separate ``transport_data.txt`` is needed.

Configure the parameter space
------------------------------

Open ``Exec/Rod/Studies/PressureStudy/Runs.py`` to inspect or adjust the parameter space.
The top-level structure is:

.. code-block:: python

    top_object = dict(
            databases=[inception_stepper],
            studies=[plasma_study_1]
            )

Both studies point to the same binary in the flat ``Exec/Rod/`` directory:

.. code-block:: python

    rod_dir = '../../'

    inception_stepper = {
        'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
        ...
    }

    plasma_study_1 = {
        'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
        ...
    }

**Database** (``inception_stepper``) — computes inception voltages over a grid of pressures and rod radii.
``App_mode`` is set to ``inception`` so the binary runs the inception-voltage sweep.
Pressure is written into ``chemistry.json`` so both stages always use the same gas conditions:

.. code-block:: python

    'parameter_space': {
        "App_mode": {
            "target": "master.inputs",
            "uri": "App.mode",
            "values": ["inception"]
            },
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

**Study** (``plasma_study_1``) — runs plasma simulations using the database results.
``App_mode`` is set to ``plasma`` so the same binary runs the full ItoKMC simulation:

.. code-block:: python

    'parameter_space': {
        "App_mode": {
            "target": "master.inputs",
            "uri": "App.mode",
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
        "K_min": { "values": [6] },
        "K_max": {
            "database": "inception_stepper",
            "values": [12.0]
            },
        "photoionization": {
            "target": "chemistry.json",
            "uri": [...],
            "values": [[1.0, 0.0]]
            },
        }

.. note::

    Because both studies write their geometry parameters (e.g. ``Rod.radius``) into the **same** ``master.inputs`` template, rod geometry is defined in one place and cannot fall out of sync between the two stages.

Parameters marked with ``"database": "inception_stepper"`` declare a dependency: the study jobs will not start until all database jobs have finished.
See :doc:`RunDefinition` for full parameter space syntax.

Run the Configurator
---------------------

.. code-block:: bash

    cd Exec/Rod/Studies/PressureStudy
    discharge-ps Runs.py \
        --output-dir ~/my_rod_study \
        --dim 2 \
        --verbose

The Configurator:

1. Creates the output directory tree.
2. Copies executables, input files, and job scripts into place.
3. Submits a SLURM array job for the database (``PDIV_DB/``).
4. Submits a second SLURM array job for the study (``study0/``), chained to depend on the database job completing first.

The resulting directory layout looks like:

.. code-block:: bash

    $ ls -R --file-type ~/my_rod_study
    .:
    PDIV_DB/  study0/

    ./PDIV_DB:
    array_job_id  DischargeInceptionJobscript.py  GenericArrayJob.sh
    index.json    master.inputs                   ParseReport.py
    main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex
    run_0/  structure.json  chemistry.json  electron_transport_data.dat  detachment_rate.dat

    ./PDIV_DB/run_0:
    chk/  master.inputs  parameters.json  plt/  pout.*  main@
    chemistry.json  electron_transport_data.dat  detachment_rate.dat

    ./study0:
    array_job_id  chemistry.json  GenericArrayJob.sh  inception_stepper@
    index.json    master.inputs   PlasmaJobscript.py
    main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex
    run_0/  structure.json

    ./study0/run_0:
    chemistry.json  detachment_rate.dat  electron_transport_data.dat
    master.inputs   parameters.json      main@

In both stages the ``main`` symlink points to the same executable from ``Exec/Rod/``.
The ``master.inputs`` files differ only in their ``App.mode`` line, which the Configurator writes
automatically: ``App.mode = inception`` in ``PDIV_DB/`` run directories and ``App.mode = plasma``
in ``study0/`` run directories.

.. note::

    ``study0/inception_stepper`` is a symlink pointing to ``../PDIV_DB``, giving study job scripts direct access to the database results.

.. note::

    Geometry parameters such as ``Rod.radius`` appear only in the shared ``master.inputs`` template.
    Both stages read them from the same copy — there is no manual sync required.

Monitor jobs
-------------

.. code-block:: bash

    squeue -u $USER

    # Check the submitted job IDs
    cat ~/my_rod_study/PDIV_DB/array_job_id     # database job ID
    cat ~/my_rod_study/study0/array_job_id    # study job ID (depends on above)

Inspect results
----------------

After both jobs complete:

.. code-block:: bash

    # Database results — inception voltage reports
    ls ~/my_rod_study/PDIV_DB/run_*/report.txt

    # Study results — plasma simulation output
    ls ~/my_rod_study/study0/run_*/pout.*
    ls ~/my_rod_study/study0/run_*/plt/

Post-process
-------------

Scripts in ``PostProcess/`` summarise and plot the study results:

.. code-block:: bash

    cd ~/my_rod_study/study0
    bash /path/to/PostProcess/Summarize.sh

Or run the analysis scripts directly:

.. code-block:: bash

    python /path/to/PostProcess/Gather.py
    python /path/to/PostProcess/PlotDeltaERel.py
