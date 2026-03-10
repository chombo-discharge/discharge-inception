import os
import sys
from shutil import copyfile


def copy_dependencies(args):
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
