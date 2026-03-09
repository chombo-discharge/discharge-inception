.. _arch_overview:

Overview
========

``discharge-inception`` is a framework for submitting, tracking, and
post-processing parametric chombo-discharge studies on SLURM clusters.  A study
is declared as a Python ``Runs.py`` file and submitted via the ``discharge-inception``
CLI.  The CLI creates run directories, injects parameters, and hands off to
SLURM.  Everything that happens *inside* a SLURM job is driven by one of the
three Python jobscripts.

The framework is built around a **two-stage pipeline** concept:

* A *database* phase (fast / lightweight, e.g. a discharge-inception sweep) runs
  first and produces intermediate data such as voltage tables.
* A *study* phase (full plasma simulation) depends on the database completing
  (via SLURM ``--dependency=afterok``) and uses the database results to configure
  detailed runs.
