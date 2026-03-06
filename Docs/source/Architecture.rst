Architecture
************

.. contents::
   :local:
   :depth: 2

.. _arch_overview:

Overview
========

``discharge-parametric-studies`` is a framework for submitting, tracking, and
post-processing parametric chombo-discharge studies on SLURM clusters.  A study
is declared as a Python ``Runs.py`` file and submitted via the ``discharge-ps``
CLI.  The CLI creates run directories, injects parameters, and hands off to
SLURM.  Everything that happens *inside* a SLURM job is driven by one of the
three Python jobscripts.

The framework is built around a **two-stage pipeline** concept:

* A *database* phase (fast / lightweight, e.g. a discharge-inception sweep) runs
  first and produces intermediate data such as voltage tables.
* A *study* phase (full plasma simulation) depends on the database completing
  (via SLURM ``--dependency=afterok``) and uses the database results to configure
  detailed runs.

.. _arch_repo_layout:

Repository layout
=================

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Path
     - Role
   * - ``discharge_ps/``
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

.. _arch_db_study:

Databases and studies
=====================

The top-level ``Runs.py`` file defines a ``top_object`` dictionary containing
two lists: ``databases`` and ``studies``:

.. code-block:: python

   top_object = dict(
       databases=[inception_stepper],
       studies=[plasma_study_1]
   )

A **database** is a lightweight first step that generates intermediate data.
A **study** depends on one or more databases via SLURM ``afterok`` ordering;
the configurator submits study jobs with a dependency on the database job ID.

The parameter space of a study is the Cartesian product of its own parameters,
filtered to only the combinations that match a completed database run.

*Example:* a database sweeping 5 pressures produces 5 SLURM array tasks.
A study sweeping those same 5 pressures × 3 rod radii produces 15 tasks, all
chained after the database completes.

.. _arch_run_definition:

Run definition
==============

Each database or study entry is a dictionary with these configurable fields:

``identifier``
   Unique string name for this database/study.  Used as the symlink name in
   dependent study directories (e.g. ``study0/inception_stepper →
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
   configurator creates a symlink ``jobscript_symlink →
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

.. _arch_param_space:

Defining parameter spaces
=========================

A ``parameter_space`` is a dictionary whose keys are parameter names.  Each
value is another dictionary with these fields:

``database``
   (optional) Identifier of the database this parameter is linked to.
   Parameters that carry ``"database"`` create a SLURM ``afterok`` dependency
   between the study and the named database, and they restrict the Cartesian
   product to only the combinations that exist in the database.

``target``
   Filename (relative to the run directory) of the file to modify.  Can be a
   ``*.inputs`` ParmParse file or a ``*.json`` file.

``uri``
   Address of the value to change within the target file.  For ``*.inputs``
   files this is a dot-separated ParmParse key string.  For ``*.json`` files
   this is a list of nested dictionary keys; see :ref:`arch_json_uri` for
   special syntax.

``values``
   List of values.  Each element becomes one point in the parameter space.
   A 2nd-order list (list of lists) drives *multiple simultaneous writes* to
   parallel targets.

The Cartesian product of all ``values`` lists determines the number of runs.
Database-linked parameters restrict that product to matching combinations.

.. code-block:: python

   'parameter_space': {
       "pressure": {
           "target": "chemistry.json",
           "uri": ["gas", "law", "ideal_gas", "pressure"],
           "values": [1e5, 2e5, 3e5]        # factor 3
       },
       "geometry_radius": {
           "target": "master.inputs",
           "uri": "Rod.radius",
           "values": [1e-3, 2e-3]           # factor 2
       }
   }

The above yields 6 run directories (3 × 2).

.. _arch_json_uri:

JSON URI syntax
===============

When a parameter's ``target`` is a ``.json`` file, the ``uri`` field is a list
of keys that traverses the nested JSON hierarchy.  Two special notations allow
searching inside JSON *lists* (arrays of objects):

``+["field"="value"]``
   Find the object in the list whose ``"field"`` equals ``"value"``.  The
   object **must** exist; raises an error if not found.

``*["field"="value"]``
   Find the object in the list whose ``"field"`` equals ``"value"``, **or
   create it** if absent.

``<chem_react>``
   Hint to the parser that ``value`` is a chombo-discharge chemical reaction
   string; comparison is semantic (ignores whitespace and ordering differences).
   See `"Specifying reactions" <https://chombo-discharge.github.io/chombo-discharge/Applications/CdrPlasmaModel.html?highlight=reaction#specifying-reactions>`_
   in the chombo-discharge documentation.

**Multiple parallel targets** — when the second element of the uri list is
itself a list, the same traversal step applies to *all* entries in that inner
list simultaneously.  This is used to write two fields at the same time:

.. code-block:: python

   "uri": [
       "photoionization",
       [
           '+["reaction"=<chem_react>"Y + (O2) -> e + O2+"]',
           '*["reaction"=<chem_react>"Y + (O2) -> (null)"]'
       ],
       "efficiency"
   ],
   "values": [[1.0, 0.0]]

**Example 1** — simple object search in a list:

.. code-block:: json

   {
       "parent": {
           "list-1": [
               {"field-name-0": "value_0"},
               {"field-name-1": {"target-field": "change-me!"}},
               {"field-name-2": "value_2"}
           ]
       }
   }

.. code-block:: python

   "uri" = [
       "parent",
       "list-1",
       '+["field-name-1"]',   # finds the container object
       "field-name-1",        # selects the child object
       "target-field"         # the actual target
   ]

**Example 2** — searching by a specific value:

.. code-block:: json

   {
       "parent": {
           "list-level-1": [
               {"field-name-0": "value_0"},
               {"field-name-1": "value_1_0", "target-field": "dont-change-me!"},
               {"field-name-1": "value_1_1", "target-field": "change-me!"},
               {"field-name-2": "value_2"}
           ]
       }
   }

.. code-block:: python

   "uri" = [
       "parent",
       "list-level-1",
       '+["field-name-1"="value_1_1"]',   # finds the correct object
       "target-field"                      # the actual target
   ]

**Example 3** — traversing two list levels:

.. code-block:: json

   {
       "parent": {
           "list-level-1": [
               {"field-name-1": "value_1_1",
                "target-field": [
                    {"search-field": "some-value", "target2-field": "dont-change!"},
                    {"search-field": "search-value", "target2-field": "change-me!"}
                ]}
           ]
       }
   }

.. code-block:: python

   "uri" = [
       "parent",
       "list-level-1",
       '+["field-name-1"="value_1_1"]',
       "target-field",
       '+["search-field"="search-value"]',
       "target2-field"
   ]

.. note::

   If searching for an object in a list where the search key is itself a JSON
   object, the value part can be omitted: ``+["field-name"]``.

.. _arch_dummy_params:

Dummy parameters
================

A *dummy* parameter has no ``target`` or ``uri`` — only a ``name`` and a
``values`` list (and optionally ``database``).  It passes configuration options
to jobscripts through ``parameters.json`` without modifying any simulation
input files.

A dummy parameter with a **single value** does not expand the parameter space
(contributes a factor of 1 to run count):

.. code-block:: python

   main_study = {
       ...
       "parameter_space": {
           "K_min": {
               "values": [6.0]    # single value — does not add runs
           },
       }
   }

The value is still written to ``index.json``, ``structure.json``, and
``parameters.json``, making it available to jobscripts at runtime.

.. _arch_output_dir:

Output directory structure
==========================

After ``discharge-ps run`` completes (and while the SLURM jobs are running),
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

.. _arch_slurm_config:

SLURM configuration
===================

Resource requests are stored in ``slurm.toml`` (path given by
``DISCHARGE_PS_SLURM_CONFIG``).  This keeps all cluster-specific settings in
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

The ``DISCHARGE_PS_SLURM_CONFIG`` variable must be set (and exported) before
submitting any job so that compute nodes can find the file.

As an alternative to ``slurm.toml``, standard SLURM environment variables
(``SBATCH_ACCOUNT``, ``SBATCH_TIMELIMIT``, etc.) are honoured by ``sbatch``
directly and do not require a config file.

.. _arch_cli:

The CLI
=======

``discharge-ps run``
--------------------

Sets up directory structure and submits the initial SLURM array jobs.

.. code-block:: text

   usage: discharge-ps run [-h] [--output-dir OUTPUT_DIR] [--dim DIM]
                           [--verbose] [--logfile LOGFILE]
                           run_definition

   positional arguments:
     run_definition        Parameter space definition (.json or .py with top_object).

   options:
     -h, --help            show this help message and exit
     --output-dir OUTPUT_DIR
                           Output directory for study result files. (default: study_results)
     --dim DIM             Dimensionality of simulations. Must match chombo-discharge
                           compilation. (default: 3)
     --verbose             Increase verbosity.
     --logfile LOGFILE     Log file; rotated automatically each invocation.
                           (default: configurator.log)

``discharge-ps ls``
-------------------

Prints a table of runs, parameter values, and completion status (✓ if
``report.txt`` is present).

.. code-block:: text

   usage: discharge-ps ls [-h] study_dir [study_dir ...]

   positional arguments:
     study_dir   Study output directory containing index.json (e.g. pdiv_database/).

Example output::

   ~/my_rod_study/PDIV_DB  (2 runs)
     run  pressure  geometry_radius  K_max
     ---  --------  ---------------  -----
     run_0  100000  0.001            12  ✓
     run_1  200000  0.001            12

.. _arch_call_chain:

The full call chain
===================

.. code-block:: text

   discharge-ps run <Runs.py>          [CLI — discharge_ps/configurator.py]
     │  Creates run dirs, writes index.json / parameters.json per run,
     │  symlinks jobscript_symlink, writes DISCHARGE_PS_SLURM_CONFIG,
     │  then submits:
     │
     └─ sbatch --array=0-N GenericArrayJob.sh        [SLURM entry-point]
          │  Loads cluster modules from slurm.toml, activates venv, then runs:
          │
          └─ python ./jobscript_symlink               [jobscript dispatch]
               │
               ├─── DischargeInceptionJobscript.py    [inception database runs]
               │      Navigates to run_<id>/ via index.json, runs the inception
               │      solver, validates max_voltage, optionally reruns.
               │      Output: report.txt in each run directory.
               │
               └─── PlasmaJobscript.py                [plasma study runs]
                      Navigates to run_<id>/ via structure.json prefix, looks up
                      the matching inception database run, reads its report.txt,
                      builds a voltage table, creates voltage_<i>/ subdirs,
                      then submits a SECOND sbatch array:
                      │
                      └─ sbatch --array=0-M GenericArrayJob.sh   [voltage array]
                           └─ python ./jobscript_symlink
                                └─── GenericArrayJobJobscript.py  [voltage runs]
                                       Navigates to voltage_<id>/ via index.json,
                                       runs the plasma solver for one voltage.

**CLI (``configurator.py``)** — Reads the ``Runs.py`` definition, expands the
Cartesian parameter space, creates the full directory tree, copies executables
and data files, writes ``index.json`` / ``parameters.json`` / ``structure.json``
per stage, creates ``jobscript_symlink``, and submits the initial ``sbatch``
arrays.  Study arrays are submitted with ``--dependency=afterok:<db_job_id>`` to
enforce ordering.

**``GenericArrayJob.sh``** — The only ``#SBATCH`` script in the project.  It is
completely resource-agnostic; all resource values are injected at submission time
by the Python jobscripts via ``build_sbatch_resource_args()``.  It reads
``DISCHARGE_PS_SLURM_CONFIG`` to load cluster modules and activate the virtual
environment, then calls ``python ./jobscript_symlink``.

**``DischargeInceptionJobscript.py``** — Reads ``index.json`` to find its run
directory, runs the inception solver, parses ``report.txt`` to check the
voltage range, and reruns with an updated voltage ceiling if necessary.

**``PlasmaJobscript.py``** — Reads ``structure.json`` to find its run directory,
locates the matching database run, extracts a filtered voltage table from the
database ``report.txt``, creates per-voltage subdirectories with injected
parameters, and submits a child SLURM array for the voltage sweep.

**``GenericArrayJobJobscript.py``** — Leaf-level runner.  Reads ``index.json``
in the voltage subdirectory, navigates to ``voltage_<id>/``, and launches the
plasma solver via MPI for a single voltage point.

.. _arch_script_roles:

Script roles
============

.. list-table::
   :header-rows: 1
   :widths: 30 25 25 20

   * - Script
     - Role
     - Reads
     - Called by
   * - ``Util/GenericArrayJob.sh``
     - SLURM wrapper; loads modules, activates venv
     - ``DISCHARGE_PS_SLURM_CONFIG`` → ``slurm.toml``
     - ``sbatch --array=...``
   * - ``GenericArrayJobJobscript.py``
     - Runs plasma solver for one voltage
     - ``index.json``, ``*.inputs``, ``slurm.toml``
     - Second ``sbatch`` in ``PlasmaJobscript.py``
   * - ``DischargeInceptionJobscript.py``
     - Runs inception solver, validates voltage range
     - ``index.json``, ``*.inputs``, ``report.txt``
     - First ``sbatch`` on database study
   * - ``PlasmaJobscript.py``
     - Orchestrates voltage sweep: reads inception results, creates subdirs, submits child array
     - ``structure.json``, ``parameters.json``, ``../inception_stepper/``, ``report.txt``
     - First ``sbatch`` on plasma study
   * - ``discharge_ps/configurator.py``
     - Expands parameter space, creates dirs, submits initial arrays
     - ``Runs.py`` / ``top_object``
     - ``discharge-ps run`` CLI
   * - ``discharge_ps/config_util.py``
     - URI injection, file helpers, SLURM task ID, jobscript setup
     - Called by all jobscripts
     - All jobscripts
