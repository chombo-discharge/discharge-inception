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

  Random::seed();  

  std::string mode;
  std::string chemistryFile;
  
  ParmParse("App").get("mode", mode);

  auto compgeom = RefCountedPtr<ComputationalGeometry>(new Rod());
  auto amr      = RefCountedPtr<AmrMesh>(new AmrMesh());
  auto physics  = RefCountedPtr<Physics::ItoKMC::ItoKMCPhysics>(new Physics::ItoKMC::ItoKMCJSON());

  if (mode == "inception") {
    using namespace Physics::DischargeInception;

    // Read pressure, temperature, and secondTownsend from chemistry.json (single source of truth).
    Real p, T;
    Real secondTownsend = 0.0;
    {
      std::string chemFile;
      ParmParse("ItoKMCJSON").get("chemistry_file", chemFile);
      std::ifstream f(chemFile);
      const auto    chem = nlohmann::json::parse(f);
      p                  = chem["gas"]["law"]["ideal_gas"]["pressure"].get<Real>();
      T                  = chem["gas"]["law"]["ideal_gas"]["temperature"].get<Real>();

      // Derive gamma from electrode emission — first reaction that emits an electron.
      for (const auto& entry : chem["electrode emission"]) {
        const auto& products     = entry["@"];
        const auto& efficiencies = entry["efficiencies"];
        for (size_t i = 0; i < products.size(); ++i) {
          if (products[i].get<std::string>() == "e") {
            secondTownsend = efficiencies[i].get<Real>();
            goto done;
          }
        }
      }
    }
    
    const Real N = p / (Units::kb * T);

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
      return 1.0;
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

    Real g_potential;
    ParmParse("StreamerIntegralCriterion").get("potential", g_potential);

    auto timestepper = RefCountedPtr<ItoKMCStepper<>>(new ItoKMCBackgroundEvaluator<>(physics));
    auto tagger      = RefCountedPtr<CellTagger>(new ItoKMCStreamerTagger<ItoKMCStepper<>>(physics, timestepper, amr));
    
    timestepper->setVoltage([g_potential](const Real) {
      return g_potential;
    });

    auto engine = RefCountedPtr<Driver>(new Driver(compgeom, timestepper, amr, tagger));
    engine->setupAndRun();      
  }
  else {
    MayDay::Error("App.mode must be 'inception' or 'plasma'");
  }



  ChomboDischarge::finalize();
}
