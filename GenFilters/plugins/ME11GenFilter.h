#ifndef GEMDQMUtils_GenFilters_ME11GenFilter_h
#define GEMDQMUtils_GenFilters_ME11GenFilter_h

#include "FWCore/Framework/interface/one/EDFilter.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/Event.h"

#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"

#include "DataFormats/GeometryVector/interface/GlobalPoint.h"
#include "DataFormats/GeometryVector/interface/GlobalVector.h"

#include "SimDataFormats/GeneratorProducts/interface/HepMCProduct.h"

#include "TrackingTools/Records/interface/TrackingComponentsRecord.h"
#include "MagneticField/Records/interface/IdealMagneticFieldRecord.h"

#include "Geometry/CSCGeometry/interface/CSCGeometry.h"
#include "DataFormats/GeometrySurface/interface/BoundDisk.h"
#include "MagneticField/Engine/interface/MagneticField.h"
#include "RecoMuon/TrackingTools/interface/MuonServiceProxy.h"
#include "TrackPropagation/SteppingHelixPropagator/interface/SteppingHelixPropagator.h"
#include "TrackingTools/TrajectoryState/interface/TrajectoryStateOnSurface.h"
#include "TrackingTools/TrajectoryState/interface/FreeTrajectoryState.h"

class ME11GenFilter : public edm::one::EDFilter<edm::one::SharedResources> {
 public:
  explicit ME11GenFilter(const edm::ParameterSet&);
  ~ME11GenFilter() override;
  static void fillDescriptions(edm::ConfigurationDescriptions &);

  bool filter(edm::Event &, const edm::EventSetup &) override;

 private:
  std::vector<Disk::DiskPointer> buildME11Disks(const edm::ESHandle<CSCGeometry>&);

  bool propagateToME11(const GlobalPoint&,
                       const GlobalVector&,
                       const int,
                       const edm::ESHandle<MagneticField>&,
                       const edm::ESHandle<Propagator>&,
                       const Disk::DiskPointer&);

  const edm::ESGetToken<CSCGeometry, MuonGeometryRecord>         kCSCGeometryToken_;
  const edm::EDGetTokenT<edm::HepMCProduct>                      kHepMCProductToken_;
  const edm::ESGetToken<MagneticField, IdealMagneticFieldRecord> kMagneticFieldToken_; 
  const edm::ESGetToken<Propagator, TrackingComponentsRecord>    kPropagatorToken_;
};

#endif // GEMDQMUtils_GenFilters_ME11GenFilter_h
