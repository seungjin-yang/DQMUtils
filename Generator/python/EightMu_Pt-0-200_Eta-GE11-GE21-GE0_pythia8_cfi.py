import FWCore.ParameterSet.Config as cms

# eta coverage
# GE11: (1.55, 2.18)
# GE21: (1.55, 2.45)
# GE0: (2.0, 3.0)

generator = cms.EDFilter("Pythia8PtGun",
    PGunParameters = cms.PSet(
        MaxPt = cms.double(200.0),
        MinPt = cms.double(5),
        ParticleID = cms.vint32(-13, -13, 13, 13),
        AddAntiParticle = cms.bool(True),
        MaxEta = cms.double(3.20),
        MaxPhi = cms.double(3.14159265359),
        MinEta = cms.double(1.35),
        MinPhi = cms.double(-3.14159265359) ## in radians
    ),
    Verbosity = cms.untracked.int32(0), ## set to 1 (or greater)  for printouts
    psethack = cms.string('Eight mu pt 0 to 200 eta 1.35 to 3.20'),
    firstRun = cms.untracked.uint32(1),
    PythiaParameters = cms.PSet(parameterSets = cms.vstring())
)
