.. _jobscripts_generic_array:

GenericArrayJob.sh — the SLURM wrapper
=======================================

``Util/GenericArrayJob.sh`` is the **only** ``#SBATCH`` script in the project.
It contains no hardcoded resource requests (nodes, tasks, time, account).
Instead, resource values are injected at submission time by the Python
jobscripts via ``build_sbatch_resource_args()``, which reads ``slurm.toml``
(see :ref:`arch_slurm_config`).

The only ``#SBATCH`` directives it does contain redirect stdout/stderr to
per-array-task log files:

.. code-block:: bash
   :caption: Util/GenericArrayJob.sh

   #!/bin/bash
   # Generic SLURM array job launcher for discharge-inception.
   #
   # Resource requests (account, partition, ntasks, time) are intentionally
   # absent here so the script is portable across clusters. Supply them via:
   #   - sbatch CLI arguments:  sbatch --account=X --ntasks=N --time=HH:MM:SS ...
   #   - SLURM environment variables: export SBATCH_ACCOUNT=X before submitting
   #   - The Python job scripts read slurm.toml and pass these automatically
   #     when they invoke sbatch themselves (e.g. for the voltage sub-array).

   #SBATCH --output=R-%x.%A-%a.out
   #SBATCH --error=R-%x.%A-%a.err

   set -o errexit
   set -o nounset

   # Load cluster modules listed in slurm.toml (requires DISCHARGE_INCEPTION_SLURM_CONFIG
   # to be set and exported before submitting the job). Uses the system python3
   # (before venv activation) to parse the TOML. The block is skipped entirely on
   # systems without the 'module' command or without the config file.
   if command -v module > /dev/null 2>&1 \
           && [ -n "${DISCHARGE_INCEPTION_SLURM_CONFIG:-}" ] \
           && [ -f "${DISCHARGE_INCEPTION_SLURM_CONFIG}" ]; then
       while IFS= read -r mod; do
           [ -n "$mod" ] && module load "$mod"
       done < <(python3 -c "
   import sys, tomllib
   with open(sys.argv[1], 'rb') as f:
       c = tomllib.load(f)
   for m in c.get('slurm', {}).get('modules', []):
       print(m)
   " "${DISCHARGE_INCEPTION_SLURM_CONFIG}")
   fi

   if [ -n "${DISCHARGE_INCEPTION_VENV:-}" ]; then
       source "$DISCHARGE_INCEPTION_VENV/bin/activate"
   fi

   python ./jobscript_symlink
   exit $?

``GenericArrayJob.sh`` must be listed as a ``job_script_dependency`` in every
run definition entry so the configurator copies it into the stage directory
(see :ref:`arch_run_definition`).
