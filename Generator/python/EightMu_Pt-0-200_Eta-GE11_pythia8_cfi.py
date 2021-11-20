import FWCore.ParameterSet.Config as cms

# eta coverage
# GE11: (1.55, 2.18)

generator = cms.EDFilter("Pythia8PtGun",
    PGunParameters = cms.PSet(
        MaxPt = cms.double(200.0),
        MinPt = cms.double(5),
        ParticleID = cms.vint32(-13, -13, 13, 13),
        AddAntiParticle = cms.bool(True),
        MaxEta = cms.double(2.38),
        MaxPhi = cms.double(3.14159265359),
        MinEta = cms.double(1.35),
        MinPhi = cms.double(-3.14159265359) ## in radians
    ),
    Verbosity = cms.untracked.int32(0), ## set to 1 (or greater)  for printouts
    psethack = cms.string('Eight mu pt 0 to 200 eta 1p35 to 2p38'),
    firstRun = cms.untracked.uint32(1),
    PythiaParameters = cms.PSet(parameterSets = cms.vstring())
)
