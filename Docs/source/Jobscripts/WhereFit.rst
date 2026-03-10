.. _jobscripts_where_fit:

Where jobscripts fit
====================

Rather than requiring users to author their own jobscripts, the framework ships two
ready-made scripts in ``Scripts/``:

``Scripts/DischargeInceptionJobscript.py``
   Runs the **database stage** (inception stepper).  Each SLURM task processes one
   parameter combination: it invokes ``DischargeInceptionStepper``, checks the result
   against ``DischargeInceptionTagger.max_voltage``, and auto-corrects and reruns if
   the stepper exceeded the tagger limit.  See :ref:`jobscripts_discharge_inception`.

``Scripts/PlasmaJobscript.py``
   Runs the **plasma stage** (ItoKMC).  It reads the database results, selects
   voltages from the K-range, creates per-voltage subdirectories, and submits the
   voltage SLURM array.  See :ref:`jobscripts_plasma`.

Both scripts are invoked through ``GenericArrayJob.sh``, which is the SLURM entry
point: it activates the environment and calls ``python ./jobscript_symlink``, which
resolves to the appropriate script for the stage.  See :ref:`jobscripts_generic_array`
for details on the SLURM wrapper itself, and :ref:`arch_call_chain` for a full picture
of how all the pieces connect.
