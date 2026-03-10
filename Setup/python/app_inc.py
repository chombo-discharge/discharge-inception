"""Copy physics-model dependency files listed in ``CD_{physics}.inc`` into the new application directory."""

import os
import sys
from shutil import copyfile


def copy_dependencies(args):
    """Read ``CD_{physics}.inc`` and copy each listed dependency into the application directory.

    The ``.inc`` file lives next to the physics model headers in
    ``$DISCHARGE_HOME/Physics/ItoKMC/PlasmaModels/{physics}/``.  Each
    non-empty line is treated as a filename relative to that directory
    (e.g. ``chemistry.json``) and is copied into ``<base_dir>/<app_name>/``.
    If the ``.inc`` file does not exist the function returns silently.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.  Consumed
            attributes:

            * ``discharge_home`` — path to the chombo-discharge source tree.
            * ``base_dir`` — parent directory for the new application.
            * ``app_name`` — subdirectory name of the new application.
            * ``physics`` — ItoKMC plasma physics model class name; used to
              locate ``CD_{physics}.inc``.

    Side effects:
        Copies one or more files into ``<base_dir>/<app_name>/``.  Prints a
        warning to stdout for each dependency listed in the ``.inc`` file that
        cannot be found on disk.
    """
    app_dir = args.base_dir + "/" + args.app_name
    kin_home = args.discharge_home + "/Physics/ItoKMC/PlasmaModels/" + args.physics
    inc_file = kin_home + "/CD_" + args.physics + ".inc"

    if os.path.exists(inc_file):
        with open(inc_file, "r") as f:
            for line in f:
                dep = line.strip()
                if dep:
                    src = kin_home + "/" + dep
                    dst = app_dir + "/" + dep
                    if os.path.exists(src):
                        copyfile(src, dst)
                    else:
                        print("Warning: could not find dependency " + src)
