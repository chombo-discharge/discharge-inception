.. _install_env_vars:

Environment variables
=====================

Two environment variables configure runtime behaviour on compute nodes.  Both
paths must be reachable from all compute nodes (typically a shared filesystem
such as ``$HOME`` or a project scratch space).  Because ``GenericArrayJob.sh``
runs on whatever node SLURM allocates, it cannot rely on paths that were valid
only on the login node — using absolute paths on a shared filesystem avoids
node-local ambiguity entirely.

``DISCHARGE_INCEPTION_VENV``
   Absolute path to the ``.venv`` directory created during installation.
   ``GenericArrayJob.sh`` sources ``$DISCHARGE_INCEPTION_VENV/bin/activate`` on
   each compute node before invoking the Python jobscript, ensuring the correct
   interpreter and installed packages are used.  If this variable is unset or
   empty, the script falls back to whatever ``python`` is on the default
   ``PATH``, which may not have ``discharge_inception`` installed.

``DISCHARGE_INCEPTION_SLURM_CONFIG``
   Absolute path to the ``slurm.toml`` configuration file.  The configurator
   (``discharge-inception run``) reads this file at submission time to build
   ``sbatch`` resource arguments, and ``GenericArrayJob.sh`` reads it on
   compute nodes to load the required cluster modules.  Job scripts also call
   ``load_slurm_config()`` at runtime to retrieve the MPI launcher name and
   per-stage resource limits.  See :ref:`arch_slurm_config` for the full file
   format and all supported keys.

Add both exports to your ``.bashrc``, SLURM prologue, or cluster environment
module so they are present on both login and compute nodes:

.. code-block:: bash

   export DISCHARGE_INCEPTION_VENV=/path/to/repo/.venv
   export DISCHARGE_INCEPTION_SLURM_CONFIG=/path/to/repo/slurm.toml

.. note::

   As an alternative to ``DISCHARGE_INCEPTION_SLURM_CONFIG``, standard SLURM
   environment variables (``SBATCH_ACCOUNT``, ``SBATCH_TIMELIMIT``, etc.) are
   respected by ``sbatch`` and can be used to supply resource requests without a
   ``slurm.toml`` file.
