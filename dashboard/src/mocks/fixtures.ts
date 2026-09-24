import type {
  CandidateMetrics,
  CandidateSummary,
  Capabilities,
  DailyMetric,
  Diagnostics,
  Health,
  Integrity,
  Prediction,
  ResearchStatus,
  RunDetail,
  RunSummary,
} from '@/api/contracts';

/**
 * SYNTHETIC mock fixtures — development/testing only.
 *
 * Every value here is invented and clearly labelled as synthetic.
 * These are NOT real research results and must never be mixed with real
 * D0-D3 numbers. The UI marks all of this with a global MOCK DATA banner.
 */

const SIGNAL_DATES = ['2025-02-10', '2025-02-11', '2025-02-12'] as const;

export const MOCK_RUN_ID = 'MOCK-RUN-SYNTHETIC-001';

export const mockHealth: Health = {
  status: 'ok',
  readOnly: true,
  sourceOfTruth: 'MOCK_SYNTHETIC_FIXTURES',
};

export const mockCapabilities: Capabilities = {
  readOnly: true,
  mutations: false,
  candidateComparison: true,
  developmentExplorer: true,
  sectorExplorer: true,
  diagnostics: true,
  portfolio: false,
  execution: false,
  etf: false,
  validationAvailable: false,
  finalOosAvailable: false,
};

export const mockResearchStatus: ResearchStatus = {
  researchLabel: 'MOCK_SYNTHETIC_RESEARCH_LABEL',
  phase: 'DEVELOPMENT',
  validation: 'SEALED',
  finalOos: 'SEALED',
  executable: false,
  tradable: false,
  strictPit: false,
  classificationAdmission: 'MOCK_FIXED_CLASSIFICATION',
  etf: 'DISABLED',
  syntheticPortfolio: 'DISABLED',
  levelB: 'DISABLED',
  sourceOfTruth: 'MOCK_SYNTHETIC_FIXTURES',
};

export const mockRunSummaries: RunSummary[] = [
  {
    runId: MOCK_RUN_ID,
    phase: 'DEVELOPMENT',
    iteration: 1,
    candidateIds: ['D0', 'D1', 'D2', 'D3'],
    researchLabel: 'MOCK_SYNTHETIC_RESEARCH_LABEL',
    gitCommit: '0000000000000000000000000000000000000000',
    protocolHash: 'mock-protocol-hash-synthetic-00000000000000000000000000000000',
    sectorSnapshotId: 'MOCK_SNAPSHOT_SYNTHETIC',
  },
];

export const mockRunDetail: RunDetail = {
  ...mockRunSummaries[0]!,
  executable: false,
  strictPit: false,
  classificationAdmission: 'MOCK_FIXED_CLASSIFICATION',
  splitPolicyHash: 'mock-split-policy-hash-synthetic-0000000000000000000000',
  predictionConfigHash: 'mock-prediction-config-hash-synthetic-000000000000000000',
  developmentIteration1ProtocolHash:
    'mock-dev-iteration1-protocol-hash-synthetic-0000000000000000',
  syntheticPortfolioConfigHash: 'mock-synthetic-portfolio-config-hash-synthetic-00000000',
  validation: 'SEALED',
  finalOos: 'SEALED',
};

export const mockCandidates: CandidateSummary[] = [
  {
    candidateId: 'D0',
    xPreprocessing: 'NONE',
    trainingTarget: 'ABSOLUTE_FORWARD_RETURN',
    weightedRankIc: 0.0123,
    weightedSpread: 0.0456,
    promotionStatus: 'DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW',
  },
  {
    candidateId: 'D1',
    xPreprocessing: 'TRAIN_ONLY_STANDARDIZATION',
    trainingTarget: 'ABSOLUTE_FORWARD_RETURN',
    weightedRankIc: -0.0234,
    weightedSpread: -0.0101,
    promotionStatus: 'NOT_PROMOTED',
  },
  {
    candidateId: 'D2',
    xPreprocessing: 'NONE',
    trainingTarget: 'CROSS_SECTIONAL_EXCESS_FORWARD_RETURN',
    weightedRankIc: 0.0345,
    weightedSpread: null,
    promotionStatus: 'DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW',
  },
  {
    candidateId: 'D3',
    xPreprocessing: 'TRAIN_ONLY_STANDARDIZATION',
    trainingTarget: 'CROSS_SECTIONAL_EXCESS_FORWARD_RETURN',
    weightedRankIc: null,
    weightedSpread: 0.0202,
    promotionStatus: null,
  },
];

function syntheticStats(base: number, validDates: number) {
  return {
    validDates,
    mean: base,
    median: base * 0.9,
    std: Math.abs(base) / 2,
    min: base - 0.05,
    max: base + 0.05,
  };
}

export const mockCandidateMetrics: Record<string, CandidateMetrics> = {
  D0: {
    candidateId: 'D0',
    weightedRankIc: 0.0123,
    weightedSpread: 0.0456,
    horizons: [
      {
        horizon: 10,
        ic: syntheticStats(0.0101, 3),
        rankIc: syntheticStats(0.0111, 3),
        top5ForwardReturn: syntheticStats(0.0121, 3),
        universeForwardReturn: syntheticStats(0.0061, 3),
        top5MinusUniverse: syntheticStats(0.0051, 3),
      },
      {
        horizon: 40,
        ic: syntheticStats(0.0102, 3),
        rankIc: syntheticStats(0.0112, 3),
        top5ForwardReturn: syntheticStats(0.0122, 3),
        universeForwardReturn: syntheticStats(0.0062, 3),
        top5MinusUniverse: syntheticStats(0.0052, 3),
      },
      {
        horizon: 120,
        ic: syntheticStats(0.0103, 3),
        rankIc: syntheticStats(0.0113, 3),
        top5ForwardReturn: syntheticStats(0.0123, 3),
        universeForwardReturn: syntheticStats(0.0063, 3),
        top5MinusUniverse: syntheticStats(0.0053, 3),
      },
    ],
  },
  D1: {
    candidateId: 'D1',
    weightedRankIc: -0.0234,
    weightedSpread: -0.0101,
    horizons: [
      {
        horizon: 10,
        ic: syntheticStats(-0.0201, 3),
        rankIc: syntheticStats(-0.0211, 3),
        top5ForwardReturn: syntheticStats(-0.0221, 3),
        universeForwardReturn: syntheticStats(-0.0111, 3),
        top5MinusUniverse: syntheticStats(-0.0091, 3),
      },
      {
        horizon: 40,
        ic: syntheticStats(-0.0202, 3),
        rankIc: syntheticStats(-0.0212, 3),
        top5ForwardReturn: syntheticStats(-0.0222, 3),
        universeForwardReturn: syntheticStats(-0.0112, 3),
        top5MinusUniverse: syntheticStats(-0.0092, 3),
      },
      {
        horizon: 120,
        ic: syntheticStats(-0.0203, 3),
        rankIc: syntheticStats(-0.0213, 3),
        top5ForwardReturn: syntheticStats(-0.0223, 3),
        universeForwardReturn: syntheticStats(-0.0113, 3),
        top5MinusUniverse: syntheticStats(-0.0093, 3),
      },
    ],
  },
  D2: {
    candidateId: 'D2',
    weightedRankIc: 0.0345,
    weightedSpread: null,
    horizons: [
      {
        horizon: 10,
        ic: syntheticStats(0.0301, 3),
        rankIc: syntheticStats(0.0311, 3),
        top5ForwardReturn: syntheticStats(0.0321, 3),
        universeForwardReturn: syntheticStats(0.0161, 3),
        top5MinusUniverse: syntheticStats(0.0141, 3),
      },
      {
        horizon: 40,
        ic: syntheticStats(0.0302, 3),
        rankIc: syntheticStats(0.0312, 3),
        top5ForwardReturn: syntheticStats(0.0322, 3),
        universeForwardReturn: syntheticStats(0.0162, 3),
        top5MinusUniverse: syntheticStats(0.0142, 3),
      },
      {
        horizon: 120,
        ic: syntheticStats(0.0303, 3),
        rankIc: syntheticStats(0.0313, 3),
        top5ForwardReturn: syntheticStats(0.0323, 3),
        universeForwardReturn: syntheticStats(0.0163, 3),
        top5MinusUniverse: syntheticStats(0.0143, 3),
      },
    ],
  },
  D3: {
    candidateId: 'D3',
    weightedRankIc: null,
    weightedSpread: 0.0202,
    horizons: [
      {
        horizon: 10,
        ic: syntheticStats(0.0001, 2),
        rankIc: syntheticStats(0.0002, 2),
        top5ForwardReturn: syntheticStats(0.0003, 2),
        universeForwardReturn: syntheticStats(0.0004, 2),
        top5MinusUniverse: syntheticStats(0.0005, 2),
      },
      {
        horizon: 40,
        ic: { validDates: 2, mean: null, median: null, std: null, min: null, max: null },
        rankIc: syntheticStats(0.0012, 2),
        top5ForwardReturn: syntheticStats(0.0013, 2),
        universeForwardReturn: syntheticStats(0.0014, 2),
        top5MinusUniverse: syntheticStats(0.0015, 2),
      },
      {
        horizon: 120,
        ic: syntheticStats(0.0021, 1),
        rankIc: { validDates: 1, mean: null, median: null, std: null, min: null, max: null },
        top5ForwardReturn: syntheticStats(0.0023, 1),
        universeForwardReturn: syntheticStats(0.0024, 1),
        top5MinusUniverse: syntheticStats(0.0025, 1),
      },
    ],
  },
};

function syntheticDaily(candidateId: string, horizon: 10 | 40 | 120): DailyMetric[] {
  const seed = { D0: 0.01, D1: -0.02, D2: 0.03, D3: 0.004 }[candidateId] ?? 0;
  return SIGNAL_DATES.map((date, index) => {
    const factor = seed * (index + 1) + horizon / 10_000;
    // Deliberately round, obviously synthetic values; one null to exercise gaps.
    const mid = Math.round(factor * 10_000) / 10_000;
    return {
      ordinal: `E00${index + 1}`,
      signalDate: date,
      horizon,
      ic: index === 2 && candidateId === 'D3' ? null : mid + 0.001,
      rankIc: mid + 0.002,
      top5ForwardReturn: mid + 0.003,
      universeForwardReturn: mid + 0.004,
      top5MinusUniverse: mid + 0.005,
    } satisfies DailyMetric;
  });
}

export function mockDailyMetrics(candidateId: string, horizon?: 10 | 40 | 120): DailyMetric[] {
  const horizons: Array<10 | 40 | 120> = horizon ? [horizon] : [10, 40, 120];
  return horizons.flatMap((h) => syntheticDaily(candidateId, h));
}

const MOCK_SECTOR_CODES = [
  '801771',
  '801772',
  '801773',
  '801774',
  '801775',
  '801776',
  '801777',
  '801778',
  '801779',
  '801780',
];

function syntheticPredictions(date: string): Prediction[] {
  const dateIndex = SIGNAL_DATES.indexOf(date as (typeof SIGNAL_DATES)[number]);
  const ordinal = `E00${dateIndex >= 0 ? dateIndex + 1 : 1}`;
  return MOCK_SECTOR_CODES.map((code, index) => {
    const rank = index + 1;
    const base = 0.1 - index * 0.01;
    return {
      ordinal,
      signalDate: date,
      sectorCode: code,
      // Two rows intentionally have no name (UI must fall back to sectorCode).
      sectorName: index === 3 || index === 8 ? null : `SYNTHETIC SECTOR ${String.fromCharCode(65 + index)}`,
      pred10: Math.round((base + 0.01) * 10_000) / 10_000,
      pred40: index === 5 ? null : Math.round((base + 0.02) * 10_000) / 10_000,
      pred120: Math.round((base + 0.03) * 10_000) / 10_000,
      fusedScore: Math.round(base * 10_000) / 10_000,
      fusedRank: rank,
      top5: rank <= 5,
      realizedForwardReturn10: Math.round((base - 0.005) * 10_000) / 10_000,
      realizedForwardReturn40: Math.round((base - 0.01) * 10_000) / 10_000,
      realizedForwardReturn120: index === 9 ? null : Math.round((base - 0.02) * 10_000) / 10_000,
      labelEnd10: '2025-02-25',
      labelEnd40: '2025-04-11',
      labelEnd120: index === 9 ? null : '2025-08-11',
    } satisfies Prediction;
  });
}

export function mockPredictionRows(date: string): Prediction[] {
  return syntheticPredictions(date);
}

export const mockPredictionDates: string[] = [...SIGNAL_DATES];

export function mockDiagnostics(): Diagnostics {
  return {
    attemptedDates: 3,
    successfulDates: 2,
    skippedDates: 1,
    horizons: [
      {
        horizon: 10,
        trainingObservations: 320,
        validTrainingDates: 3,
        validSectorCounts: 10,
        missingFactorExclusions: 1,
        missingLabelExclusions: 2,
        numericalFailures: 0,
        insufficientTrainingCases: 0,
        zeroStdFeatureOccurrences: 0,
        scalerDiagnosticHash: 'mock-scaler-diag-10-synthetic-0000000000000000000',
        demeanResidualMaxAbsMean: 0.0001,
        targetDiagnosticHash: 'mock-target-diag-10-synthetic-000000000000000000000',
      },
      {
        horizon: 40,
        trainingObservations: 310,
        validTrainingDates: 3,
        validSectorCounts: 10,
        missingFactorExclusions: 1,
        missingLabelExclusions: 3,
        numericalFailures: 1,
        insufficientTrainingCases: 0,
        zeroStdFeatureOccurrences: 2,
        scalerDiagnosticHash: 'mock-scaler-diag-40-synthetic-0000000000000000000',
        demeanResidualMaxAbsMean: 0.0002,
        targetDiagnosticHash: 'mock-target-diag-40-synthetic-000000000000000000000',
      },
      {
        horizon: 120,
        trainingObservations: null,
        validTrainingDates: 1,
        validSectorCounts: 8,
        missingFactorExclusions: 2,
        missingLabelExclusions: null,
        numericalFailures: 0,
        insufficientTrainingCases: 1,
        zeroStdFeatureOccurrences: null,
        scalerDiagnosticHash: null,
        demeanResidualMaxAbsMean: null,
        targetDiagnosticHash: 'mock-target-diag-120-synthetic-0000000000000000000',
      },
    ],
  };
}

export const mockIntegrity: Integrity = {
  researchLabel: 'MOCK_SYNTHETIC_RESEARCH_LABEL',
  phase: 'DEVELOPMENT',
  validation: 'SEALED',
  finalOos: 'SEALED',
  universe: 'SYNTHETIC MOCK UNIVERSE',
  sectorCount: 10,
  featureCount: 6,
  alpha: 0.05,
  horizons: [10, 40, 120],
  fusion: [0.3, 0.4, 0.3],
  topK: 5,
  splitPolicyHash: 'mock-split-policy-hash-synthetic-0000000000000000000000',
  predictionConfigHash: 'mock-prediction-config-hash-synthetic-000000000000000000',
  developmentIteration1ProtocolHash:
    'mock-dev-iteration1-protocol-hash-synthetic-0000000000000000',
  sectorSnapshotId: 'MOCK_SNAPSHOT_SYNTHETIC',
  executable: false,
  strictPit: false,
  etf: 'DISABLED',
  syntheticPortfolio: 'DISABLED',
  levelB: 'DISABLED',
};
