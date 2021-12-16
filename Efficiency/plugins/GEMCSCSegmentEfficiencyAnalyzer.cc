#include "GEMDQMUtils/Efficiency/plugins/GEMCSCSegmentEfficiencyAnalyzer.h"

#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/GeometryCommonDetAlgo/interface/ErrorFrameTransformer.h"
#include "Validation/MuonHits/interface/MuonHitHelper.h"

#include <numeric> // iota
#include <algorithm> // minmax_element

GEMCSCSegmentEfficiencyAnalyzer::GEMCSCSegmentEfficiencyAnalyzer(const edm::ParameterSet& parameter_set)
    : kGEMToken_(esConsumes<GEMGeometry, MuonGeometryRecord>()),
      kGEMTokenBeginRun_(esConsumes<edm::Transition::BeginRun>()),
      kCSCToken_(esConsumes<CSCGeometry, MuonGeometryRecord>()),
      kGEMRecHitToken_(getToken<GEMRecHitCollection>(parameter_set, "gemRecHitTag")),
      kCSCSegmentToken_(getToken<CSCSegmentCollection>(parameter_set, "cscSegmentTag")),
      kGEMCSCSegmentToken_(getToken<GEMCSCSegmentCollection>(parameter_set, "gemcscSegmentTag")),
      kMuonToken_(getToken<edm::View<reco::Muon> >(parameter_set, "recoMuonTag")),
      kMuonColToken_(getToken<reco::MuonCollection>(parameter_set, "recoMuonTag")),
      kMuonSimInfoToken_(getToken<edm::ValueMap<reco::MuonSimInfo> >(parameter_set, "muonSimInfoTag")) {

  edm::ConsumesCollector consumes_collector = consumesCollector();
  muon_segment_matcher_ = std::make_unique<MuonSegmentMatcher>(
      parameter_set.getParameter<edm::ParameterSet>("MatchParameters"),
      consumes_collector); 
}

void GEMCSCSegmentEfficiencyAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;
  desc.add<edm::InputTag>("gemRecHitTag", edm::InputTag("gemRecHits"));
  desc.add<edm::InputTag>("cscSegmentTag", edm::InputTag("cscSegments"));
  desc.add<edm::InputTag>("gemcscSegmentTag", edm::InputTag("gemcscSegments"));
  desc.add<edm::InputTag>("recoMuonTag", edm::InputTag("muons"));
  desc.add<edm::InputTag>("patMuonTag", edm::InputTag("muons"));
  desc.add<edm::InputTag>("muonSimInfoTag", edm::InputTag("muonSimClassifier"));

  {
    edm::ParameterSetDescription match_parameters;
    match_parameters.add<edm::InputTag>("DTsegments", edm::InputTag("dt4DSegments"));
    match_parameters.add<double>("DTradius", 0.01);
    match_parameters.add<edm::InputTag>("CSCsegments", edm::InputTag("cscSegments"));
    match_parameters.add<edm::InputTag>("RPChits", edm::InputTag("rpcRecHits"));
    match_parameters.add<bool>("TightMatchDT", false);
    match_parameters.add<bool>("TightMatchCSC", true);

    desc.add<edm::ParameterSetDescription>("MatchParameters", match_parameters);
  }

  descriptions.add("GEMCSCSegmentEfficiencyAnalyzer", desc);
}

GEMCSCSegmentEfficiencyAnalyzer::~GEMCSCSegmentEfficiencyAnalyzer() {
}

void GEMCSCSegmentEfficiencyAnalyzer::beginJob() {
  edm::Service<TFileService> file_service;

  tree_ = file_service->make<TTree>("GEM", "GEM");

  // for the single numerical variables and the nested vector 
  #define BRANCH(name) tree_->Branch(#name, &b_##name##_);

  #define BRANCH_(name, suffix) tree_->Branch(#name, &b_##name##_, #name "/" #suffix);
  #define BRANCH_F(name) BRANCH_(name, F);
  #define BRANCH_I(name) BRANCH_(name, I);
  #define BRANCH_O(name) BRANCH_(name, O);

  //
  #define BRANCH_V_(name, type) tree_->Branch(#name, "vector<"#type">", &b_##name##_);
  #define BRANCH_VF(name) BRANCH_V_(name, Float_t);
  #define BRANCH_VL(name) BRANCH_V_(name, Long_t);

  //
  BRANCH_F(gemcsc_reduced_chi2)
  BRANCH_I(gemcsc_gemhit_size)
  BRANCH_I(gemcsc_cschit_size)
  BRANCH_I(gemcsc_region) // CSCDetId::zendcap
  //
  BRANCH_I(csc_chamber)
  BRANCH_O(csc_is_me1a)
  BRANCH_F(csc_reduced_chi2)
  //
  BRANCH_I(gem_chamber)
  //
  BRANCH_O(gem_has_layer1)
  BRANCH_I(gem_layer1_ieta)
  BRANCH_I(gem_layer1_strip)
  BRANCH_I(gem_layer1_cls)
  BRANCH_I(gem_layer1_bx)
  //
  BRANCH_O(gem_has_layer2)
  BRANCH_I(gem_layer2_ieta)
  BRANCH_I(gem_layer2_strip)
  BRANCH_I(gem_layer2_cls)
  BRANCH_I(gem_layer2_bx)
  // if matched
  BRANCH_O(is_matched_with_muon)
  BRANCH_F(muon_pt)
  BRANCH_F(muon_eta)
  BRANCH_F(muon_phi)
  BRANCH_I(muon_charge)

  //
}

void GEMCSCSegmentEfficiencyAnalyzer::endJob() {

}

void GEMCSCSegmentEfficiencyAnalyzer::resetBranch() {
  b_gemcsc_reduced_chi2_ = -1.0f;
  b_gemcsc_cschit_size_ = -1;
  b_gemcsc_gemhit_size_ = -1;
  b_gemcsc_region_ = 0;

  b_csc_chamber_ = -1;
  b_csc_is_me1a_ = false;
  b_csc_reduced_chi2_ = -1.0f;

  b_gem_chamber_ = -1;

  b_gem_has_layer1_ = false;
  b_gem_layer1_ieta_ = -1;
  b_gem_layer1_strip_ = -1;
  b_gem_layer1_cls_ = -1;
  b_gem_layer1_bx_ = -1000;

  b_gem_has_layer2_ = false;
  b_gem_layer2_ieta_ = -1;
  b_gem_layer2_strip_ = -1;
  b_gem_layer2_cls_ = -1;
  b_gem_layer2_bx_ = -1000;

  b_is_matched_with_muon_ = false;
  b_muon_pt_ = -1.0f;
  b_muon_eta_ = -1000.0f;
  b_muon_phi_ = -1000.0f;
  b_muon_charge_ = 0;
}


void GEMCSCSegmentEfficiencyAnalyzer::analyze(const edm::Event& event, const edm::EventSetup& setup) {
  const edm::Handle<GEMCSCSegmentCollection>&& gemcsc_segment_collection = event.getHandle(kGEMCSCSegmentToken_);
  if (not gemcsc_segment_collection.isValid()) {
    edm::LogError(kLogCategory_) << "GEMCSCSegmentCollection is not valid";
    return;
  }

  const edm::Handle<GEMRecHitCollection>&& gem_rechit_collection = event.getHandle(kGEMRecHitToken_);
  if (not gem_rechit_collection.isValid()) {
    edm::LogError(kLogCategory_) << "GEMRecHitCollection is not valid";
    return;
  }

  const edm::Handle<CSCSegmentCollection>&& csc_segment_collection = event.getHandle(kCSCSegmentToken_);
  if (not csc_segment_collection.isValid()) {
    edm::LogError(kLogCategory_) << "CSCSegmentCollection is not valid";
    return;
  }

  const edm::Handle<edm::View<reco::Muon> >&& muon_view = event.getHandle(kMuonToken_);
  if (not muon_view.isValid()) {
    edm::LogError(kLogCategory_) << "View<Muon> is not valid";
    return;
  }

  const edm::Handle<reco::MuonCollection>&& muon_collection = event.getHandle(kMuonColToken_);
  if (not muon_collection.isValid()) {
    edm::LogError(kLogCategory_) << "MuonCollection is not valid";
    return;
  }

  const edm::Handle<edm::ValueMap<reco::MuonSimInfo> >& muon_sim_info_value_map = event.getHandle(kMuonSimInfoToken_);
  if (not muon_sim_info_value_map.isValid()) {
    edm::LogError(kLogCategory_) << "edm::ValueMap<reco::MuonSimInfo> is not valid";
    return;
  }

  //////////////////////////////////////////////////////////////////////////////
  const edm::ESHandle<GEMGeometry>&& gem = setup.getHandle(kGEMToken_);
  if (not gem.isValid()) {
    edm::LogError(kLogCategory_) << "GEMGeometry is not valid";
    return;
  }

  const edm::ESHandle<CSCGeometry>&& csc = setup.getHandle(kCSCToken_);
  if (not csc.isValid()) {
    edm::LogError(kLogCategory_) << "CSCGeometry is not valid";
    return;
  }

  //////////////////////////////////////////////////////////////////////////////
  if (gemcsc_segment_collection->size() == 0) {
    edm::LogInfo(kLogCategory_) << "GEMCSCSegment is empty";
    return;
  }

  // region, chamber, x, y, z
  // station=1, ring=1 or 4...
  std::map<std::tuple<int, int, float, float, float>, const reco::Muon*> matched_me11_segment_map;
  for (const reco::Muon& muon : *muon_view) {
    if (not muon.isStandAloneMuon()) {
      continue;
    }

    const reco::TrackRef&& track_ref = muon.outerTrack();
    for (const CSCSegment* csc_segment : muon_segment_matcher_->matchCSC(*track_ref, event)) {
      const CSCDetId&& csc_id = csc_segment->cscDetId();
      if (not csc_id.isME11()) {
        continue;
      }

      const LocalPoint&& local_position = csc_segment->localPosition();
      std::tuple<int, int, float, float, float> key = {
        csc_id.endcap(),
        csc_id.chamber(),
        local_position.x(),
        local_position.y(),
        local_position.z(),
      };

      matched_me11_segment_map.insert({key, &muon});
    }
  }

  std::cout << "edm::ValueMap<reco::MuonSimInfo>::size = " << muon_sim_info_value_map->size() << std::endl;
  for (size_t idx = 0; idx < muon_sim_info_value_map->size(); idx++) {
    std::vector<reco::MuonSimInfo>::const_reference muon_sim_info  = muon_sim_info_value_map->get(idx);
    std::cout << "flavor = " << muon_sim_info.flavour
              << ", pdgId = " << muon_sim_info.pdgId 
              << ", primary class = " << static_cast<int>(muon_sim_info.primaryClass)
              << ", motherFlavour = " << muon_sim_info.motherFlavour
              << ", motherPdgId = " << muon_sim_info.motherPdgId
              << std::endl;
  }

  /*
  for (unsigned int idx = 0; idx < muon_collection->size(); idx++) {
    const reco::Muon& muon = muon_collection->at(idx);

    const reco::MuonRef muon_ref(muon_collection, idx);

    std::vector<reco::MuonSimInfo>::const_reference muon_sim_info  = (*muon_sim_info_value_map)[muon_ref];
    std::cout << "flavor=" << muon_sim_info.flavour << std::endl;
  }
  */

  std::cout << "# of matched ME11 Segments = " << matched_me11_segment_map.size() << std::endl;
  // for (const auto [key, csc_segment] : matched_me11_segment_map) {
  //   csc_segment->print();
  // }

  //////////////////////////////////////////////////////////////////////////////
  for (edm::OwnVector<GEMCSCSegment>::const_iterator gemcsc_segment = gemcsc_segment_collection->begin(); gemcsc_segment != gemcsc_segment_collection->end(); gemcsc_segment++) {
    resetBranch();

    const CSCDetId&& csc_id = gemcsc_segment->cscDetId();
    if (not csc_id.isME11()) {
      continue;
    }
    const CSCSegment&& csc_segment = gemcsc_segment->cscSegment();

    const LocalPoint&& local_position = csc_segment.localPosition();
    std::tuple<int, int, float, float, float> key = {
      csc_id.endcap(),
      csc_id.chamber(),
      local_position.x(),
      local_position.y(),
      local_position.z(),
    };
    const bool is_matched = matched_me11_segment_map.find(key) != matched_me11_segment_map.end();

    const GEMRecHit* gem_hit_layer1 = nullptr;
    const GEMRecHit* gem_hit_layer2 = nullptr;

    for (const GEMRecHit& gem_hit : gemcsc_segment->gemRecHits()) {
      const GEMDetId&& gem_id = gem_hit.gemId();
      if (gem_id.station() != 1) {
        std::cerr << gem_id << std::endl;
        continue;
      }

      const int layer = gem_id.layer();
      if (layer == 1) {
        gem_hit_layer1 = &gem_hit;

      } else {
        gem_hit_layer2 = &gem_hit;

      }
    }

    // TTree
    b_gemcsc_reduced_chi2_ = static_cast<float>(gemcsc_segment->chi2()) / gemcsc_segment->degreesOfFreedom();
    b_gemcsc_cschit_size_ = gemcsc_segment->cscRecHits().size();
    b_gemcsc_gemhit_size_ = gemcsc_segment->gemRecHits().size();
    b_gemcsc_region_ = csc_id.zendcap();

    b_csc_chamber_ = csc_id.chamber();
    b_csc_is_me1a_ = csc_id.isME1a();
    b_csc_reduced_chi2_ = static_cast<float>(csc_segment.chi2()) / csc_segment.degreesOfFreedom();

    if (gem_hit_layer1) {
      const GEMDetId&& gem_id = gem_hit_layer1->gemId();
      const GEMEtaPartition* eta_partition = gem->etaPartition(gem_id);

      b_gem_chamber_ = gem_id.chamber();

      b_gem_has_layer1_ = true;
      b_gem_layer1_ieta_ = gem_id.ieta();
      b_gem_layer1_strip_ = static_cast<int>(eta_partition->strip(gem_hit_layer1->localPosition()));
      b_gem_layer1_cls_ = gem_hit_layer1->clusterSize();
      b_gem_layer1_bx_ = gem_hit_layer1->BunchX();
    }

    if (gem_hit_layer2) {
      const GEMDetId&& gem_id = gem_hit_layer2->gemId();
      const GEMEtaPartition* eta_partition = gem->etaPartition(gem_id);

      b_gem_chamber_ = gem_id.chamber();

      b_gem_has_layer2_ = true;
      b_gem_layer2_ieta_ = gem_id.ieta();
      b_gem_layer2_strip_ = static_cast<int>(eta_partition->strip(gem_hit_layer2->localPosition()));
      b_gem_layer2_cls_ = gem_hit_layer2->clusterSize();
      b_gem_layer2_bx_ = gem_hit_layer2->BunchX();
    }

    if (is_matched) {
      const reco::Muon* muon = matched_me11_segment_map.at(key);

      b_is_matched_with_muon_ = is_matched;
      b_muon_pt_ = muon->pt();
      b_muon_eta_ = muon->eta();
      b_muon_phi_ = muon->phi();
      b_muon_charge_ = muon->charge();
    }

    tree_->Fill();

    // std::cout << *segment << std::endl;
    std::cout << (is_matched ? "Matched" : "Unmatched") << " segment: "
              << "# of GEMRecHits = " << gemcsc_segment->gemRecHits().size()
              << " @ "<< gemcsc_segment->cscDetId()
              << std::endl;
    // csc_segment.print();
  }
}
