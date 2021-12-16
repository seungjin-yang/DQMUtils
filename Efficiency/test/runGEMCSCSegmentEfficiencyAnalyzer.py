# Auto generated configuration file
# using:
# Revision: 1.19
# Source: /local/reps/CMSSW/CMSSW/Configuration/Applications/python/ConfigBuilder.py,v
# with command line options: step3 --conditions auto:phase1_2021_realistic --datatier GEN-SIM-RECO --era Run3 --eventcontent RECOSIM --filein file:step2.root --fileout file:step3.root --geometry DB:Extended --no_exec --number -1 --step RAW2DIGI,L1Reco,RECO,RECOSIM,EI,PAT
import FWCore.ParameterSet.Config as cms

from Configuration.Eras.Era_Run3_cff import Run3

process = cms.Process('ANALYSIS',Run3)

# import of standard configurations
process.load('Configuration.StandardSequences.Services_cff')
process.load('SimGeneral.HepPDTESSource.pythiapdt_cfi')
process.load('FWCore.MessageService.MessageLogger_cfi')
process.load('Configuration.EventContent.EventContent_cff')
process.load('Configuration.StandardSequences.GeometryRecoDB_cff')
process.load('Configuration.StandardSequences.MagneticField_cff')
process.load('Configuration.StandardSequences.EndOfProcess_cff')
process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')

from FWCore.ParameterSet.VarParsing import VarParsing
options = VarParsing('analysis')
options.parseArguments()

process.maxEvents = cms.untracked.PSet(
    input = cms.untracked.int32(options.maxEvents),
    output = cms.optional.untracked.allowed(cms.int32,cms.PSet)
)

# Input source
process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(options.inputFiles),
    secondaryFileNames = cms.untracked.vstring()
)

# Output definition

# Additional output definition
process.TFileService = cms.Service("TFileService",
    fileName = cms.string(options.outputFile)
)


# Other statements
from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, 'auto:phase1_2021_realistic', '')

process.load('RecoLocalMuon.GEMCSCSegment.gemcscSegments_cfi')
process.gemcscSegments_step    = cms.Path(process.gemcscSegments)

# Path and EndPath definitions
process.load("GEMDQMUtils.Efficiency.GEMCSCSegmentEfficiencyAnalyzer_cfi")
process.p = cms.Path(process.GEMCSCSegmentEfficiencyAnalyzer)
