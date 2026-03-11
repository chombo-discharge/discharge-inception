.. _install_prereqs:

Prerequisites
=============

Python
------

``discharge-inception`` requires **Python >= 3.10**.  The minimum version is set
by the use of structural pattern matching (``match``/``case``) in the parameter
handling code and by ``tomllib``, which entered the standard library in 3.11 but
is available as a backport (``tomli``) for 3.10.  Using the newest Python 3.x
release available on your cluster is recommended.

``numpy`` is a declared dependency and is installed automatically by ``pip``.
Certain post-processing scripts additionally require ``matplotlib`` and ``scipy``,
available via the ``[plot]`` extra:

.. code-block:: bash

   pip install -e ".[plot]"

chombo-discharge
----------------

A compiled `chombo-discharge <https://chombo-discharge.github.io/>`_ installation
is required to build and run the simulation executables inside ``Exec/``.  The
framework itself (the Python package and SLURM scripts) does not link against
chombo-discharge, but every ``Exec/`` case depends on it at compile time.

The environment variable ``DISCHARGE_HOME`` must be set and exported before
compiling any ``Exec/`` case.  It should point to the root of the
chombo-discharge source tree — the same directory that contains
``GNUmakefile.defs``.  Setting this in your ``.bashrc`` (or the cluster
environment module) is the most convenient approach.

SLURM
-----

SLURM client tools (``sbatch``, ``squeue``, ``sinfo``, ``scancel``) must be
available on the machine from which you submit jobs.  On HPC clusters these are
typically pre-installed by system administrators — you need only an account and
partition access.

The framework submits jobs programmatically: the ``discharge-inception run``
command calls ``sbatch`` directly from Python, so the SLURM client must be on
the ``PATH`` of the machine where you run the configurator.  Compute nodes
themselves do not need to call ``sbatch`` unless you use the two-stage pipeline,
in which case ``PlasmaJobscript.py`` submits a child array from inside the first
SLURM job.

For local testing, both the SLURM controller (``slurmctld``) and the worker
daemon (``slurmd``) can run on the same workstation or WSL instance.  See the
`SLURM documentation <https://slurm.schedmd.com/documentation.html>`_ for
installation instructions.
