import { useState } from 'react'
import { useData } from '../contexts/DataContext'
import { IntroBox, TableContainer } from '../components/shared'
import '../lib/chartDefaults'
import type { RiskSignal } from '../types'

const RISK_COLORS: Record<string, string> = { red: '#ff4757', yellow: '#ffa502', green: '#00c48c' }

function ScoreRing({ score, maxScore, level }: { score: number; maxScore: number; level: string }) {
  const pct = Math.min(score / maxScore, 1)
  const circumference = 2 * Math.PI * 60
  const offset = circumference * (1 - pct)
  const color = RISK_COLORS[level] || RISK_COLORS.green

  return (
    <div className="relative w-36 h-36 shrink-0">
      <svg width="144" height="144" viewBox="0 0 144 144">
        <circle cx="72" cy="72" r="60" fill="none" stroke="var(--color-border)" strokeWidth="10" />
        <circle
          cx="72" cy="72" r="60" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 72 72)"
          style={{ transition: 'stroke-dashoffset 1s ease, stroke 0.5s' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold" style={{ color }}>{score}</span>
        <span className="text-xs text-text-muted">/{maxScore}</span>
      </div>
    </div>
  )
}

function SignalCard({ signal, onClick }: { signal: RiskSignal; onClick: () => void }) {
  const color = RISK_COLORS[signal.signal] || RISK_COLORS.green

  return (
    <button onClick={onClick} className="w-full text-left bg-card border border-border rounded-xl p-4 hover:bg-card-hover transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-text-primary">{signal.name}</span>
        <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
      </div>
      <div className="text-2xl font-bold mb-1" style={{ color }}>{signal.value?.toFixed(2) ?? '-'}</div>
      <div className="text-xs text-text-muted mb-2">{signal.desc || '-'}</div>
      {/* Phase & slope info */}
      <div className="flex items-center gap-2 text-xs text-text-muted">
        {signal.phase_label && <span className="bg-border/50 px-1.5 py-0.5 rounded">{signal.phase_label}</span>}
        {signal.slope_20d != null && (
          <span className={signal.slope_20d > 0 ? 'text-up' : signal.slope_20d < 0 ? 'text-down' : ''}>
            slope: {signal.slope_20d > 0 ? '+' : ''}{signal.slope_20d.toFixed(4)}
          </span>
        )}
      </div>
    </button>
  )
}

function SignalDetailModal({ signal, onClose }: { signal: RiskSignal; onClose: () => void }) {
  const color = RISK_COLORS[signal.signal] || RISK_COLORS.green
  const signalLabel = signal.signal === 'red' ? '紅燈' : signal.signal === 'yellow' ? '黃燈' : '綠燈'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-card border border-border rounded-2xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-text-primary">{signal.name}</h3>
          <button onClick={onClose} className="text-2xl text-text-muted hover:text-text-primary">&times;</button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <div className="bg-bg rounded-lg p-3 text-center">
            <div className="text-xs text-text-muted mb-1">當前值</div>
            <div className="text-xl font-bold" style={{ color }}>{signal.value?.toFixed(4) ?? '-'}</div>
          </div>
          <div className="bg-bg rounded-lg p-3 text-center">
            <div className="text-xs text-text-muted mb-1">燈號</div>
            <div className="text-xl font-bold" style={{ color }}>{signalLabel}</div>
          </div>
          <div className="bg-bg rounded-lg p-3 text-center">
            <div className="text-xs text-text-muted mb-1">20日斜率</div>
            <div className="text-xl font-bold" style={{ color }}>
              {signal.slope_20d != null ? (signal.slope_20d > 0 ? '+' : '') + signal.slope_20d.toFixed(4) : '-'}
            </div>
          </div>
          <div className="bg-bg rounded-lg p-3 text-center">
            <div className="text-xs text-text-muted mb-1">加速度</div>
            <div className="text-xl font-bold" style={{ color }}>
              {signal.accel != null ? signal.accel.toFixed(4) : '-'}
            </div>
          </div>
        </div>

        {/* Description & Theory */}
        <div className="text-sm text-text-muted mb-3">{signal.desc || '-'}</div>
        {signal.theory && (
          <div className="text-sm text-text-muted mb-4 p-3 bg-accent/5 rounded-lg">
            <span className="font-semibold text-text-primary">理論依據：</span>{signal.theory}
          </div>
        )}

        {/* Extra info grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
          {signal.phase_label && (
            <div className="bg-bg rounded-lg p-3">
              <div className="text-xs text-text-muted mb-1">階段</div>
              <div className="text-sm font-semibold text-text-primary">{signal.phase_label}</div>
            </div>
          )}
          {signal.extremity_pct != null && (
            <div className="bg-bg rounded-lg p-3">
              <div className="text-xs text-text-muted mb-1">極端度</div>
              <div className="text-sm font-semibold text-text-primary">{(signal.extremity_pct * 100).toFixed(1)}%</div>
            </div>
          )}
          <div className="bg-bg rounded-lg p-3">
            <div className="text-xs text-text-muted mb-1">可靠性</div>
            <div className="text-sm font-semibold text-text-primary">{signal.reliable ? '可靠' : '不確定'}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function P8RiskSignals() {
  const { strategy, newsAnalysis } = useData()
  const [selectedSignal, setSelectedSignal] = useState<RiskSignal | null>(null)

  const riskSignals = strategy?.risk_signals
  const agentStatus = strategy?.agent_status
  const signals = riskSignals?.signals || []

  // Find macro analysis from news
  const _macroAnalysis = newsAnalysis?.news_analyses?.find(n => n.category === '宏觀風險' || n.category === '市場動態')
  void _macroAnalysis // keep for future use

  if (!riskSignals) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-text-primary">宏觀風險訊號儀表板</h2>
        <div className="bg-card border border-border rounded-xl p-8 text-center text-text-muted">暫無風險訊號資料</div>
      </div>
    )
  }

  const levelLabel = riskSignals.level === 'red' ? '高度警戒' : riskSignals.level === 'yellow' ? '中度警戒' : '正常'
  const levelColor = RISK_COLORS[riskSignals.level] || RISK_COLORS.green

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-text-primary">宏觀風險訊號儀表板</h2>

      <IntroBox>
        基於選擇權隱含特徵研究與流動性風險實驗，追蹤 8 個宏觀風險指標的 20 日趨勢斜率。<br />
        核心理論：<strong>VIX 斜率</strong>比絕對值重要、<strong>SPY/JPY</strong> 套利平倉是最強領先指標、<strong>HYG/TLT</strong> 反映流動性枯竭速度。
      </IntroBox>

      {/* Agent Status */}
      {agentStatus && (
        <details className="text-sm">
          <summary className="cursor-pointer text-text-muted py-1">Agent Pipeline 狀態</summary>
          <div className="grid grid-cols-3 gap-2 mt-2">
            {Object.entries(agentStatus).map(([key, agent]) => (
              <div key={key} className="bg-card border border-border rounded-lg p-3">
                <div className="text-xs text-text-muted">{key}</div>
                <div className={`text-sm font-semibold ${agent.status === 'success' ? 'text-down' : 'text-warning'}`}>
                  {agent.status}
                </div>
                <div className="text-xs text-text-muted">{agent.updated_at}</div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Score Panel */}
      <div className="flex items-center gap-6 bg-card border border-border rounded-xl p-6">
        <ScoreRing score={riskSignals.score} maxScore={riskSignals.max_score} level={riskSignals.level} />
        <div>
          <div className="text-lg font-bold mb-1" style={{ color: levelColor }}>{levelLabel}</div>
          <div className="text-sm text-text-muted leading-relaxed">
            紅燈 {riskSignals.n_red} 個 · 黃燈 {riskSignals.n_yellow} 個 · 綠燈 {riskSignals.n_green} 個
          </div>
          {riskSignals.updated_at && (
            <div className="text-xs text-text-muted mt-2">更新：{riskSignals.updated_at}</div>
          )}
        </div>
      </div>

      {/* Signal Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {signals.map(signal => (
          <SignalCard key={signal.key} signal={signal} onClick={() => setSelectedSignal(signal)} />
        ))}
      </div>

      {/* Signal Detail Modal */}
      {selectedSignal && (
        <SignalDetailModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}

      {/* Research Basis */}
      <details className="bg-card border border-border rounded-xl p-5">
        <summary className="cursor-pointer font-semibold text-text-primary">研究依據與理論基礎</summary>
        <div className="mt-4 text-sm text-text-muted leading-relaxed space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-4 bg-up/5 rounded-lg border-l-4 border-l-up">
              <div className="font-semibold text-text-primary mb-1">1. SPY/JPY 套利平倉壓力 <span className="text-up text-xs">重要度 19.9%</span></div>
              <p>全球 Carry Trade 的核心機制：借入低利率日圓，買進美股。日圓走強迫使平倉。2024年8月日圓套利平倉事件，台股同步重挫千點。</p>
            </div>
            <div className="p-4 bg-up/5 rounded-lg border-l-4 border-l-up">
              <div className="font-semibold text-text-primary mb-1">2. VIX 波動率趨勢 <span className="text-up text-xs">重要度 13.3%</span></div>
              <p>VIX 的緩步墊高比突然飆升更能預測崩盤。20日斜率持續正值且加速 = 恐慌累積。</p>
            </div>
            <div className="p-4 bg-warning/5 rounded-lg border-l-4 border-l-warning">
              <div className="font-semibold text-text-primary mb-1">3. HYG/TLT 流動性枯竭 <span className="text-warning text-xs">重要度 12.5%</span></div>
              <p>HYG/TLT 比值下降 = 資金從垃圾債撤出湧入國債。信用市場通常領先股市 1-2 週反應風險。</p>
            </div>
            <div className="p-4 bg-accent/5 rounded-lg border-l-4 border-l-accent">
              <div className="font-semibold text-text-primary mb-1">4. DXY 美元壓力</div>
              <p>美元走強 → 新興市場貨幣貶值 → 外資撤出 → 台股承壓。</p>
            </div>
            <div className="p-4 bg-accent/5 rounded-lg border-l-4 border-l-accent">
              <div className="font-semibold text-text-primary mb-1">5-8. US10Y / Fear&Greed / Gold / Oil</div>
              <p>殖利率上升壓縮股票估值、恐懼指數為情緒濾網、黃金反映避險需求、油價影響通膨預期。</p>
            </div>
            <div className="p-4 bg-purple/5 rounded-lg border-l-4 border-l-purple">
              <div className="font-semibold text-text-primary mb-1">方法論：速度與加速度</div>
              <p>一階導數（20日斜率）判斷趨勢，二階導數（加速度）判斷惡化是否擴大。紅燈x2 + 黃燈x1 → 換算 0-10 分制。</p>
            </div>
          </div>
        </div>
      </details>
    </div>
  )
}
