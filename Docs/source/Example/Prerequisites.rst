.. _example_prereqs:

Prerequisites
=============

This chapter walks through the complete workflow for the ``Exec/Rod``
parametric study, from compilation through post-processing.

The Rod case demonstrates the **two-level database -> study pipeline**:

1. A discharge-inception database sweeps over pressures and rod radii to
   compute inception voltages.
2. A full plasma simulation study uses those inception voltages as its input,
   creating a sub-hierarchy of per-voltage runs.

Before starting, ensure the following are available:

* ``discharge-inception`` is installed — see :doc:`/Installation/InstallationInstructions`.
* ``DISCHARGE_HOME`` is set and points to a compiled
  `chombo-discharge <https://chombo-discharge.github.io/>`_ installation —
  see :ref:`install_prereqs`.
* A SLURM scheduler is available on the machine — see :ref:`install_prereqs`.
* Both environment variables are exported — see :ref:`install_env_vars`:

  .. code-block:: bash

     export DISCHARGE_INCEPTION_VENV=/path/to/repo/.venv
     export DISCHARGE_INCEPTION_SLURM_CONFIG=/path/to/repo/slurm.toml
