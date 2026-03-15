import { useState, useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import { useData } from '../contexts/DataContext'
import { KpiCard, KpiGrid, IntroBox, Badge, TableContainer, DataTable } from '../components/shared'
import { chartColors, defaultScaleOptions, defaultPluginOptions } from '../lib/chartDefaults'
import { ETF_LIST, ETF_SHORT_NAMES } from '../lib/constants'
import '../lib/chartDefaults'
import type { EtfPageData, DateRecord } from '../types'

function getLatestRecord(etfData: EtfPageData): DateRecord | null {
  const records = etfData.date_records
  if (!Array.isArray(records) || records.length === 0) return null
  return records[records.length - 1] ?? null
}

function getRecordByDate(etfData: EtfPageData, date: string): DateRecord | null {
  const records = etfData.date_records
  if (!Array.isArray(records)) return null
  return records.find(r => r.date === date) ?? null
}

export function P4EtfHistoryComparison() {
  const { etfPages } = useData()
  const [currentETF, setCurrentETF] = useState<string>('00981A')
  const [compareDate1, setCompareDate1] = useState('')
  const [compareDate2, setCompareDate2] = useState('')
  const [compareResult, setCompareResult] = useState<{
    newStocks: Array<{ code: string; name: string; weight: number }>
    exitedStocks: Array<{ code: string; name: string; prevWeight: number }>
    changedStocks: Array<{ code: string; name: string; w1: number; w2: number; delta: number }>
    cashDelta: number
    holdingsDelta: number
    cash1: number
    cash2: number
    n1: number
    n2: number
  } | null>(null)

  const etfData = etfPages?.[currentETF]
  const latest = etfData ? getLatestRecord(etfData) : null
  const dates = etfData?.dates || []

  // Initialize compare dates
  useMemo(() => {
    if (dates.length > 1) {
      setCompareDate1(dates[dates.length - 2])
      setCompareDate2(dates[dates.length - 1])
    }
  }, [dates])

  // KPIs
  const nHoldings = latest?.n_stocks || 0
  const cashPct = latest?.cash_pct || 0
  const latestDate = dates[dates.length - 1] || '-'
  const top5Weight = useMemo(() => {
    const h = latest?.holdings || []
    return h.slice(0, 5).reduce((sum, item) => sum + (item.weight || 0), 0)
  }, [latest])

  // Cash vs Index chart
  const cashChartData = useMemo(() => {
    if (!etfData?.cash_series) return null
    const last30 = etfData.cash_series.slice(-30)
    return {
      labels: last30.map(d => d.date),
      datasets: [
        {
          label: '現金比例',
          data: last30.map(d => d.cash_pct),
          borderColor: chartColors.accent,
          backgroundColor: 'rgba(79, 142, 247, 0.1)',
          borderWidth: 2, tension: 0.3, pointRadius: 0, fill: true, yAxisID: 'y',
        },
      ],
    }
  }, [etfData])

  // Holdings trend chart
  const holdingsTrendData = useMemo(() => {
    if (!etfData || dates.length < 2) return null
    const last30Dates = dates.slice(-30)
    return {
      labels: last30Dates,
      datasets: [{
        label: '持股數',
        data: last30Dates.map(d => {
          const r = getRecordByDate(etfData, d)
          return r?.n_stocks || 0
        }),
        borderColor: chartColors.purple,
        backgroundColor: 'rgba(168, 85, 247, 0.1)',
        borderWidth: 2, tension: 0.3, pointRadius: 0, fill: true,
      }],
    }
  }, [etfData, dates])

  // Holdings table
  const holdingColumns = [
    { key: 'code', label: '代碼' },
    { key: 'name', label: '名稱' },
    {
      key: 'weight', label: '權重 (%)', align: 'right' as const,
      render: (h: { weight: number }) => {
        const maxW = Math.max(...(latest?.holdings || []).map(x => x.weight || 0), 1)
        const pct = Math.min(100, (h.weight / maxW) * 100)
        const color = h.weight >= 5 ? 'bg-accent' : h.weight >= 2 ? 'bg-cyan' : 'bg-text-muted'
        return (
          <div className="flex items-center gap-2 justify-end">
            <span>{h.weight.toFixed(2)}%</span>
            <div className="w-20 h-1.5 bg-border rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        )
      },
      sortValue: (h: { weight: number }) => h.weight,
    },
  ]

  // Changes timeline
  const changesTimeline = useMemo(() => {
    if (!etfData || dates.length < 2) return []
    const timeline: Array<{ date: string; tags: Array<{ text: string; variant: 'green' | 'red' | 'blue' | 'orange' }> }> = []

    for (let i = dates.length - 1; i >= 1 && i >= dates.length - 10; i--) {
      const curr = getRecordByDate(etfData, dates[i])
      const prev = getRecordByDate(etfData, dates[i - 1])
      if (!curr || !prev) continue

      const currMap = Object.fromEntries((curr.holdings || []).map(h => [h.code, h]))
      const prevMap = Object.fromEntries((prev.holdings || []).map(h => [h.code, h]))
      const currCodes = new Set(Object.keys(currMap))
      const prevCodes = new Set(Object.keys(prevMap))

      const tags: typeof timeline[0]['tags'] = []
      ;[...currCodes].filter(c => !prevCodes.has(c)).forEach(c => tags.push({ text: `+${currMap[c]?.name || c}`, variant: 'green' }))
      ;[...prevCodes].filter(c => !currCodes.has(c)).forEach(c => tags.push({ text: `-${prevMap[c]?.name || c}`, variant: 'red' }))
      ;[...currCodes].filter(c => prevCodes.has(c) && (currMap[c].weight - prevMap[c].weight) > 0.3).forEach(c =>
        tags.push({ text: `\u2191${currMap[c].name} +${(currMap[c].weight - prevMap[c].weight).toFixed(1)}%`, variant: 'blue' })
      )
      ;[...currCodes].filter(c => prevCodes.has(c) && (currMap[c].weight - prevMap[c].weight) < -0.3).forEach(c =>
        tags.push({ text: `\u2193${currMap[c].name} ${(currMap[c].weight - prevMap[c].weight).toFixed(1)}%`, variant: 'orange' })
      )

      if (tags.length) timeline.push({ date: dates[i], tags })
    }
    return timeline
  }, [etfData, dates])

  function doCompare() {
    if (!etfData || !compareDate1 || !compareDate2) return
    const r1 = getRecordByDate(etfData, compareDate1)
    const r2 = getRecordByDate(etfData, compareDate2)
    if (!r1 || !r2) return

    const map1 = Object.fromEntries((r1.holdings || []).map(h => [h.code, h]))
    const map2 = Object.fromEntries((r2.holdings || []).map(h => [h.code, h]))
    const codes1 = new Set(Object.keys(map1))
    const codes2 = new Set(Object.keys(map2))

    const newStocks = [...codes2].filter(c => !codes1.has(c)).map(c => ({ code: c, name: map2[c].name, weight: map2[c].weight }))
    const exitedStocks = [...codes1].filter(c => !codes2.has(c)).map(c => ({ code: c, name: map1[c].name, prevWeight: map1[c].weight }))
    const changedStocks = [...codes2].filter(c => codes1.has(c) && Math.abs(map2[c].weight - map1[c].weight) > 0.01)
      .map(c => ({ code: c, name: map2[c].name, w1: map1[c].weight, w2: map2[c].weight, delta: map2[c].weight - map1[c].weight }))
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))

    setCompareResult({
      newStocks, exitedStocks, changedStocks,
      cashDelta: (r2.cash_pct || 0) - (r1.cash_pct || 0),
      holdingsDelta: (r2.n_stocks || 0) - (r1.n_stocks || 0),
      cash1: r1.cash_pct || 0, cash2: r2.cash_pct || 0,
      n1: r1.n_stocks || 0, n2: r2.n_stocks || 0,
    })
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-text-primary">ETF 歷史回溯與對比</h2>

      <IntroBox variant="accent">
        選擇 ETF 查看歷史持股、現金水位變化，並使用對比工具分析任意兩個日期間的持股變動。
      </IntroBox>

      {/* ETF Tabs */}
      <div className="flex gap-2 flex-wrap">
        {ETF_LIST.map(etf => (
          <button
            key={etf}
            onClick={() => { setCurrentETF(etf); setCompareResult(null) }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              currentETF === etf
                ? 'bg-accent text-white border-accent'
                : 'bg-card text-text-muted border-border hover:bg-card-hover'
            }`}
          >
            {etf} {ETF_SHORT_NAMES[etf] && <span className="text-xs opacity-70">({ETF_SHORT_NAMES[etf]})</span>}
          </button>
        ))}
      </div>

      <KpiGrid>
        <KpiCard label="持股數" value={nHoldings} valueColor={nHoldings >= 40 ? 'text-down' : nHoldings >= 20 ? 'text-accent' : 'text-warning'} />
        <KpiCard label="現金水位" value={`${cashPct.toFixed(1)}%`} valueColor={cashPct >= 5 ? 'text-up' : cashPct >= 3 ? 'text-warning' : 'text-down'} />
        <KpiCard label="最新日期" value={latestDate} />
        <KpiCard label="持股集中度 (Top 5)" value={`${top5Weight.toFixed(1)}%`} valueColor={top5Weight >= 40 ? 'text-up' : top5Weight >= 30 ? 'text-warning' : 'text-down'} />
      </KpiGrid>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <TableContainer title="現金權重趨勢">
          <div className="h-56">
            {cashChartData && (
              <Line data={cashChartData} options={{
                responsive: true, maintainAspectRatio: false,
                plugins: defaultPluginOptions,
                scales: { y: { ...defaultScaleOptions, title: { display: true, text: '現金比例 (%)', color: chartColors.textMuted } }, x: defaultScaleOptions },
              }} />
            )}
          </div>
        </TableContainer>

        <TableContainer title="持股數量變化">
          <div className="h-56">
            {holdingsTrendData && (
              <Line data={holdingsTrendData} options={{
                responsive: true, maintainAspectRatio: false,
                plugins: defaultPluginOptions,
                scales: { y: defaultScaleOptions, x: defaultScaleOptions },
              }} />
            )}
          </div>
        </TableContainer>
      </div>

      {/* Holdings Table */}
      <TableContainer title="完整持股明細">
        <DataTable columns={holdingColumns} data={latest?.holdings || []} emptyText="無數據" />
      </TableContainer>

      {/* Changes Timeline */}
      <TableContainer title="近期異動紀錄" maxHeight="350px">
        {changesTimeline.length === 0 ? (
          <div className="py-4 text-text-muted text-center">近期無重大異動</div>
        ) : (
          changesTimeline.map(({ date, tags }) => (
            <div key={date} className="flex gap-3 items-start py-3 border-b border-border last:border-b-0">
              <span className="text-sm text-text-muted w-20 shrink-0">{date}</span>
              <div className="flex flex-wrap gap-1.5">
                {tags.map((t, i) => <Badge key={i} variant={t.variant}>{t.text}</Badge>)}
              </div>
            </div>
          ))
        )}
      </TableContainer>

      {/* Comparison Tool */}
      <TableContainer title="對比分析工具">
        <div className="flex flex-wrap gap-4 items-end mb-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">基準日（較早）</label>
            <select
              value={compareDate1}
              onChange={e => setCompareDate1(e.target.value)}
              className="bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
            >
              {[...dates].reverse().map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">對比日（較晚）</label>
            <select
              value={compareDate2}
              onChange={e => setCompareDate2(e.target.value)}
              className="bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
            >
              {[...dates].reverse().map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <button onClick={doCompare} className="px-4 py-1.5 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90">
            比較
          </button>
        </div>

        {compareResult && (
          <div className="space-y-4">
            <KpiGrid>
              <KpiCard
                label="現金水位變化"
                value={`${compareResult.cashDelta >= 0 ? '+' : ''}${compareResult.cashDelta.toFixed(1)}%`}
                valueColor={compareResult.cashDelta > 0 ? 'text-up' : compareResult.cashDelta < 0 ? 'text-down' : 'text-text-muted'}
                subtext={`${compareResult.cash1.toFixed(1)}% → ${compareResult.cash2.toFixed(1)}%`}
              />
              <KpiCard
                label="持股數變化"
                value={`${compareResult.holdingsDelta >= 0 ? '+' : ''}${compareResult.holdingsDelta}`}
                valueColor={compareResult.holdingsDelta > 0 ? 'text-down' : compareResult.holdingsDelta < 0 ? 'text-up' : 'text-text-muted'}
                subtext={`${compareResult.n1} → ${compareResult.n2}`}
              />
            </KpiGrid>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className="text-sm font-semibold text-down mb-2">新增持股</div>
                <DataTable
                  columns={[
                    { key: 'code', label: '代碼' },
                    { key: 'name', label: '名稱' },
                    { key: 'weight', label: '權重', align: 'right' as const, render: (s: { weight: number }) => `${s.weight.toFixed(2)}%` },
                  ]}
                  data={compareResult.newStocks}
                  emptyText="無"
                />
              </div>
              <div>
                <div className="text-sm font-semibold text-up mb-2">退出持股</div>
                <DataTable
                  columns={[
                    { key: 'code', label: '代碼' },
                    { key: 'name', label: '名稱' },
                    { key: 'prevWeight', label: '原權重', align: 'right' as const, render: (s: { prevWeight: number }) => `${s.prevWeight.toFixed(2)}%` },
                  ]}
                  data={compareResult.exitedStocks}
                  emptyText="無"
                />
              </div>
              <div>
                <div className="text-sm font-semibold text-accent mb-2">權重變化</div>
                <DataTable
                  columns={[
                    { key: 'code', label: '代碼' },
                    { key: 'name', label: '名稱' },
                    {
                      key: 'delta', label: '變化', align: 'right' as const,
                      render: (s: { delta: number }) => (
                        <span className={s.delta > 0 ? 'text-up' : 'text-down'}>{s.delta > 0 ? '+' : ''}{s.delta.toFixed(2)}%</span>
                      ),
                    },
                  ]}
                  data={compareResult.changedStocks}
                  emptyText="無"
                />
              </div>
            </div>
          </div>
        )}
      </TableContainer>
    </div>
  )
}
