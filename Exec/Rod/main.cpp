#include <CD_Driver.H>
#include <CD_Rod.H>
#include <CD_DischargeInceptionStepper.H>
#include <CD_DischargeInceptionTagger.H>
#include <CD_ItoKMCJSON.H>
#include <CD_ItoKMCBackgroundEvaluator.H>
#include <CD_ItoKMCStreamerTagger.H>
#include <ParmParse.H>

#include <nlohmann/json.hpp>
#include <fstream>

using namespace ChomboDischarge;

int
main(int argc, char* argv[])
{
  ChomboDischarge::initialize(argc, argv);

  std::string mode;
  ParmParse("App").get("mode", mode);

  // Geometry and AMR are shared by both branches.
  auto compgeom = RefCountedPtr<ComputationalGeometry>(new Rod());
  auto amr      = RefCountedPtr<AmrMesh>(new AmrMesh());

  if (mode == "inception") {
    using namespace Physics::DischargeInception;

    // Read pressure and temperature from chemistry.json (single source of truth).
    Real p, T;
    {
      std::ifstream f("chemistry.json");
      const auto    chem = nlohmann::json::parse(f);
      p                  = chem["gas"]["law"]["ideal_gas"]["pressure"].get<Real>();
      T                  = chem["gas"]["law"]["ideal_gas"]["temperature"].get<Real>();
    }
    const Real N = p / (Units::kb * T);

    // Create ItoKMCJSON physics object — derives alpha/eta from the reaction network.
    auto physics = RefCountedPtr<Physics::ItoKMC::ItoKMCPhysics>(new Physics::ItoKMC::ItoKMCJSON());

    // Read data for the voltage curve.
    Real peak           = 0.0;
    Real t0             = 0.0;
    Real t1             = 0.0;
    Real t2             = 0.0;
    Real secondTownsend = 0.0;

    ParmParse li("lightning_impulse");
    li.get("peak", peak);
    li.get("start", t0);
    li.get("tail_time", t1);
    li.get("front_time", t2);

    ParmParse di("DischargeInception");
    di.get("second_townsend", secondTownsend);

    // Alpha and eta from ItoKMCJSON (same source as plasma branch).
    auto alpha = [physics](const Real& E, const RealVect& x) -> Real {
      return physics->computeAlpha(E, x);
    };
    auto eta = [physics](const Real& E, const RealVect& x) -> Real {
      return physics->computeEta(E, x);
    };
    auto alphaEff = [&](const Real& E, const RealVect x) -> Real {
      return alpha(E, x) - eta(E, x);
    };
    auto bgRate = [&](const Real& E, const RealVect& x) -> Real {
      return 0.0;
    };
    auto detachRate = [&](const Real& E, const RealVect& x) -> Real {
      const Real Etd = E / (N * 1E-21);
      return 1.24E-11 * 1E-6 * N * exp(-std::pow((179.0 / (8.8 + Etd)), 2));
    };
    auto ionMobility = [&](const Real& E) -> Real {
      return 2E-4;
    };
    auto ionDiffusion = [&](const Real& E) -> Real {
      return ionMobility(E) * Units::kb * T / Units::Qe;
    };
    auto ionDensity = [&](const RealVect& x) -> Real {
      return 4.E6;
    };
    auto voltageCurve = [&](const Real& t) -> Real {
      return peak * (exp(-(t + t0) / t1) - exp(-(t + t0) / t2));
    };
    auto fieldEmission = [&](const Real& E, const RealVect& x) -> Real {
      const Real beta = 1.0; // Field enhancement factor
      const Real phi  = 4.5;
      const Real C1   = 1.54E-6 * std::pow(10, 4.52 / sqrt(phi)) / phi;
      const Real C2   = 2.84E9 * std::pow(phi, 1.5);

      return C1 * (E * E) * exp(-C2 / (beta * E));
    };
    auto secondaryEmission = [&](const Real& E, const RealVect& x) -> Real {
      return secondTownsend;
    };

    // Set up time stepper
    auto timestepper = RefCountedPtr<DischargeInceptionStepper<>>(new DischargeInceptionStepper<>());
    auto celltagger  = RefCountedPtr<DischargeInceptionTagger>(
      new DischargeInceptionTagger(amr, timestepper->getElectricField(), alphaEff));

    // Set transport data
    timestepper->setAlpha(alpha);
    timestepper->setEta(eta);
    timestepper->setBackgroundRate(bgRate);
    timestepper->setDetachmentRate(detachRate);
    timestepper->setFieldEmission(fieldEmission);
    timestepper->setIonMobility(ionMobility);
    timestepper->setIonDiffusion(ionDiffusion);
    timestepper->setIonDensity(ionDensity);
    timestepper->setVoltageCurve(voltageCurve);
    timestepper->setSecondaryEmission(secondaryEmission);

    // Set up the Driver and run it
    auto engine = RefCountedPtr<Driver>(new Driver(compgeom, timestepper, amr, celltagger));
    engine->setupAndRun();
  }
  else if (mode == "plasma") {
    using namespace Physics::ItoKMC;

    // Get potential and output basename from input script
    Real        g_potential;
    std::string basename;
    {
      ParmParse pp("StreamerIntegralCriterion");
      pp.get("potential", g_potential);
      pp.get("basename", basename);
      setPoutBaseName(basename);
    }

    // Initialize RNG
    Random::seed();

    auto physics     = RefCountedPtr<ItoKMCPhysics>(new ItoKMCJSON());
    auto timestepper = RefCountedPtr<ItoKMCStepper<>>(new ItoKMCBackgroundEvaluator<>(physics));
    auto tagger      = RefCountedPtr<CellTagger>(
      new ItoKMCStreamerTagger<ItoKMCStepper<>>(physics, timestepper, amr));

    // Set constant voltage
    timestepper->setVoltage([g_potential](const Real) { return g_potential; });

    // Set up the Driver and run it
    auto engine = RefCountedPtr<Driver>(new Driver(compgeom, timestepper, amr, tagger));
    engine->setupAndRun();
  }
  else {
    MayDay::Error("App.mode must be 'inception' or 'plasma'");
  }

  ChomboDischarge::finalize();
}
