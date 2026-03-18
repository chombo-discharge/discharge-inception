#!/usr/bin/env python3
"""Scaffold a new chombo-discharge simulation directory for the dual-mode inception+plasma workflow.

Usage::

    python3 Setup/setup.py \\
        -discharge_home "$DISCHARGE_HOME" \\
        -base_dir Exec \\
        -app_name MyApp \\
        -geometry Rod \\
        -physics ItoKMCJSON \\
        -plasma_stepper ItoKMCBackgroundEvaluator \\
        -plasma_tagger ItoKMCStreamerTagger

The script delegates to three helper modules:

* ``app_main``    — generates ``main.cpp`` with dual-mode ``main()``.
* ``app_options`` — collects ``.options`` files and writes ``template.inputs``.
* ``app_inc``     — reads ``CD_{physics}.inc`` and copies dependency files (e.g. ``chemistry.json``).

A ``GNUmakefile`` is also copied from ``Setup/python/`` into the new directory.
"""
import argparse
import os
import sys
import shutil

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "python"))
import app_main
import app_options
import app_inc

# Determine the inception project root (one level up from this script's directory)
_inception_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

parser = argparse.ArgumentParser()
parser.add_argument("-discharge_home",  type=str, default=os.environ.get("DISCHARGE_HOME", ""),       help="chombo-discharge source directory (default: $DISCHARGE_HOME)")
parser.add_argument("-base_dir",        type=str, default=os.path.join(_inception_root, "Exec"),      help="Parent directory for the new app (default: %(default)s)")
parser.add_argument("-app_name",        type=str, default="MyApplication",                             help="Subdirectory name for the new app (default: %(default)s)")
parser.add_argument("-geometry",        type=str, default="RegularGeometry",                           help="Computational geometry class (default: %(default)s)")
parser.add_argument("-physics",         type=str, default="ItoKMCJSON",                                help="ItoKMC plasma physics model (default: %(default)s)")
parser.add_argument("-ito_solver",      type=str, default="ItoSolver",                                 help="Ito solver type (default: %(default)s)")
parser.add_argument("-cdr_solver",      type=str, default="CdrCTU",                                    help="CDR solver type (default: %(default)s)")
parser.add_argument("-rte_solver",      type=str, default="McPhoto",                                   help="RTE solver type (default: %(default)s)")
parser.add_argument("-field_solver",    type=str, default="FieldSolverGMG",                            help="Poisson solver type (default: %(default)s)")
parser.add_argument("-plasma_stepper",  type=str, default="ItoKMCBackgroundEvaluator",                 help="ItoKMC stepper for plasma mode (default: %(default)s)")
parser.add_argument("-plasma_tagger",   type=str, default="ItoKMCStreamerTagger",                      help="Cell tagger for plasma mode, or 'none' (default: %(default)s)")

args = parser.parse_args()
args.base_dir = os.path.abspath(args.base_dir)

if not args.discharge_home:
    print("Error: DISCHARGE_HOME is not set.")
    print("       Please set DISCHARGE_HOME, for example:")
    print("       export DISCHARGE_HOME=<directory>")
    sys.exit(1)

print("DISCHARGE_HOME is " + args.discharge_home)
print("Setting up application in " + args.base_dir + "/" + args.app_name)

app_main.write_template(args)
app_options.write_template(args)
app_inc.copy_dependencies(args)

app_dir = os.path.join(args.base_dir, args.app_name)
makefile_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python", "GNUmakefile")
shutil.copy2(makefile_src, os.path.join(app_dir, "GNUmakefile"))

print("Problem setup successful")
