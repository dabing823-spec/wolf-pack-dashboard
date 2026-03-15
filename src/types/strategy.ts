export interface ManagerStyle {
  etf_id: string
  style: string
  turnover: number
  concentration: string
  top5_weight: number
  cash_trend: string
}

export interface ConsensusTrend {
  code: string
  name: string
  direction: string
  strength: number
  etf_count: number
}

export interface VelocityItem {
  code: string
  name: string
  velocity: number
  momentum: string
}

export interface TimingScore {
  accuracy_5d: number
  accuracy_10d: number
  correct_calls: number
  total_calls: number
  recent_calls: Array<{
    date: string
    signal: string
    result: string
    return_5d: number
  }>
}

export interface Recommendation {
  code: string
  name: string
  score: number
  factors?: { consensus: number; conviction: number; velocity: number; cash_mode: number }
  recommendation: string
  current_weight?: number
}

export interface IndustryExposure {
  industry: string
  weight: number
  etf_count: number
  change: number
}

export interface HoldingsOverlap {
  matrix: number[][]
  etf_ids: string[]
  shared_details: Record<string, Array<{ code: string; name: string }>>
}

export interface MarketIndices {
  vix: number
  vix_prev: number
  vix_chg: number
  vix_chg_pct: number
  dxy: number
  dxy_prev: number
  dxy_chg: number
  dxy_chg_pct: number
  oil: number
  oil_prev: number
  oil_chg: number
  oil_chg_pct: number
  gold: number
  gold_prev: number
  gold_chg: number
  gold_chg_pct: number
  us10y: number
  us10y_prev: number
  us10y_chg: number
  us10y_chg_pct: number
  taiex: number
  taiex_prev: number
  taiex_chg: number
  taiex_chg_pct: number
  tpex: number
  tpex_prev: number
  tpex_chg: number
  tpex_chg_pct: number
  fear_greed: number
  fear_greed_label: string
  vix_tw: number
  vix_tw_prev: number
  vix_tw_chg: number
  vix_tw_chg_pct: number
}

export interface RiskSignal {
  name: string
  key: string
  value: number
  slope_20d: number
  signal: string
  desc: string
  theory: string
  accel: number
  phase: string
  phase_label: string
  extremity_pct: number
  reliable: boolean
}

export interface RiskSignals {
  score: number
  max_score: number
  level: string
  n_red: number
  n_yellow: number
  n_green: number
  signals: RiskSignal[]
  history: Array<{ date: string; score: number; level: string }>
  updated_at: string
}

export interface Strategy0050Stock {
  code: string
  name: string
  rank?: number
  market_cap_rank?: number
  current_in_0050?: boolean
  reason?: string
  price?: number | string
  change_pct?: number | string
  volume?: number | string
  turnover?: number | string
  link?: string
}

export interface Strategy0050 {
  potential_in: Strategy0050Stock[]
  potential_out: Strategy0050Stock[]
}

export interface MarketWeightStock {
  code: string
  name: string
  rank: number
  market_cap?: number
  price?: number | string
  change_pct?: number | string
  volume?: number | string
  turnover?: number | string
  link?: string
}

export interface SignalBacktest {
  summary: {
    total_signals: number
    evaluated_signals: number
    win_rate_10d: number
    win_rate_20d: number
    avg_return_10d: number
    avg_return_20d: number
  }
  by_type: Record<string, { count: number; win_rate_10d: number; avg_return_10d: number; win_rate_20d: number; avg_return_20d: number }>
  signals: Array<{
    date: string
    type: string
    code: string
    name: string
    weight_chg?: number
    confidence?: number
    return_10d: number
    return_20d: number
    return_60d?: number
  }>
}

export interface TrumpSignalConfidence {
  signal: string
  confidence: number
  detected_today: boolean
}

export interface TrumpPrediction {
  time: string
  preview: string
  signal_types: string[]
  direction: string
  confidence: number
}

export interface TrumpModel {
  name: string
  win_rate: number
  avg_return: number
  total_trades: number
}

export interface TrumpPlaybookRule {
  label: string
  action: string
  avg_return: number
  up_rate?: number
}

export interface TrumpSignals {
  date: string
  posts_today: number
  signals_today: string[]
  signal_confidence: TrumpSignalConfidence[]
  consensus: string
  overall_hit_rate: number
  total_predictions: number
  latest_post: string
  models: TrumpModel[]
  hedge_rules: TrumpPlaybookRule[]
  position_rules: TrumpPlaybookRule[]
  live_predictions: TrumpPrediction[]
  sp500_recent: unknown[]
  summary_zh: string
}

export interface AgentStatus {
  data_agent: { status: string; updated_at: string }
  validator_agent: { status: string; updated_at: string }
  signal_agent: { status: string; updated_at: string }
  trump_agent: { status: string; updated_at: string }
}

export interface StrategyData {
  report_date: string
  generated_at: string
  manager_styles: Record<string, ManagerStyle>
  consensus_trends: ConsensusTrend[]
  velocity: VelocityItem[]
  timing_score: TimingScore
  recommendations: Recommendation[]
  industry_exposure: IndustryExposure[]
  holdings_overlap: HoldingsOverlap
  market_indices: MarketIndices
  risk_signals: RiskSignals
  strategy_0050: Strategy0050
  market_weight_top150: { stocks: MarketWeightStock[] }
  agent_status: AgentStatus
  signal_backtest: SignalBacktest
  trump_signals: TrumpSignals
}
