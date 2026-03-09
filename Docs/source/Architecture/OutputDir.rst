.. _arch_output_dir:

Output directory structure
==========================

After ``discharge-inception run`` completes (and while the SLURM jobs are running),
the output tree looks like:

.. code-block:: text

   $ ls -R --file-type ~/my_rod_study
   .:
   PDIV_DB/  study0/

   ./PDIV_DB:
   array_job_id  DischargeInceptionJobscript.py  GenericArrayJob.sh
   index.json    master.inputs                   ParseReport.py
   main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex
   run_0/  structure.json  chemistry.json  electron_transport_data.dat  detachment_rate.dat
   jobscript_symlink@

   ./PDIV_DB/run_0:
   chk/  master.inputs  parameters.json  plt/  pout.*  main@
   chemistry.json  electron_transport_data.dat  detachment_rate.dat

   ./study0:
   array_job_id  chemistry.json  GenericArrayJob.sh  inception_stepper@
   index.json    master.inputs   PlasmaJobscript.py
   main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex
   run_0/  structure.json  jobscript_symlink@

   ./study0/run_0:
   chemistry.json  detachment_rate.dat  electron_transport_data.dat
   master.inputs   parameters.json      main@

Key files and symlinks:

``array_job_id``
   Contains the SLURM array job ID for this stage as a single integer.

``index.json``
   Maps integer run indices to parameter tuples.  Format::

     {"prefix": "run_", "keys": ["pressure", "geometry_radius"], "index": {"0": [1e5, 1e-3], ...}}

``structure.json``
   Parsed export of the run definition for this stage.  Jobscripts read it to
   get metadata such as the run prefix and ``required_files`` list.

``run_N/parameters.json``
   Named parameter dict for run N.  Convenient for inspection and for
   jobscripts that need to locate a matching database run.

``jobscript_symlink@``
   Points to the jobscript for this stage
   (e.g. ``DischargeInceptionJobscript.py``).  ``GenericArrayJob.sh`` calls
   ``python ./jobscript_symlink`` without knowing which script it is.

``run_N/main@``
   Symlink pointing to the executable in the parent stage directory.

``study0/inception_stepper@``
   Symlink pointing to ``../PDIV_DB`` — gives the plasma study jobscript
   direct access to database results.
