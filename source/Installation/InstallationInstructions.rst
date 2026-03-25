.. _installation_instructs:

Installation instructions
=========================

.. _install_venv:

Create and activate a virtual environment
------------------------------------------

A virtual environment isolates the project's Python dependencies from the
system Python and from other projects on the same machine.  This is especially
important on HPC clusters, where the system Python may be managed by
administrators and ``pip install`` into it is either forbidden or inadvisable.

The virtual environment directory is conventionally named ``.venv`` and placed
at the repository root.  Because compute nodes need to activate the same
environment, the ``.venv`` directory must live on a shared filesystem that is
accessible from all nodes -- typically your home directory or a project scratch
space, both of which are usually network-mounted on HPC clusters.  Do **not**
place ``.venv`` on a node-local scratch directory (e.g. ``/tmp``), as it will
not be visible to other nodes.

From the repository root:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate        # Linux / macOS
   # .venv\Scripts\activate         # Windows

.. _install_package:

Install the package
-------------------

Install in *editable* mode so that local edits to the ``discharge_inception/``
source directory take effect immediately without reinstalling.  Editable mode
also means that the ``inception`` command-line entry point is
registered in the virtual environment and will always run the current state of
the checked-out source.

``matplotlib`` and ``scipy`` are included as standard dependencies and are
installed automatically alongside the core package:

.. code-block:: bash

   pip install -e .

.. _install_verify:

Verify
------

After installing the package, confirm that the ``inception`` entry
point is registered in the active virtual environment and that the package
imports correctly.  The ``which`` command should resolve to the ``.venv/bin/``
directory, confirming that the system Python (or another environment) is not
being used by mistake.  Running ``--help`` exercises the full import chain --
including ``configurator`` and ``config_util`` -- so any missing dependency or
broken import will surface here rather than at job-submission time.

.. code-block:: bash

   which inception               # should point into .venv/bin/
   inception --help

.. _install_env_vars:

Environment variables
---------------------

Two environment variables configure runtime behaviour on compute nodes.  Both
paths must be reachable from all compute nodes (typically a shared filesystem
such as ``$HOME`` or a project scratch space).  Because ``GenericArrayJob.sh``
runs on whatever node SLURM allocates, it cannot rely on paths that were valid
only on the login node -- using absolute paths on a shared filesystem avoids
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
   (``inception run``) reads this file at submission time to build
   ``sbatch`` resource arguments, and ``GenericArrayJob.sh`` reads it on
   compute nodes to load the required cluster modules.  Job scripts also call
   ``load_slurm_config()`` at runtime to retrieve the MPI launcher name and
   per-stage resource limits.  See :ref:`arch_slurm_config` for the full file
   format and all supported keys.

   This variable is **optional** when ``slurm.toml`` is in the directory from
   which you run ``inception run`` — the configurator detects it automatically
   and propagates the absolute path to compute nodes.  Set the variable
   explicitly only when the file lives elsewhere.

Add the venv export to your ``.bashrc``, SLURM prologue, or cluster environment
module so it is present on both login and compute nodes.  The slurm config
export is only needed when ``slurm.toml`` is not in your working directory:

.. code-block:: bash

   export DISCHARGE_INCEPTION_VENV=/path/to/repo/.venv
   # Only needed if slurm.toml is not in the directory where you run inception run:
   export DISCHARGE_INCEPTION_SLURM_CONFIG=/path/to/repo/slurm.toml

.. note::

   As an alternative to ``DISCHARGE_INCEPTION_SLURM_CONFIG``, standard SLURM
   environment variables (``SBATCH_ACCOUNT``, ``SBATCH_TIMELIMIT``, etc.) are
   respected by ``sbatch`` and can be used to supply resource requests without a
   ``slurm.toml`` file.
