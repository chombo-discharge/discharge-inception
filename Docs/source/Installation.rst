Installation
************

.. contents::
   :local:
   :depth: 2

.. _install_prereqs:

Prerequisites
=============

Python
------

``discharge-ps`` requires **Python ≥ 3.10**.

``numpy`` is a declared dependency and is installed automatically by ``pip``.
Certain post-processing scripts additionally require ``matplotlib`` and ``scipy``,
available via the ``[plot]`` extra:

.. code-block:: bash

   pip install -e ".[plot]"

chombo-discharge
----------------

A compiled `chombo-discharge <https://chombo-discharge.github.io/>`_ installation
is required.  The environment variable ``DISCHARGE_HOME`` must be set and point to
the root of that installation before compiling any ``Exec/`` case.

SLURM
-----

SLURM client tools (``sbatch``, ``squeue``, ``sinfo``, ``scancel``) must be
available on the machine from which you submit jobs.  On HPC clusters these are
typically pre-installed by system administrators — you need only an account and
partition access.

For local testing, both the SLURM controller (``slurmctld``) and the worker
daemon (``slurmd``) can run on the same workstation or WSL instance.  See the
`SLURM documentation <https://slurm.schedmd.com/documentation.html>`_ for
installation instructions.

.. _install_get_source:

Get the source
==============

.. code-block:: bash

   git clone https://github.com/SINTEF-Power-system-asset-management/discharge-parametric-studies.git
   cd discharge-parametric-studies

.. _install_venv:

Create and activate a virtual environment
==========================================

From the repository root:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate        # Linux / macOS
   # .venv\Scripts\activate         # Windows

.. _install_package:

Install the package
===================

Install in *editable* mode so that local edits take effect immediately without
reinstalling:

.. code-block:: bash

   pip install -e .                 # core only
   pip install -e ".[plot]"         # with matplotlib + scipy

.. _install_verify:

Verify
======

.. code-block:: bash

   which discharge-ps               # should point into .venv/bin/
   discharge-ps --help

.. _install_env_vars:

Environment variables
=====================

Two environment variables configure runtime behaviour on compute nodes.  Both
paths must be reachable from all compute nodes (typically a shared filesystem
such as ``$HOME`` or a project scratch space).

``DISCHARGE_PS_VENV``
   Absolute path to the ``.venv`` directory.  ``GenericArrayJob.sh`` reads this
   variable and activates the virtual environment on compute nodes before calling
   the jobscript.

``DISCHARGE_PS_SLURM_CONFIG``
   Absolute path to ``slurm.toml``.  Job scripts read this file to obtain MPI
   launcher settings, module lists, and per-stage resource requests.  See
   :ref:`arch_slurm_config` for the file format.

Add both exports to your ``.bashrc``, SLURM prologue, or cluster environment
module:

.. code-block:: bash

   export DISCHARGE_PS_VENV=/path/to/repo/.venv
   export DISCHARGE_PS_SLURM_CONFIG=/path/to/repo/slurm.toml

.. note::

   As an alternative to ``DISCHARGE_PS_SLURM_CONFIG``, standard SLURM
   environment variables (``SBATCH_ACCOUNT``, ``SBATCH_TIMELIMIT``, etc.) are
   respected by ``sbatch`` and can be used to supply resource requests without a
   ``slurm.toml`` file.
