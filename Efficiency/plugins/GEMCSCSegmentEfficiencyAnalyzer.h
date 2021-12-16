#ifndef GEMDQMUtils_Efficiency_GEMCSCSegmentEfficiencyAnalyzer_h
#define GEMDQMUtils_Efficiency_GEMCSCSegmentEfficiencyAnalyzer_h

#include "GEMDQMUtils/Efficiency/interface/GEMLayerData.h"

#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/Framework/interface/ConsumesCollector.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ServiceRegistry/interface/Service.h"

#include "Geometry/GEMGeometry/interface/GEMGeometry.h"
#include "Geometry/GEMGeometry/interface/GEMEtaPartition.h"
#include "Geometry/GEMGeometry/interface/GEMEtaPartitionSpecs.h"
#include "Geometry/CSCGeometry/interface/CSCGeometry.h"
#include "Geometry/Records/interface/MuonGeometryRecord.h"

#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/GEMRecHit/interface/GEMRecHitCollection.h"
#include <DataFormats/GEMRecHit/interface/GEMCSCSegmentCollection.h>
#include "DataFormats/CSCRecHit/interface/CSCSegmentCollection.h"

#include "SimDataFormats/Track/interface/SimTrackContainer.h"

#include "RecoMuon/TrackingTools/interface/MuonSegmentMatcher.h"

#include "TTree.h"


class GEMCSCSegmentEfficiencyAnalyzer : public edm::one::EDAnalyzer<> {
 public:
  explicit GEMCSCSegmentEfficiencyAnalyzer(const edm::ParameterSet&);
  ~GEMCSCSegmentEfficiencyAnalyzer();
  static void fillDescriptions(edm::ConfigurationDescriptions &);
 
 private:
  // method
  virtual void analyze(const edm::Event&, const edm::EventSetup&);
  void beginJob();
  void endJob();

  void resetBranch();

  template <typename T>
  edm::EDGetTokenT<T> getToken(const edm::ParameterSet&, const std::string&);

  // parameters
  const edm::ESGetToken<GEMGeometry, MuonGeometryRecord>                      kGEMToken_;
  const edm::ESGetToken<GEMGeometry, MuonGeometryRecord>                      kGEMTokenBeginRun_;
  const edm::ESGetToken<CSCGeometry, MuonGeometryRecord>                      kCSCToken_;
  // parmaeters from ParameterSet
  const edm::EDGetTokenT<GEMRecHitCollection>                                 kGEMRecHitToken_;
  const edm::EDGetTokenT<CSCSegmentCollection>                                kCSCSegmentToken_;
  const edm::EDGetTokenT<GEMCSCSegmentCollection>                             kGEMCSCSegmentToken_;
  const edm::EDGetTokenT<edm::View<reco::Muon> >                              kMuonToken_;
  const edm::EDGetTokenT<reco::MuonCollection>                              kMuonColToken_;
  const edm::EDGetTokenT<edm::ValueMap<reco::MuonSimInfo> >                   kMuonSimInfoToken_;

  std::unique_ptr<MuonSegmentMatcher> muon_segment_matcher_;

  TTree* tree_;

  // GEMCSCSegment
  float b_gemcsc_reduced_chi2_;
  int b_gemcsc_cschit_size_;
  int b_gemcsc_gemhit_size_;
  int b_gemcsc_region_;

  // CSCSegment, only for ME11
  int b_csc_chamber_;
  bool b_csc_is_me1a_;
  float b_csc_reduced_chi2_;

  // GEMRecHit, only for GE11
  int b_gem_chamber_;

  bool b_gem_has_layer1_;
  int b_gem_layer1_ieta_;
  int b_gem_layer1_strip_;
  int b_gem_layer1_cls_;
  int b_gem_layer1_bx_;

  bool b_gem_has_layer2_;
  int b_gem_layer2_ieta_;
  int b_gem_layer2_strip_;
  int b_gem_layer2_cls_;
  int b_gem_layer2_bx_;

  // muon
  bool b_is_matched_with_muon_;
  float b_muon_pt_;
  float b_muon_eta_;
  float b_muon_phi_;
  int b_muon_charge_;

  //
  const std::string kLogCategory_ = "GEMCSCSegmentEfficiencyAnalyzer";
};


template <typename T>
edm::EDGetTokenT<T> GEMCSCSegmentEfficiencyAnalyzer::getToken(const edm::ParameterSet& parameter_set, const std::string& name) {
  return consumes<T>(parameter_set.getParameter<edm::InputTag>(name));
}

#endif // GEMDQMUtils_Efficiency_GEMCSCSegmentEfficiencyAnalyzer_h
