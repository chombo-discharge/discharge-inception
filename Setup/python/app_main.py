"""Generate ``main.cpp`` for a dual-mode DischargeInception + ItoKMC application."""

import os
import sys


def write_template(args):
    """Write a parametrized ``main.cpp`` into the new application directory.

    The generated file contains the necessary ``#include`` directives, type
    aliases (``I``, ``C``, ``R``, ``F``), and a ``main()`` that branches on
    ``app.mode`` at runtime: ``"inception"`` activates ``DischargeInceptionStepper``
    and ``"plasma"`` activates the chosen ``ItoKMCStepper`` subclass.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.  Consumed
            attributes:

            * ``discharge_home`` — path to the chombo-discharge source tree.
            * ``base_dir`` — parent directory for the new application.
            * ``app_name`` — subdirectory name of the new application.
            * ``geometry`` — computational geometry class name.
            * ``physics`` — ItoKMC plasma physics model class name.
            * ``ito_solver`` — Ito-diffusion solver type (``I`` alias).
            * ``cdr_solver`` — CDR solver type (``C`` alias).
            * ``rte_solver`` — radiative-transfer solver type (``R`` alias).
            * ``field_solver`` — Poisson/field solver type (``F`` alias).
            * ``plasma_stepper`` — ItoKMC time-stepper for plasma mode.
            * ``plasma_tagger`` — cell-tagger for plasma mode, or ``"none"``.

    Side effects:
        Creates ``<base_dir>/<app_name>/`` (if absent) and writes
        ``<base_dir>/<app_name>/main.cpp``.  Prints a warning to stdout for
        each expected header file that cannot be found on disk.
    """
    discharge_home = args.discharge_home

    # Warn (don't abort) if expected headers are missing
    headers_to_check = [
        discharge_home + "/Geometries/" + args.geometry + "/CD_" + args.geometry + ".H",
        discharge_home + "/Physics/ItoKMC/PlasmaModels/" + args.physics + "/CD_" + args.physics + ".H",
        discharge_home + "/Physics/ItoKMC/TimeSteppers/" + args.plasma_stepper + "/CD_" + args.plasma_stepper + ".H",
        discharge_home + "/Physics/DischargeInception/CD_DischargeInceptionStepper.H",
        discharge_home + "/Physics/DischargeInception/CD_DischargeInceptionTagger.H",
    ]
    if args.plasma_tagger != "none":
        headers_to_check.append(
            discharge_home + "/Physics/ItoKMC/CellTaggers/" + args.plasma_tagger + "/CD_" + args.plasma_tagger + ".H"
        )
    for h in headers_to_check:
        if not os.path.exists(h):
            print("Warning: could not find " + h)

    app_dir = args.base_dir + "/" + args.app_name
    os.makedirs(app_dir, exist_ok=True)

    main_filename = app_dir + "/main.cpp"
    with open(main_filename, "w") as f:
        # Includes
        f.write("#include <fstream>\n")
        f.write("#include <nlohmann/json.hpp>\n")
        f.write("\n")
        f.write("#include <ParmParse.H>\n")
        f.write("\n")
        f.write("#include <CD_Driver.H>\n")
        f.write("#include <CD_" + args.geometry + ".H>\n")
        f.write("#include <CD_DischargeInceptionStepper.H>\n")
        f.write("#include <CD_DischargeInceptionTagger.H>\n")
        f.write("#include <CD_" + args.physics + ".H>\n")
        f.write("#include <CD_" + args.plasma_stepper + ".H>\n")
        if args.plasma_tagger != "none":
            f.write("#include <CD_" + args.plasma_tagger + ".H>\n")
        f.write("\n")

        # Namespaces
        f.write("using namespace ChomboDischarge;\n")
        f.write("using namespace Physics::ItoKMC;\n")
        f.write("using namespace Physics::DischargeInception;\n")
        f.write("\n")

        # Type aliases
        f.write("using I = " + args.ito_solver + ";\n")
        f.write("using C = " + args.cdr_solver + ";\n")
        f.write("using R = " + args.rte_solver + ";\n")
        f.write("using F = " + args.field_solver + ";\n")
        f.write("\n")

        # main()
        f.write("int\n")
        f.write("main(int argc, char* argv[])\n")
        f.write("{\n")
        f.write("  ChomboDischarge::initialize(argc, argv);\n")
        f.write("\n")
        f.write("  Random::seed();\n")
        f.write("\n")
        f.write("  ParmParse app(\"app\");\n")
        f.write("  ParmParse kmc(\"" + args.physics + "\");\n")
        f.write("  ParmParse plasma(\"plasma\");\n")
        f.write("\n")
        f.write("  std::string mode;\n")
        f.write("  std::string chemistryFile;\n")
        f.write("\n")
        f.write("  Real voltage;\n")
        f.write("  Real pressure;\n")
        f.write("  Real temperature;\n")
        f.write("  Real N;\n")
        f.write("\n")
        f.write("  app.get(\"mode\", mode);\n")
        f.write("  kmc.get(\"chemistry_file\", chemistryFile);\n")
        f.write("  plasma.get(\"voltage\", voltage);\n")
        f.write("\n")
        f.write("  const auto json = nlohmann::json::parse(std::ifstream(chemistryFile), nullptr, true, true);\n")
        f.write("\n")
        f.write("  pressure    = json[\"gas\"][\"law\"][\"ideal_gas\"][\"pressure\"].get<Real>();\n")
        f.write("  temperature = json[\"gas\"][\"law\"][\"ideal_gas\"][\"temperature\"].get<Real>();\n")
        f.write("  N           = pressure / (Units::kb * temperature);\n")
        f.write("\n")
        f.write("  RefCountedPtr<TimeStepper>           timestepper;\n")
        f.write("  RefCountedPtr<Driver>                driver;\n")
        f.write("  RefCountedPtr<CellTagger>            celltagger;\n")
        f.write("  RefCountedPtr<AmrMesh>               amr      = RefCountedPtr<AmrMesh>(new AmrMesh());\n")
        f.write("  RefCountedPtr<ComputationalGeometry> geometry = RefCountedPtr<ComputationalGeometry>(new " + args.geometry + "());\n")
        f.write("  RefCountedPtr<ItoKMCPhysics>         physics  = RefCountedPtr<ItoKMCPhysics>(new " + args.physics + "());\n")
        f.write("\n")

        # inception mode
        f.write("  if (mode == \"inception\") {\n")
        f.write("    auto alpha = [physics](const Real& E, const RealVect& x) -> Real {\n")
        f.write("      return physics->computeAlpha(E, x);\n")
        f.write("    };\n")
        f.write("    auto eta = [physics](const Real& E, const RealVect& x) -> Real {\n")
        f.write("      return physics->computeEta(E, x);\n")
        f.write("    };\n")
        f.write("    auto alphaEff = [&](const Real& E, const RealVect x) -> Real {\n")
        f.write("      return alpha(E, x) - eta(E, x);\n")
        f.write("    };\n")
        f.write("\n")
        f.write("    auto ts = RefCountedPtr<DischargeInceptionStepper<>>(new DischargeInceptionStepper<>());\n")
        f.write("    auto ct = RefCountedPtr<DischargeInceptionTagger>(\n")
        f.write("      new DischargeInceptionTagger(amr, ts->getElectricField(), alphaEff));\n")
        f.write("\n")
        f.write("    ts->setAlpha(alpha);\n")
        f.write("    ts->setEta(eta);\n")
        f.write("\n")
        f.write("    timestepper = ts;\n")
        f.write("    celltagger  = ct;\n")
        f.write("  }\n")

        # plasma mode
        f.write("  else if (mode == \"plasma\") {\n")
        f.write("    auto ts = RefCountedPtr<ItoKMCStepper<I, C, R, F>>(new " + args.plasma_stepper + "<I, C, R, F>(physics));\n")
        if args.plasma_tagger != "none":
            f.write("    auto ct = RefCountedPtr<CellTagger>(new " + args.plasma_tagger + "<ItoKMCStepper<I, C, R, F>>(physics, ts, amr));\n")
        else:
            f.write("    auto ct = RefCountedPtr<CellTagger>(nullptr);\n")
        f.write("\n")
        f.write("    ts->setVoltage([voltage](const Real) {\n")
        f.write("      return voltage;\n")
        f.write("    });\n")
        f.write("\n")
        f.write("    timestepper = ts;\n")
        f.write("    celltagger  = ct;\n")
        f.write("  }\n")

        # else error
        f.write("  else {\n")
        f.write("    MayDay::Error(\"app.mode must be 'inception' or 'plasma'\");\n")
        f.write("  }\n")
        f.write("\n")
        f.write("  driver = RefCountedPtr<Driver>(new Driver(geometry, timestepper, amr, celltagger));\n")
        f.write("  driver->setupAndRun();\n")
        f.write("\n")
        f.write("  ChomboDischarge::finalize();\n")
        f.write("}\n")
