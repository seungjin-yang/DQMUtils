#include "GEMDQMUtils/GenFilters/plugins/ME11GenFilter.h"

#include "FWCore/Framework/interface/ESHandle.h"
#include "DataFormats/Common/interface/Handle.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "TrackingTools/TrajectoryState/interface/TrajectoryStateOnSurface.h"
#include "TrackingTools/TrajectoryState/interface/FreeTrajectoryState.h"
#include "FWCore/ServiceRegistry/interface/Service.h"

#include "Geometry/CSCGeometry/interface/CSCChamber.h"


ME11GenFilter::ME11GenFilter(const edm::ParameterSet& parameter_set)
    : kCSCGeometryToken_(esConsumes<CSCGeometry, MuonGeometryRecord>()),
      kHepMCProductToken_(consumes<edm::HepMCProduct>(parameter_set.getParameter<edm::InputTag>("hepMCProductTag"))),
      kMagneticFieldToken_(esConsumes()),
      kPropagatorToken_(esConsumes(parameter_set.getParameter<edm::ESInputTag>("propagatorTag"))) {
}

ME11GenFilter::~ME11GenFilter() {}

void ME11GenFilter::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;

  desc.add<edm::InputTag>("hepMCProductTag", edm::InputTag("generator", "unsmeared"));
  desc.add<edm::ESInputTag>("propagatorTag", edm::ESInputTag("", "SteppingHelixPropagatorAlong"));
  descriptions.add("ME11GenFilter", desc);
}


bool ME11GenFilter::filter(edm::Event& event, const edm::EventSetup& setup) {
  const edm::Handle<edm::HepMCProduct>&& hep_mc_product = event.getHandle(kHepMCProductToken_);
  if (not hep_mc_product.isValid()) {
    edm::LogError("ME11GenFilter") << "invalid HepMCProduct";
    return false;
  }

  //////////////////////////////////////////////////////////////////////////////
  const edm::ESHandle<CSCGeometry>&& csc = setup.getHandle(kCSCGeometryToken_);
  if (not csc.isValid()) {
    edm::LogError("ME11GenFilter") << "invalid CSCGeometry";
    return false;
  }

  const edm::ESHandle<MagneticField>&& magnetic_field = setup.getHandle(kMagneticFieldToken_);
  if (not magnetic_field.isValid()) {
    edm::LogError("ME11GenFilter") << "invalid MagneticField";
    return false;
  }

  const edm::ESHandle<Propagator>&& propagator = setup.getHandle(kPropagatorToken_);
  if (not propagator.isValid()) {
    edm::LogError("ME11GenFilter") << "invalid Propagator";
    return false;
  }

  //////////////////////////////////////////////////////////////////////////////
  const std::vector<Disk::DiskPointer>&& me11_vector = buildME11Disks(csc);

  bool result = false;

  const HepMC::GenEvent *gen_event = hep_mc_product->GetEvent();
  // for (HepMC::GenEvent::particle_const_iterator particle_iter : gen_event->particles()) {
  for (HepMC::GenEvent::particle_const_iterator particle_iter = gen_event->particles_begin(); particle_iter != gen_event->particles_end(); particle_iter++) {
    const HepMC::GenParticle* particle = *particle_iter;

    if (particle->status() != 1) {
      // look only at stable particles   
      continue;
    }

    if (std::abs(particle->pdg_id()) != 13) {
      // look only at muons
      continue;
    }

    // Get the position and momentum
    const HepMC::ThreeVector hepmc_position{particle->production_vertex()->point3d()};
    const GlobalPoint position(hepmc_position.x() / 10., hepmc_position.y() / 10., hepmc_position.z() / 10.); // mm to cm

    const HepMC::FourVector hepmc_momentum{particle->momentum()}; // GeV
    const GlobalVector momentum(hepmc_momentum.x(), hepmc_momentum.y(), hepmc_momentum.z());

    const int charge = particle->pdg_id() > 0 ? -1 : 1;

    for (const Disk::DiskPointer& me11_disk : me11_vector) {
      if (propagateToME11(position, momentum, charge, magnetic_field, propagator, me11_disk)) {
        result = true;
        break;
      }
    }

    if (result) {
      break;
    }
  } // particles

  return result;
}


std::vector<Disk::DiskPointer> ME11GenFilter::buildME11Disks(
    const edm::ESHandle<CSCGeometry>& csc) {

  std::map<int, std::vector<const CSCChamber*> > me11_chambers_per_endcap;
  for (const CSCChamber* chamber : csc->chambers()) {
    const CSCDetId&& chamber_id = chamber->id();
    if (not chamber_id.isME11()) {
      continue;
    }

    const int endcap = chamber_id.endcap();

    if (me11_chambers_per_endcap.find(endcap) == me11_chambers_per_endcap.end()) {
      me11_chambers_per_endcap.insert({endcap, std::vector<const CSCChamber*>()});
    }

    me11_chambers_per_endcap.at(endcap).push_back(chamber);
  }

  const float inf = std::numeric_limits<float>::infinity();
  std::vector<Disk::DiskPointer> me11_vector;

  for (const auto [endcap, chamber_vector] : me11_chambers_per_endcap) {

    float rmin = +inf;
    float rmax = -inf;
    float zmin = +inf;
    float zmax = -inf;

    for (const CSCChamber* chamber : chamber_vector) {
      auto [chamber_rmin, chamber_rmax] = chamber->surface().rSpan();
      auto [chamber_zmin, chamber_zmax] = chamber->surface().zSpan();

      rmin = std::min(rmin, chamber_rmin);
      rmax = std::max(rmax, chamber_rmax);
      zmin = std::min(zmin, chamber_zmin);
      zmax = std::max(zmax, chamber_zmax);
    }

    const float layer_z = chamber_vector.at(0)->position().z();
    Surface::PositionType position{0.f, 0.f, layer_z};
    Surface::RotationType rotation;

    zmin -= layer_z;
    zmax -= layer_z;

    if ((rmin > rmax) or (zmin > zmax)) {
      edm::LogError("ME11GenFilter") << "wrong";
      continue;
    }

    // the bounds from min and max R and Z in the local coordinates.
    SimpleDiskBounds* bounds = new SimpleDiskBounds(rmin, rmax, zmin, zmax);
    const Disk::DiskPointer&& disk = Disk::build(position, rotation, bounds);

    me11_vector.push_back(disk);
  }

  return me11_vector;
}


bool ME11GenFilter::propagateToME11(const GlobalPoint& starting_state_position,
                                    const GlobalVector& starting_state_momentum,
                                    const int charge,
                                    const edm::ESHandle<MagneticField>& magnetic_field,
                                    const edm::ESHandle<Propagator>& propagator,
                                    const Disk::DiskPointer& me11_disk) {

  const FreeTrajectoryState starting_state{starting_state_position,
                                           starting_state_momentum,
                                           charge,
                                           magnetic_field.product()};

  const TrajectoryStateOnSurface&& propagated_state = propagator->propagate(
      starting_state, *me11_disk);

  if (not propagated_state.isValid()) {
    return false;
  }

  const LocalPoint&& local_point = (*me11_disk).toLocal(propagated_state.globalPosition());
  if (not (*me11_disk).bounds().inside(local_point)) {
    return false;
  }

  return true;
}
