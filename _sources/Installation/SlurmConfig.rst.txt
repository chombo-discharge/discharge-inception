.. _arch_slurm_config:

SLURM configuration
===================

Resource requests are stored in ``slurm.toml`` (path given by
``DISCHARGE_INCEPTION_SLURM_CONFIG``).  This keeps all cluster-specific settings in
one place and out of shell scripts.

.. code-block:: toml
   :caption: slurm.toml

   [slurm]
   account        = ""        # SLURM account; empty uses cluster default
   partition      = ""        # SLURM partition; empty uses cluster default
   mpi            = "mpirun"  # MPI launcher: "mpirun", "srun", or "mpiexec"
   modules        = []        # Modules to load, e.g. ["foss/2023a", "HDF5/1.14.0-gompi-2023a"]
   nodes          = 1         # Default number of nodes
   tasks_per_node = 16        # Default MPI tasks per node

   [slurm.inception]
   # Per-stage overrides for inception (database) runs
   tasks_per_node = 4
   time = "0-00:30:00"

   [slurm.plasma]
   # Per-stage overrides for plasma (voltage) runs
   tasks_per_node = 16
   time = "0-02:00:00"

``GenericArrayJob.sh`` reads the ``modules`` list from ``slurm.toml`` and calls
``module load`` for each entry.  Job scripts call ``build_sbatch_resource_args()``
to translate the ``[slurm.<stage>]`` section into ``sbatch`` command-line flags.

If ``slurm.toml`` is in the directory where you run ``inception run``, the
configurator finds it automatically and exports ``DISCHARGE_INCEPTION_SLURM_CONFIG``
for compute nodes.  If you keep the file elsewhere, set the variable explicitly
before submitting any job:

.. code-block:: bash

   export DISCHARGE_INCEPTION_SLURM_CONFIG=/absolute/path/to/slurm.toml

As an alternative to ``slurm.toml``, standard SLURM environment variables
(``SBATCH_ACCOUNT``, ``SBATCH_TIMELIMIT``, etc.) are honoured by ``sbatch``
directly and do not require a config file.
