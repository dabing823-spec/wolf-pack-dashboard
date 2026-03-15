import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import { useData } from '../contexts/DataContext'
import { KpiCard, KpiGrid, IntroBox, Badge, TableContainer, DataTable, InsightCard } from '../components/shared'
import { chartColors, defaultScaleOptions, defaultPluginOptions } from '../lib/chartDefaults'
import '../lib/chartDefaults'
import type { Recommendation } from '../types'

function actionBadge(score: number): { text: string; color: string } {
  if (score >= 8) return { text: '強力買進', color: 'bg-up text-white' }
  if (score >= 5) return { text: '買進', color: 'bg-warning text-white' }
  return { text: '觀望', color: 'bg-text-muted/70 text-text-primary' }
}

export function P5StrategyAnalysis() {
  const { strategy } = useData()
  const recommendations = strategy?.recommendations || []
  const backtest = strategy?.signal_backtest

  const top10 = recommendations.slice(0, 10)

  const recColumns = [
    { key: 'rank', label: '排名', render: (_: Recommendation, i: number) => i + 1 },
    { key: 'code', label: '代碼' },
    { key: 'name', label: '名稱' },
    {
      key: 'current_weight', label: '權重',
      render: (r: Recommendation) => r.current_weight != null ? `${r.current_weight.toFixed(2)}%` : '-',
    },
    {
      key: 'score', label: '評分',
      render: (r: Recommendation) => <span className="font-bold text-accent">{r.score ?? '-'}</span>,
      sortValue: (r: Recommendation) => r.score ?? 0,
    },
    {
      key: 'recommendation', label: '建議',
      render: (r: Recommendation) => {
        const b = actionBadge(r.score ?? 0)
        return <span className={`px-2 py-0.5 rounded text-xs font-bold ${b.color}`}>{r.recommendation || b.text}</span>
      },
    },
  ]

  // Backtest bar chart data
  const backtestBarData = useMemo(() => {
    if (!backtest?.by_type) return null
    const types = Object.keys(backtest.by_type)
    return {
      labels: types,
      datasets: [{
        label: '10日勝率 (%)',
        data: types.map(t => backtest.by_type[t]?.win_rate_10d ?? 0),
        backgroundColor: types.map(t => {
          const wr = backtest.by_type[t]?.win_rate_10d ?? 0
          return wr >= 65 ? chartColors.green : wr >= 55 ? chartColors.accent : chartColors.textMuted
        }),
        borderRadius: 4,
      }],
    }
  }, [backtest])

  const backtestSignals = backtest?.signals || []
  const backtestSignalColumns = [
    { key: 'date', label: '日期' },
    { key: 'code', label: '代碼' },
    { key: 'name', label: '名稱' },
    {
      key: 'type', label: '類型',
      render: (s: { type: string }) => <Badge variant={s.type === '新增' ? 'red' : 'blue'}>{s.type}</Badge>,
    },
    {
      key: 'return_10d', label: '10日報酬', align: 'right' as const,
      render: (s: { return_10d?: number }) => {
        const v = s.return_10d
        if (v == null) return '-'
        const color = v > 0 ? 'text-up' : v < 0 ? 'text-down' : ''
        return <span className={color}>{v > 0 ? '+' : ''}{v.toFixed(2)}%</span>
      },
    },
    {
      key: 'return_20d', label: '20日報酬', align: 'right' as const,
      render: (s: { return_20d?: number }) => {
        const v = s.return_20d
        if (v == null) return '-'
        const color = v > 0 ? 'text-up' : v < 0 ? 'text-down' : ''
        return <span className={color}>{v > 0 ? '+' : ''}{v.toFixed(2)}%</span>
      },
    },
  ]

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-text-primary">策略分析 & 回測</h2>

      <IntroBox>
        綜合評分操作建議與信號回測績效。操作建議基於權重、動能、共識等多因子評分；回測驗證過去信號的實際報酬表現。
      </IntroBox>

      {/* Section 1: Recommendations */}
      <TableContainer title="操作建議 TOP10">
        <details className="mb-3 text-sm">
          <summary className="cursor-pointer text-accent font-medium">這個排行怎麼選出來的？</summary>
          <div className="mt-2 p-3 bg-accent/5 rounded-lg text-text-muted leading-relaxed">
            從 5 檔主動式 ETF 的持股中，用 <strong className="text-text-primary">4 個因子加總評分</strong>，分數越高越值得關注：
            <div className="grid grid-cols-2 gap-2 mt-2 mb-2">
              <div><span className="text-accent font-semibold">共識 (0~5分)</span> 幾檔 ETF 同時持有</div>
              <div><span className="text-purple font-semibold">信念 (0~3分)</span> 連續加碼天數</div>
              <div><span className="text-down font-semibold">速度 (0~3分)</span> 權重加碼的加速度</div>
              <div><span className="text-warning font-semibold">現金 (0~1分)</span> 進攻模式加分</div>
            </div>
            <strong className="text-text-primary">建議分級：</strong>
            <span className="bg-up text-white px-2 py-0.5 rounded text-xs mx-1">強力買進</span> 8分+
            <span className="bg-warning text-white px-2 py-0.5 rounded text-xs mx-1">買進</span> 5~7分
            <span className="bg-text-muted/70 text-text-primary px-2 py-0.5 rounded text-xs mx-1">觀望</span> 2~4分
          </div>
        </details>
        <DataTable columns={recColumns} data={top10} emptyText="暫無推薦" />
      </TableContainer>

      {/* Section 2: Backtest */}
      {backtest && (
        <TableContainer title="信號回測績效">
          <details className="mb-3 text-sm">
            <summary className="cursor-pointer text-down font-medium">這些數字怎麼看？怎麼用？</summary>
            <div className="mt-2 p-3 bg-down/5 rounded-lg text-text-muted leading-relaxed">
              每當 00981A 經理人新增或加碼一檔股票，就產生一個「信號」。追蹤信號發出後 10 天和 20 天的漲跌表現。
              <br />勝率 &gt; 55% → 值得跟單。勝率 &gt; 65% → 強烈跟單。
            </div>
          </details>

          <KpiGrid>
            <KpiCard label="總信號數" value={backtest.summary?.total_signals ?? '-'} />
            <KpiCard label="10日勝率" value={backtest.summary?.win_rate_10d != null ? `${backtest.summary.win_rate_10d.toFixed(1)}%` : '-'} valueColor={(backtest.summary?.win_rate_10d ?? 0) >= 55 ? 'text-down' : 'text-text-muted'} />
            <KpiCard label="10日平均報酬" value={backtest.summary?.avg_return_10d != null ? `${backtest.summary.avg_return_10d >= 0 ? '+' : ''}${backtest.summary.avg_return_10d.toFixed(2)}%` : '-'} valueColor={(backtest.summary?.avg_return_10d ?? 0) > 0 ? 'text-up' : 'text-down'} />
            <KpiCard label="20日平均報酬" value={backtest.summary?.avg_return_20d != null ? `${backtest.summary.avg_return_20d >= 0 ? '+' : ''}${backtest.summary.avg_return_20d.toFixed(2)}%` : '-'} valueColor={(backtest.summary?.avg_return_20d ?? 0) > 0 ? 'text-up' : 'text-down'} />
          </KpiGrid>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-sm font-semibold text-text-primary mb-2">信號類型勝率比較</div>
              <div className="h-56">
                {backtestBarData && (
                  <Bar data={backtestBarData} options={{
                    responsive: true, maintainAspectRatio: false,
                    plugins: defaultPluginOptions,
                    scales: { y: defaultScaleOptions, x: defaultScaleOptions },
                  }} />
                )}
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold text-text-primary mb-2">近期回測結果</div>
              <div className="max-h-56 overflow-y-auto">
                <DataTable columns={backtestSignalColumns} data={backtestSignals.slice(0, 20)} emptyText="暫無回測資料" />
              </div>
            </div>
          </div>
        </TableContainer>
      )}

      {/* Section 3: 跟單回測分析 (static data) */}
      <div className="text-lg font-bold text-text-primary mt-6">跟單回測分析</div>

      <IntroBox variant="red">
        00981A 持股異動信號回測（2025/10/17 ~ 2025/12/26）。分析新增/加碼持股後 3、5、10 日的短線績效與勝率，找出最佳跟單策略與現金水位濾網效果。
      </IntroBox>

      <KpiGrid>
        <KpiCard label="新增持股" value="81%" valueColor="text-up" subtext="勝率 | 平均報酬 9.0% | 建議跟 5 天" />
        <KpiCard label="加碼持股" value="68%" valueColor="text-up" subtext="勝率 | 平均報酬 5.6% | 建議跟 3 天" />
        <KpiCard label="新增 + 現金>4%" value="83%" valueColor="text-up" subtext="勝率 | 5日報酬 6.3%（最強組合）" />
        <KpiCard label="5日內二次加碼" value="59%" valueColor="text-warning" subtext="勝率偏弱 | 最多跟 3 天" />
      </KpiGrid>

      {/* Static backtest table */}
      <TableContainer title="信號類型 x 持有天數 績效明細">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="py-2 px-3 text-left text-xs font-semibold text-text-muted">信號條件</th>
              <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">3日績效</th>
              <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">3日勝率</th>
              <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">5日績效</th>
              <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">5日勝率</th>
              <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">10日績效</th>
              <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">10日勝率</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border/50">
              <td className="py-2 px-3"><Badge variant="blue">加碼</Badge>（473 筆）</td>
              <td className="py-2 px-3 text-right text-up">+1.71%</td><td className="py-2 px-3 text-right">60.7%</td>
              <td className="py-2 px-3 text-right text-up">+1.74%</td><td className="py-2 px-3 text-right">58.7%</td>
              <td className="py-2 px-3 text-right text-text-muted">+0.31%</td><td className="py-2 px-3 text-right text-text-muted">47.0%</td>
            </tr>
            <tr className="border-b border-border/50 bg-up/5">
              <td className="py-2 px-3"><Badge variant="blue">加碼</Badge> + 現金&gt;4%</td>
              <td className="py-2 px-3 text-right text-up">+3.07%</td><td className="py-2 px-3 text-right text-up">69.9%</td>
              <td className="py-2 px-3 text-right text-up">+2.95%</td><td className="py-2 px-3 text-right">64.6%</td>
              <td className="py-2 px-3 text-right text-down">-0.55%</td><td className="py-2 px-3 text-right text-text-muted">45.5%</td>
            </tr>
            <tr className="border-b border-border/50">
              <td className="py-2 px-3"><Badge variant="red">新增</Badge>（21 筆）</td>
              <td className="py-2 px-3 text-right text-up">+2.21%</td><td className="py-2 px-3 text-right">61.9%</td>
              <td className="py-2 px-3 text-right text-up font-bold">+5.15%</td><td className="py-2 px-3 text-right text-up font-bold">75.0%</td>
              <td className="py-2 px-3 text-right text-up">+4.66%</td><td className="py-2 px-3 text-right">68.8%</td>
            </tr>
            <tr className="border-b border-border/50 bg-up/5">
              <td className="py-2 px-3"><Badge variant="red">新增</Badge> + 現金&gt;4%（6 筆）</td>
              <td className="py-2 px-3 text-right text-up">+2.77%</td><td className="py-2 px-3 text-right">66.7%</td>
              <td className="py-2 px-3 text-right text-up font-bold">+6.33%</td><td className="py-2 px-3 text-right text-up font-bold">83.3%</td>
              <td className="py-2 px-3 text-right text-up font-bold">+6.60%</td><td className="py-2 px-3 text-right text-up font-bold">80.0%</td>
            </tr>
            <tr className="border-b border-border/50">
              <td className="py-2 px-3">5日內二次加碼（366 筆）</td>
              <td className="py-2 px-3 text-right text-up">+1.48%</td><td className="py-2 px-3 text-right">58.7%</td>
              <td className="py-2 px-3 text-right text-up">+1.29%</td><td className="py-2 px-3 text-right">56.3%</td>
              <td className="py-2 px-3 text-right text-down">-0.40%</td><td className="py-2 px-3 text-right text-text-muted">44.9%</td>
            </tr>
          </tbody>
        </table>
      </TableContainer>

      {/* Conclusions */}
      <div className="text-sm font-semibold text-text-primary mb-2">結論與策略建議</div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <InsightCard title="結論 1｜整體效果排序" borderColor="border-l-up">新增持股（績效最高）＞ 一般加碼 ＞ 5日內二次加碼（最弱）</InsightCard>
        <InsightCard title="結論 2｜加碼建議持有期" borderColor="border-l-accent">以資金效率看，加碼事件偏向跟 3 天較合適。10 天後勝率跌破 50%。</InsightCard>
        <InsightCard title="結論 3｜新增建議持有期" borderColor="border-l-up">新增事件偏向跟 5 天表現最佳（勝率 75%、報酬 5.15%）。</InsightCard>
        <InsightCard title="結論 4｜5日內二次加碼" borderColor="border-l-warning">這類事件偏弱，建議最多跟 3 天內，避免拖太久把優勢耗掉。</InsightCard>
        <InsightCard title="結論 5｜現金 >4% 濾網" borderColor="border-l-up">當 00981A 現金水位 &gt;4% 時進場，勝率和績效明顯提升。最重要的濾網。</InsightCard>
        <InsightCard title="結論 6｜短線資金配置" borderColor="border-l-text-muted">若目標是長抱，直接買 ETF 即可。跟單的價值在於短線資金效率的最佳化。</InsightCard>
      </div>

      <div className="p-4 bg-warning/10 border border-warning/20 rounded-xl text-sm text-text-muted mt-2">
        <strong>重要提醒：</strong>跟單有統計優勢，但不等於完整交易策略。仍需搭配公司產業基本面、法說會佈局、產業旺季等條件來建立完整優勢後再進場。回測期間僅 2 個月，樣本數有限。
      </div>
    </div>
  )
}
