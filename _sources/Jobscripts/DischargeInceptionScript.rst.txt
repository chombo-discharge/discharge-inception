.. _jobscripts_discharge_inception:

Specifying the inception database options
=========================================

``Scripts/DischargeInceptionJobscript.py`` is the jobscript for the **database stage**.
Each SLURM task executes one parameter combination:

1. Runs ``DischargeInceptionStepper`` to compute the ionisation integral over a voltage
   sweep.
2. Validates the result against ``DischargeInceptionTagger.max_voltage``.
3. If the stepper exceeded the tagger limit, auto-corrects the voltage range and reruns
   until a valid result is obtained.

The script does not need to be edited directly.  All configuration is driven by the run
definition -- specifically the ``parameter_space`` and ``input_overrides`` fields -- which
the configurator writes into the ``.inputs`` file before the job runs.

Parameter space
---------------

Keys listed under ``parameter_space`` in the run definition become the free parameters
of the database sweep.  The configurator injects one value per key into the ``.inputs``
file for each SLURM task, so the stepper sees the correct combination.

See :ref:`arch_param_space` and :ref:`arch_run_definition` for the full syntax.

Input overrides
---------------

Keys listed under ``input_overrides`` are fixed values injected into every ``.inputs``
file regardless of the task index.  Use this to set stepper or tagger settings that are
constant across the sweep (e.g. ``DischargeInceptionStepper.max_steps``).

See :ref:`arch_run_definition` for details.

job_script_options
------------------

This script has no user-configurable runtime knobs beyond what is already expressed in
the ``.inputs`` file.  The ``job_script_options`` field of the run definition is not
read by ``DischargeInceptionJobscript.py`` and may be omitted.
