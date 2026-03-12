Discharge Inception
*******************

Documentation for a framework of Python and SLURM scripts for running chombo-discharge studies over wide parameter spaces.
This program provides an interface for coupling two different modules within chombo-discharge:

* DischargeInceptionStepper, which can compute values of the ionization integral for a provided geometry and gas.
* ItoKMC, which can run plasma simulations.

The interface consists of parametric sweeps where the partial discharge inception voltage (PDIV) is first computed using DischargeInceptionStepper by adjusting one or more free parameters.
This first step builds a database of the PDIV as a function of the various free parameters. 
In a second step, the plasma solver is run for each unique set of the free parameters, and for a specified range of voltages.
The intention of this composite procedure is that users will quickly be able to:

1. Easily generate PDIV-vs-parameter databases.
2. Run multiple plasma simulations corresponding to these databases to provide even more accurate information on the discharge processes themselves.

The second step provides a self-consistent coupling to the electric field, accounts for space-charge screening, formative time lag, and so on.
This step is automatic run by submitting jobs via a SLURM queue system, so the user does not have to be directly involved in the logistics of setting up these simulations.

.. raw:: html

   <style>
   section#installation,
   section#architecture,
   section#jobscripts-guide,
   section#post-processing,
   section#example-rod-case {
       display:none;
   }
   </style>

.. only:: latex

   .. toctree::
      :caption: Contents

Installation
************

.. toctree::
   :maxdepth: 2
   :caption: Installation
   :hidden:

   Installation/Prerequisites
   Installation/GetSource
   Installation/InstallationInstructions
   Installation/SlurmConfig
   Installation/CLI   

Architecture
************

.. toctree::
   :maxdepth: 2
   :caption: Architecture
   :hidden:

   Architecture/Overview
   Architecture/RepoLayout
   Architecture/DbStudy
   Architecture/RunDefinition
   Architecture/ParamSpace
   Architecture/JsonUri
   Architecture/DummyParams
   Architecture/OutputDir
   Architecture/CallChain
   Architecture/ScriptRoles

Jobscripts guide
*****************

.. toctree::
   :maxdepth: 2
   :caption: Jobscripts guide
   :hidden:

   Jobscripts/SetupTool
   Jobscripts/WhereFit
   Jobscripts/GenericArrayJob
   Jobscripts/DischargeInceptionScript
   Jobscripts/PlasmaScript

Post-processing
***************

.. toctree::
   :maxdepth: 2
   :caption: Post-processing
   :hidden:

   PostProcess/Quickstart
   PostProcess/ExtractInceptionVoltages
   PostProcess/GatherPlasmaEventLogs
   PostProcess/AnalyzeTimeSeries
   PostProcess/PlotDeltaERel


Example -- Rod Case
*******************

.. toctree::
   :maxdepth: 2
   :caption: Example -- Rod Case
   :hidden:

   Example/Prerequisites
   Example/Compile
   Example/SmokeTest
   Example/ParamSpace
   Example/RunConfigurator
   Example/OutputLayout
   Example/Monitor
   Example/Inspect
