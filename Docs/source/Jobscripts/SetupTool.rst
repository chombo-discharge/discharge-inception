.. _jobscripts_setup_tool:

Setting up a simulation directory
==================================

``Setup/setup.py`` scaffolds a new simulation directory under ``Exec/`` (or a
user-specified parent).  The generated directory contains ``main.cpp``,
``GNUmakefile``, ``template.inputs``, and any physics-model dependency files
(e.g. ``chemistry.json``).

The produced code follows the **dual-mode** pattern: a single binary that runs
either the ``DischargeInceptionStepper`` (inception mode) or ``ItoKMCStepper``
(plasma mode), selected at runtime via ``app.mode`` in the inputs file.

How it works
------------

``setup.py`` delegates to three helper modules:

``app_main.py``
   Writes ``main.cpp`` with parametrized ``#include`` directives, solver type
   aliases (``I``, ``C``, ``R``, ``F``), and a dual-mode ``main()`` that
   branches on ``app.mode``.

``app_options.py``
   Collects all ``.options`` files for the selected components and
   concatenates them into ``template.inputs``, prefixed by the ``app.mode``
   and ``plasma.voltage`` runtime controls.

``app_inc.py``
   Reads ``CD_{physics}.inc`` from the plasma-model directory and copies any
   listed dependency files (e.g. ``chemistry.json``) into the new application
   directory.

Arguments
---------

.. list-table::
   :widths: 20 12 18 50
   :header-rows: 1

   * - Argument
     - Type
     - Default
     - Description
   * - ``-discharge_home``
     - ``str``
     - ``$DISCHARGE_HOME``
     - Path to the chombo-discharge source tree.  Required; the script exits
       with an error if this is empty and the environment variable is not set.
   * - ``-base_dir``
     - ``str``
     - ``Exec/`` (project root)
     - Parent directory under which the new application subdirectory is
       created.
   * - ``-app_name``
     - ``str``
     - ``MyApplication``
     - Name of the new application subdirectory.
   * - ``-geometry``
     - ``str``
     - ``RegularGeometry``
     - Chombo-Discharge computational geometry class.
   * - ``-physics``
     - ``str``
     - ``ItoKMCJSON``
     - ItoKMC plasma physics model class.
   * - ``-ito_solver``
     - ``str``
     - ``ItoSolver``
     - Ito-diffusion solver type (``I`` template parameter).
   * - ``-cdr_solver``
     - ``str``
     - ``CdrCTU``
     - Convection-diffusion-reaction solver type (``C`` template parameter).
   * - ``-rte_solver``
     - ``str``
     - ``McPhoto``
     - Radiative-transfer solver type (``R`` template parameter).
   * - ``-field_solver``
     - ``str``
     - ``FieldSolverGMG``
     - Poisson/field solver type (``F`` template parameter).
   * - ``-plasma_stepper``
     - ``str``
     - ``ItoKMCBackgroundEvaluator``
     - ItoKMC time-stepper used in plasma mode.
   * - ``-plasma_tagger``
     - ``str``
     - ``ItoKMCStreamerTagger``
     - Cell-tagger used in plasma mode.  Pass ``none`` to disable tagging.

Example
-------

The following invocation reproduces the ``Exec/Rod`` configuration.  Run it
from the project root:

.. code-block:: bash
   :caption: Scaffold a Rod application

   python3 Setup/setup.py \
       -discharge_home "$DISCHARGE_HOME" \
       -base_dir Exec \
       -app_name MyRod \
       -geometry Rod \
       -physics ItoKMCJSON \
       -plasma_stepper ItoKMCBackgroundEvaluator \
       -plasma_tagger ItoKMCStreamerTagger

This creates ``Exec/MyRod/`` containing:

* ``main.cpp`` -- dual-mode driver configured for the Rod geometry.
* ``GNUmakefile`` -- ready-to-use build file.
* ``template.inputs`` -- complete options for every selected component,
  with ``app.mode`` and ``plasma.voltage`` at the top.
* ``chemistry.json`` -- dependency copied from the ``ItoKMCJSON`` model
  directory via ``CD_ItoKMCJSON.inc``.
