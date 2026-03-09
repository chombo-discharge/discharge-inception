.. _jobscripts_where_fit:

Where jobscripts fit
====================

``discharge-inception run`` sets up the directory structure and submits SLURM array
jobs, but the actual simulation work is done by *jobscripts* — Python scripts
that run inside each SLURM task.  ``GenericArrayJob.sh`` is the SLURM entry
point; it activates the environment and then calls
``python ./jobscript_symlink``, which resolves to the specific jobscript for
that stage.

See :ref:`arch_call_chain` for a full picture of how the pieces connect.
