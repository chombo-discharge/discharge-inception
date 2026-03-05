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
using namespace Physics::ItoKMC;
using namespace Physics::DischargeInception;

#warning "Ion mobilities must scale against N (currently, they do not)"

int
main(int argc, char* argv[])
{
  ChomboDischarge::initialize(argc, argv);

  Random::seed();

  ParmParse app("app");
  ParmParse kmc("ItoKMCJSON");
  ParmParse plasma("plasma");

  std::string mode;
  std::string chemistryFile;

  Real voltage;
  Real pressure;
  Real temperature;
  Real secondTownsend;
  Real N;

  app.get("mode", mode);
  kmc.get("chemistry_file", chemistryFile);
  plasma.get("voltage", voltage);

  const auto json = nlohmann::json::parse(std::ifstream(chemistryFile), nullptr, true, true);

  pressure    = json["gas"]["law"]["ideal_gas"]["pressure"].get<Real>();
  temperature = json["gas"]["law"]["ideal_gas"]["temperature"].get<Real>();
  N           = pressure / (Units::kb * temperature);

  RefCountedPtr<TimeStepper>           timeStepper;
  RefCountedPtr<Driver>                driver;
  RefCountedPtr<CellTagger>            cellTagger;
  RefCountedPtr<AmrMesh>               amr      = RefCountedPtr<AmrMesh>(new AmrMesh());
  RefCountedPtr<ComputationalGeometry> geometry = RefCountedPtr<ComputationalGeometry>(new Rod());
  RefCountedPtr<ItoKMCPhysics>         physics  = RefCountedPtr<ItoKMCPhysics>(new ItoKMCJSON());

  if (mode == "inception") {

    // Second Townsend ionization coefficient. This is something that now becomes hard-wired to the chemistry file. For simplicity, we use the
    // average rate of reactions that produce electrons.
    int numEmissionMechanisms = 0;

    for (const auto& entry : json["electrode emission"]) {
      const auto& products     = entry["@"];
      const auto& efficiencies = entry["efficiencies"];

      for (size_t i = 0; i < products.size(); ++i) {
        if (products[i].get<std::string>() == "e") {
          secondTownsend += efficiencies[i].get<Real>();
        }
      }
    }

    secondTownsend = (numEmissionMechanisms) > 0 ? secondTownsend / numEmissionMechanisms : 0.0;

    auto alpha = [physics](const Real& E, const RealVect& x) -> Real {
      return physics->computeAlpha(E, x);
    };
    auto eta = [physics](const Real& E, const RealVect& x) -> Real {
      return physics->computeEta(E, x);
    };
    auto alphaEff = [&](const Real& E, const RealVect x) -> Real {
      return alpha(E, x) - eta(E, x);
    };
    auto secondaryEmission = [&](const Real& E, const RealVect& x) -> Real {
      return secondTownsend;
    };

    auto ts = RefCountedPtr<DischargeInceptionStepper<>>(new DischargeInceptionStepper<>());
    auto ct = RefCountedPtr<DischargeInceptionTagger>(
      new DischargeInceptionTagger(amr, ts->getElectricField(), alphaEff));

    ts->setAlpha(alpha);
    ts->setEta(eta);
    ts->setSecondaryEmission(secondaryEmission);

    timeStepper = ts;
    cellTagger  = ct;
  }
  else if (mode == "plasma") {
    auto ts = RefCountedPtr<ItoKMCStepper<>>(new ItoKMCBackgroundEvaluator<>(physics));
    auto ct = RefCountedPtr<CellTagger>(new ItoKMCStreamerTagger<ItoKMCStepper<>>(physics, ts, amr));

    ts->setVoltage([voltage](const Real) {
      return voltage;
    });

    timeStepper = ts;
    cellTagger  = ct;
  }
  else {
    MayDay::Error("app.mode must be 'inception' or 'plasma'");
  }

  driver = RefCountedPtr<Driver>(new Driver(geometry, timeStepper, amr, cellTagger));
  driver->setupAndRun();

  ChomboDischarge::finalize();
}
