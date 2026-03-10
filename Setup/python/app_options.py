import os
import sys


def write_template(args):
    app_dir = args.base_dir + "/" + args.app_name
    options_filename = app_dir + "/template.inputs"

    with open(options_filename, "w") as optf:
        # Preamble
        optf.write("# App settings\n")
        optf.write("app.mode    = inception   # 'inception' or 'plasma'\n")
        optf.write("\n")
        optf.write("# Plasma mode settings\n")
        optf.write("plasma.voltage = 1.0\n")
        optf.write("\n")

        options_files = [
            args.discharge_home + "/Source/AmrMesh/CD_AmrMesh.options",
            args.discharge_home + "/Source/Driver/CD_Driver.options",
            args.discharge_home + "/Source/ConvectionDiffusionReaction/CD_" + args.cdr_solver + ".options",
            args.discharge_home + "/Source/Electrostatics/CD_" + args.field_solver + ".options",
            args.discharge_home + "/Source/ItoDiffusion/CD_" + args.ito_solver + ".options",
            args.discharge_home + "/Source/SurfaceODESolver/CD_SurfaceODESolver.options",
            args.discharge_home + "/Source/RadiativeTransfer/CD_" + args.rte_solver + ".options",
            args.discharge_home + "/Geometries/" + args.geometry + "/CD_" + args.geometry + ".options",
            args.discharge_home + "/Physics/ItoKMC/TimeSteppers/" + args.plasma_stepper + "/CD_" + args.plasma_stepper + ".options",
            args.discharge_home + "/Physics/ItoKMC/PlasmaModels/" + args.physics + "/CD_" + args.physics + ".options",
        ]

        if args.plasma_tagger != "none":
            options_files.append(
                args.discharge_home + "/Physics/ItoKMC/CellTaggers/" + args.plasma_tagger + "/CD_" + args.plasma_tagger + ".options"
            )

        options_files.append(args.discharge_home + "/Physics/DischargeInception/CD_DischargeInceptionStepper.options")
        options_files.append(args.discharge_home + "/Physics/DischargeInception/CD_DischargeInceptionTagger.options")

        for opt in options_files:
            if os.path.exists(opt):
                with open(opt, "r") as f:
                    lines = f.readlines()
                optf.writelines(lines)
                optf.write("\n\n")
            else:
                print("Warning: could not find options file (this _may_ be normal behavior) " + opt)
