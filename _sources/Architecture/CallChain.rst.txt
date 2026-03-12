.. _arch_call_chain:

The full call chain
===================

.. code-block:: text

   discharge-inception run <Runs.py>          [CLI -- discharge_inception/configurator.py]
     |  Creates run dirs, writes index.json / parameters.json per run,
     |  symlinks jobscript_symlink, writes DISCHARGE_INCEPTION_SLURM_CONFIG,
     |  then submits:
     |
     \- sbatch --array=0-N GenericArrayJob.sh        [SLURM entry-point]
          |  Loads cluster modules from slurm.toml, activates venv, then runs:
          |
          \- python ./jobscript_symlink               [jobscript dispatch]
               |
               +--- DischargeInceptionJobscript.py    [inception database runs]
               |      Navigates to run_<id>/ via index.json, runs the inception
               |      solver, validates max_voltage, optionally reruns.
               |      Output: report.txt in each run directory.
               |
               \--- PlasmaJobscript.py                [plasma study runs]
                      Navigates to run_<id>/ via structure.json prefix, looks up
                      the matching inception database run, reads its report.txt,
                      builds a voltage table, creates voltage_<i>/ subdirs,
                      then submits a SECOND sbatch array:
                      |
                      \- sbatch --array=0-M GenericArrayJob.sh   [voltage array]
                           \- python ./jobscript_symlink
                                \--- GenericArrayJobJobscript.py  [voltage runs]
                                       Navigates to voltage_<id>/ via index.json,
                                       runs the plasma solver for one voltage.

**CLI (``configurator.py``)** -- Reads the ``Runs.py`` definition, expands the
Cartesian parameter space, creates the full directory tree, copies executables
and data files, writes ``index.json`` / ``parameters.json`` / ``structure.json``
per stage, creates ``jobscript_symlink``, and submits the initial ``sbatch``
arrays.  Study arrays are submitted with ``--dependency=afterok:<db_job_id>`` to
enforce ordering.

**``GenericArrayJob.sh``** -- The only ``#SBATCH`` script in the project.  It is
completely resource-agnostic; all resource values are injected at submission time
by the Python jobscripts via ``build_sbatch_resource_args()``.  It reads
``DISCHARGE_INCEPTION_SLURM_CONFIG`` to load cluster modules and activate the virtual
environment, then calls ``python ./jobscript_symlink``.

**``DischargeInceptionJobscript.py``** -- Reads ``index.json`` to find its run
directory, runs the inception solver, parses ``report.txt`` to check the
voltage range, and reruns with an updated voltage ceiling if necessary.

**``PlasmaJobscript.py``** -- Reads ``structure.json`` to find its run directory,
locates the matching database run, extracts a filtered voltage table from the
database ``report.txt``, creates per-voltage subdirectories with injected
parameters, and submits a child SLURM array for the voltage sweep.

**``GenericArrayJobJobscript.py``** -- Leaf-level runner.  Reads ``index.json``
in the voltage subdirectory, navigates to ``voltage_<id>/``, and launches the
plasma solver via MPI for a single voltage point.
