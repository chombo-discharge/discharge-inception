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
A study sweeping those same 5 pressures x 3 rod radii produces 15 tasks, all
chained after the database completes.
