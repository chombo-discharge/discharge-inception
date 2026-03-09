.. _arch_repo_layout:

Repository layout
=================

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Path
     - Role
   * - ``discharge_inception/``
     - Installable Python package: ``configurator``, ``config_util``, ``cli``
   * - ``Util/GenericArrayJob.sh``
     - Portable SLURM bash wrapper; the only ``#SBATCH`` script
   * - ``GenericArrayJobJobscript.py``
     - Leaf-level voltage solver runner (called via ``jobscript_symlink``)
   * - ``Exec/Rod/Studies/DischargeInceptionJobscript.py``
     - Inception database jobscript — runs the inception solver, validates range
   * - ``Exec/Rod/Studies/PlasmaJobscript.py``
     - Study orchestrator — reads inception results, creates voltage subdirs, submits child array
   * - ``slurm.toml``
     - Cluster resource configuration (MPI launcher, modules, per-stage overrides)
   * - ``Exec/Rod/``
     - Flat layout: source, headers, and data files for the Rod case
   * - ``Exec/Rod/Studies/PressureStudy/Runs.py``
     - Example parameter space definition
   * - ``PostProcess/``
     - Summary and plotting scripts
