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
  The active mode is selected at runtime via the ``app.mode`` parameter in the ``.inputs`` file (``inception`` or ``plasma``).

The ``{N}`` in the filename is replaced at runtime by the dimensionality specified with ``--dim``.

.. note::

    Both pipeline stages share the same ``chemistry.json`` as their single source of truth for gas properties and transport data.
    In ``inception`` mode, alpha and eta are computed via ``ItoKMCJSON::computeAlpha/computeEta``, which derives them from the reaction network in ``chemistry.json`` — the same path used by the ``plasma`` mode.
    No separate ``transport_data.txt`` is needed.

Run an example directly
------------------------

The default ``master.inputs`` sets ``app.mode = inception``, so the simplest test run is:

.. code-block:: bash

    cd Exec/Rod
    mpirun -n 4 ./main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex master.inputs

This runs a stationary inception-voltage sweep on the default rod geometry at 1 atm.
Results are written to ``report.txt`` and plot files to ``plt/``.

To run the plasma simulation instead, override the mode (and optionally the voltage) on the
command line — Chombo ParmParse arguments passed after the input file take precedence over
the file:

.. code-block:: bash

    mpirun -n 4 ./main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex master.inputs \
        app.mode=plasma \
        plasma.voltage=40E3

Any ``master.inputs`` key can be overridden this way.

.. note::

    The ``plasma.voltage`` key sets the constant applied voltage (in V) for the ItoKMC
    plasma simulation.  The inception sweep does not use this value.

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
``app.mode=inception`` is injected on the command line by ``DischargeInceptionJobscript.py`` at runtime,
so it is not part of the parameter space.
Pressure is written into ``chemistry.json`` so both stages always use the same gas conditions:

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

**Study** (``plasma_study_1``) — runs plasma simulations using the database results.
``app.mode`` is set to ``plasma`` by its own parameter space entry so the same binary runs the full ItoKMC simulation.
The applied voltage comes from the inception database results and is set per voltage sub-run:

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
The ``master.inputs`` files differ only in their ``app.mode`` line, which the Configurator writes
automatically: ``app.mode = inception`` in ``PDIV_DB/`` run directories and ``app.mode = plasma``
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

Identify the settings for each run
------------------------------------

Each run directory has two files that record its exact parameter values.

**``index.json``** at the top of each stage directory maps integer run index to parameter tuple:

.. code-block:: json

    {
        "prefix": "run_",
        "keys": ["pressure", "geometry_radius", "K_max"],
        "index": {
            "0": [100000.0, 0.001, 12.0],
            "1": [200000.0, 0.001, 12.0]
        }
    }

The key order in ``"keys"`` matches the tuple order in ``"index"``, so run ``run_0`` used
``pressure = 1e5 Pa``, ``Rod.radius = 1e-3 m``, ``K_max = 12``.

**``parameters.json``** inside every run directory contains the same information as a named dict,
which is more convenient for direct inspection:

.. code-block:: bash

    cat ~/my_rod_study/PDIV_DB/run_0/parameters.json

.. code-block:: json

    {
        "pressure": 100000.0,
        "geometry_radius": 0.001,
        "K_max": 12.0
    }

So ``PDIV_DB/run_0/report.txt`` was produced with those settings.
For a quick overview of all runs:

.. code-block:: bash

    # Print settings for every database run
    for d in ~/my_rod_study/PDIV_DB/run_*/; do
        echo "$d"; cat "$d/parameters.json"; echo
    done

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
