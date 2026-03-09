.. _jobscripts_setup_helper:

Standard jobscript setup — the helper
======================================

Every jobscript begins by calling two helpers from ``discharge_inception.config_util``:

.. code-block:: python

   from discharge_inception.config_util import setup_jobscript_logging_and_dir, load_slurm_config

``setup_jobscript_logging_and_dir(prefix=None)``
   Reads ``$SLURM_ARRAY_TASK_ID``, sets up a ``logging`` instance, locates the
   run directory for this task (using ``index.json`` for leaf-level scripts or
   ``prefix`` from ``structure.json`` for study scripts), changes into it, and
   finds the ``*.inputs`` file.

   Returns a 4-tuple ``(log, task_id, run_dir, input_file)``.

   * ``log`` — configured ``logging.Logger``
   * ``task_id`` — integer SLURM array task index
   * ``run_dir`` — ``pathlib.Path`` to the current run directory
   * ``input_file`` — filename of the ``*.inputs`` file in that directory

   Pass ``prefix`` explicitly when reading it from ``structure.json`` (study
   scripts) rather than using the default ``"run_"`` prefix.

``load_slurm_config(stage=None)``
   Reads ``slurm.toml`` (via ``DISCHARGE_INCEPTION_SLURM_CONFIG``) and returns the
   merged configuration dict for the requested stage.  Keys at
   ``[slurm.<stage>]`` override top-level ``[slurm]`` defaults.
