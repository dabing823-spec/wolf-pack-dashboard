import { useData } from '../contexts/DataContext'
import { Badge, TableContainer, DataTable } from '../components/shared'
import { formatPct } from '../lib/formatters'
import { RISK_LEVEL_COLORS } from '../lib/constants'
import type { MarketIndices, ConsensusItem } from '../types'

/* ── helpers ─────────────────────────────────────────── */

function Chg({ val, suffix = '' }: { val?: number; suffix?: string }) {
  if (val == null) return <span className="text-text-muted">-</span>
  const c = val > 0 ? 'text-up' : val < 0 ? 'text-down' : 'text-text-muted'
  return <span className={`${c} tabular-nums`}>{val > 0 ? '+' : ''}{val.toFixed(2)}{suffix}</span>
}

/* ── Compact Ticker Strip ────────────────────────────── */

function TickerItem({ label, value, chgPct }: { label: string; value?: number; chgPct?: number }) {
  const c = (chgPct ?? 0) > 0 ? 'text-up' : (chgPct ?? 0) < 0 ? 'text-down' : 'text-text-muted'
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 min-w-0">
      <span className="text-[10px] text-text-muted uppercase tracking-wider shrink-0">{label}</span>
      <span className={`text-sm font-bold tabular-nums ${c}`}>
        {value != null ? value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '-'}
      </span>
      <Chg val={chgPct} suffix="%" />
    </div>
  )
}

function MarketTicker({ mi }: { mi: MarketIndices }) {
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden mb-3">
      <div className="flex items-center divide-x divide-border overflow-x-auto scrollbar-hide">
        <TickerItem label="TAIEX" value={mi.taiex} chgPct={mi.taiex_chg_pct} />
        <TickerItem label="TPEX" value={mi.tpex} chgPct={mi.tpex_chg_pct} />
        {mi.vix_tw != null && <TickerItem label="VIX TW" value={mi.vix_tw} chgPct={mi.vix_tw_chg_pct} />}
        <TickerItem label="VIX" value={mi.vix} chgPct={mi.vix_chg_pct} />
        <TickerItem label="DXY" value={mi.dxy} chgPct={mi.dxy_chg_pct} />
        <TickerItem label="OIL" value={mi.oil} chgPct={mi.oil_chg_pct} />
        <TickerItem label="GOLD" value={mi.gold} chgPct={mi.gold_chg_pct} />
        <TickerItem label="US10Y" value={mi.us10y} chgPct={mi.us10y_chg_pct} />
        <div className="flex items-center gap-2 px-3 py-1.5">
          <span className="text-[10px] text-text-muted uppercase tracking-wider">F&G</span>
          <span className={`text-sm font-bold tabular-nums ${
            mi.fear_greed < 25 ? 'text-up' : mi.fear_greed < 50 ? 'text-warning' : 'text-down'
          }`}>{mi.fear_greed}</span>
          <span className="text-[10px] text-text-muted">{mi.fear_greed_label}</span>
        </div>
      </div>
    </div>
  )
}

/* ── Risk Score Compact ──────────────────────────────── */

function RiskScoreCompact({ score, maxScore, level, nRed, nYellow, nGreen, signals }: {
  score: number; maxScore: number; level: string; nRed: number; nYellow: number; nGreen: number
  signals: Array<{ name: string; level: string }>
}) {
  const color = RISK_LEVEL_COLORS[level] || RISK_LEVEL_COLORS.green
  const label = level === 'red' ? '高度警戒' : level === 'yellow' ? '中度警戒' : '正常'
  const pct = (score / maxScore) * 100

  return (
    <div className="bg-card border border-border rounded-lg p-3">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-full flex items-center justify-center text-base font-bold border-2 shrink-0"
          style={{ borderColor: color, color }}>
          {score}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold" style={{ color }}>{label}</span>
            <span className="text-[10px] text-text-muted">
              R{nRed} Y{nYellow} G{nGreen}
            </span>
          </div>
          <div className="w-full h-1 bg-border rounded-full mt-1 overflow-hidden">
            <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
          </div>
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {signals.map((s, i) => (
          <span key={i} className="px-1.5 py-0.5 rounded text-[10px] font-medium"
            style={{ backgroundColor: `${RISK_LEVEL_COLORS[s.level]}15`, color: RISK_LEVEL_COLORS[s.level] }}>
            {s.name}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ── Compact KPI Row ─────────────────────────────────── */

function MiniKpi({ label, value, valueColor, sub }: { label: string; value: string | number; valueColor?: string; sub?: string }) {
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2.5">
      <div className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`text-lg font-bold leading-tight ${valueColor || 'text-accent'}`}>{value}</div>
      {sub && <div className="text-[10px] text-text-muted mt-0.5 leading-tight">{sub}</div>}
    </div>
  )
}

/* ── Action List Compact ─────────────────────────────── */

function ActionItem({ type, code, name, value, variant }: {
  type: string; code: string; name: string; value?: string; variant: 'red' | 'blue' | 'orange' | 'green'
}) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-border/30 last:border-b-0 text-xs">
      <Badge variant={variant}>{type}</Badge>
      <span className="text-accent font-mono">{code}</span>
      <span className="text-text-primary">{name}</span>
      {value && <span className="ml-auto tabular-nums">{value}</span>}
    </div>
  )
}

/* ── Main Component ──────────────────────────────────── */

export function P2StrategicDashboard() {
  const { dashboard, strategy } = useData()
  const mi: MarketIndices | undefined = strategy?.market_indices
  const riskSignals = strategy?.risk_signals
  const cashMode = dashboard?.cash_mode
  const consensus = dashboard?.consensus || []
  const dailyChanges = dashboard?.daily_changes?.['00981A'] || []

  const top15 = consensus.slice(0, 15)
  const consensusColumns = [
    { key: 'code', label: '代碼', render: (c: ConsensusItem) => <span className="font-mono text-accent">{c.code}</span> },
    { key: 'name', label: '名稱' },
    {
      key: 'avg_weight', label: '共識%', align: 'right' as const,
      render: (c: ConsensusItem) => `${c.avg_weight?.toFixed(2) ?? '-'}%`,
      sortValue: (c: ConsensusItem) => c.avg_weight || 0,
    },
    {
      key: 'etf_count', label: 'ETF', align: 'right' as const,
      render: (c: ConsensusItem) => (
        <div className="flex items-center justify-end gap-0.5">
          {Array.from({ length: c.etf_count }).map((_, i) => (
            <span key={i} className="w-1.5 h-1.5 rounded-full bg-accent" />
          ))}
        </div>
      ),
      sortValue: (c: ConsensusItem) => c.etf_count,
    },
  ]

  const todayChanges = dailyChanges.length > 0 ? dailyChanges[dailyChanges.length - 1] : null
  const nNew = todayChanges?.new?.length || 0
  const nAdded = todayChanges?.added?.length || 0
  const nReduced = todayChanges?.reduced?.length || 0
  const nRemoved = todayChanges?.removed?.length || 0
  const totalSignals = nNew + nAdded + nReduced + nRemoved

  const cashNow = cashMode?.cash_now ?? 0
  const cashTrend = cashMode?.trend || '-'

  return (
    <div className="space-y-3">
      {/* Market Ticker Strip */}
      {mi && <MarketTicker mi={mi} />}

      {/* 2-column: Risk + KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-3">
        {/* Left: Risk Score */}
        {riskSignals && (
          <RiskScoreCompact
            score={riskSignals.score} maxScore={riskSignals.max_score} level={riskSignals.level}
            nRed={riskSignals.n_red} nYellow={riskSignals.n_yellow} nGreen={riskSignals.n_green}
            signals={riskSignals.signals.map(s => ({ name: s.name, level: s.signal }))}
          />
        )}

        {/* Right: KPI Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <MiniKpi label="現金水位" value={`${cashNow.toFixed(1)}%`}
            valueColor={cashNow >= 5 ? 'text-up' : cashNow >= 3 ? 'text-warning' : 'text-down'}
            sub={cashMode?.mode_desc} />
          <MiniKpi label="攻防模式" value={cashMode?.mode || '-'} sub={`趨勢 ${cashTrend}`} />
          <MiniKpi label="跟單狀態" value={cashNow > 4 ? '加分中' : '一般'}
            valueColor={cashNow > 4 ? 'text-up' : 'text-text-muted'}
            sub={cashNow > 4 ? '現金>4%' : '一般狀態'} />
          <MiniKpi label="今日異動" value={totalSignals}
            sub={`+${nNew} \u25B2${nAdded} \u25BC${nReduced} -${nRemoved}`} />
        </div>
      </div>

      {/* 3-column: Action List + Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Action List */}
        <div className="lg:col-span-2 bg-card border border-border rounded-lg p-3">
          <div className="text-xs font-semibold text-text-primary mb-2 flex items-center gap-2">
            <span className="w-1 h-3 bg-up rounded-full" />
            今日跟單行動清單
          </div>
          {!todayChanges || totalSignals === 0 ? (
            <div className="py-3 text-center text-text-muted text-xs">今日無異動</div>
          ) : (
            <div>
              {todayChanges.new?.map((s, i) => (
                <ActionItem key={`n${i}`} type="新增" code={s.code} name={s.name} value={`${s.weight?.toFixed(2)}%`} variant="red" />
              ))}
              {todayChanges.added?.map((s, i) => (
                <ActionItem key={`a${i}`} type="加碼" code={s.code} name={s.name} value={`+${s.weight_chg?.toFixed(2)}%`} variant="blue" />
              ))}
              {todayChanges.reduced?.map((s, i) => (
                <ActionItem key={`r${i}`} type="減碼" code={s.code} name={s.name} value={`${s.weight_chg?.toFixed(2)}%`} variant="orange" />
              ))}
              {todayChanges.removed?.map((s, i) => (
                <ActionItem key={`x${i}`} type="退出" code={s.code} name={s.name} variant="green" />
              ))}
            </div>
          )}
        </div>

        {/* Gauges Column */}
        <div className="space-y-2">
          {[
            { title: '現金趨勢', value: `${cashNow.toFixed(1)}%`, mode: cashTrend,
              color: cashTrend === '上升' ? '#ff4757' : cashTrend === '下降' ? '#00c48c' : '#9ca0b4' },
            { title: '持股集中度', value: `${(dashboard?.conviction?.[0]?.avg_weight ?? 0).toFixed(1)}%`,
              mode: 'Top 1 權重', color: '#4f8ef7' },
            { title: '經理人動向', value: cashMode?.mode || '-', mode: cashMode?.mode_desc || '-',
              color: cashTrend === '上升' ? '#ff4757' : '#00c48c' },
          ].map(g => (
            <div key={g.title} className="bg-card border border-border rounded-lg px-3 py-2 flex items-center justify-between">
              <div>
                <div className="text-[10px] text-text-muted uppercase">{g.title}</div>
                <div className="text-sm font-bold text-text-primary">{g.value}</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold" style={{ backgroundColor: `${g.color}20`, color: g.color }}>
                {g.mode}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom: Consensus + Signal Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TableContainer title="共識標的 TOP15" maxHeight="320px" className="mb-0">
          <DataTable columns={consensusColumns} data={top15} emptyText="暫無共識標的" />
        </TableContainer>

        <TableContainer title="今日 00981A 異動" maxHeight="320px" className="mb-0">
          {!todayChanges || totalSignals === 0 ? (
            <div className="py-4 text-center text-text-muted text-xs">今日無異動</div>
          ) : (
            <div className="space-y-1.5">
              {todayChanges.new?.map((s, i) => (
                <div key={`sn${i}`} className="flex items-center gap-2 px-2 py-1.5 rounded bg-up/5 text-xs">
                  <Badge variant="red">新增</Badge>
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-text-muted font-mono">{s.code}</span>
                </div>
              ))}
              {todayChanges.added?.map((s, i) => (
                <div key={`sa${i}`} className="flex items-center gap-2 px-2 py-1.5 rounded bg-accent/5 text-xs">
                  <Badge variant="blue">加碼</Badge>
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-up ml-auto tabular-nums">+{s.weight_chg?.toFixed(2)}%</span>
                </div>
              ))}
              {todayChanges.reduced?.map((s, i) => (
                <div key={`sr${i}`} className="flex items-center gap-2 px-2 py-1.5 rounded bg-warning/5 text-xs">
                  <Badge variant="orange">減碼</Badge>
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-down ml-auto tabular-nums">{s.weight_chg?.toFixed(2)}%</span>
                </div>
              ))}
            </div>
          )}
        </TableContainer>
      </div>
    </div>
  )
}
