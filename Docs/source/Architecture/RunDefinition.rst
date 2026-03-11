.. _arch_run_definition:

Run definition
==============

Each database or study entry is a dictionary with these configurable fields:

``identifier``
   Unique string name for this database/study.  Used as the symlink name in
   dependent study directories (e.g. ``study0/inception_stepper ->
   ../PDIV_DB``).

``output_directory``
   Sub-directory inside ``--output-dir`` where this stage's files are written.

``output_dir_prefix``
   Prefix for individual run directories (default: ``"run_"``).

``program``
   Executable to run.  The token ``{DIMENSIONALITY}`` is replaced at setup time
   with the value of ``--dim``.  The binary is copied/symlinked into the output
   directory hierarchy.

``job_script``
   Python script that drives the actual SLURM work for this stage.  The
   configurator creates a symlink ``jobscript_symlink ->
   <job_script>`` in the stage directory so ``GenericArrayJob.sh`` can call it
   generically.

``job_script_dependencies``
   List of files the jobscript itself needs at runtime (e.g.
   ``GenericArrayJob.sh``, ``ParseReport.py``).  These are copied into the
   stage's top-level directory.

``required_files``
   List of files copied into **every** per-run ``run_N/`` directory —
   typically ``*.inputs``, ``chemistry.json``, and other data files needed by
   the executable.

``parameter_space``
   Dictionary of named parameters.  See :ref:`arch_param_space`.

The key distinction between ``job_script_dependencies`` and ``required_files``:

* ``job_script_dependencies`` — files the jobscript at the stage level needs
  (present once in the stage directory).
* ``required_files`` — files needed by every invocation of the executable
  (copied into every ``run_N/`` directory).

A realistic example:

.. code-block:: python

   inception_stepper = {
       'identifier': 'inception_stepper',
       'output_directory': 'PDIV_DB',
       'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
       'job_script': 'DischargeInceptionJobscript.py',
       'job_script_dependencies': [
           'GenericArrayJob.sh',
           'ParseReport.py',
       ],
       'required_files': [
           'master.inputs',
           'chemistry.json',
           'electron_transport_data.dat',
           'detachment_rate.dat',
       ],
       'parameter_space': { ... }
   }

Note the use of ``{DIMENSIONALITY}`` in the ``program`` field — this token is
substituted with the value supplied via ``--dim`` on the command line.
