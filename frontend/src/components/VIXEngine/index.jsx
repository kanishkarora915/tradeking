/**
 * TRADEKING VIX Engine — Main Component
 * Real-time VIX monitoring + trade signal generation
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import useVIXSocket from './useVIXSocket'
import { processTick, scoreColor, getZone } from './signals'
import { ZONES, MAX_TICKS, COLORS } from './constants'

const DEFAULT_WS = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/vix`

export default function VIXEngine({ wsUrl, compact = false }) {
  const { status, lastMessage } = useVIXSocket(wsUrl || DEFAULT_WS)
  const [signalState, setSignalState] = useState(null)
  const [tickHistory, setTickHistory] = useState([])
  const [fastEmaHistory, setFastEmaHistory] = useState([])
  const [slowEmaHistory, setSlowEmaHistory] = useState([])
  const [alerts, setAlerts] = useState([])
  const [tradeSignals, setTradeSignals] = useState([])
  const [indexPrices, setIndexPrices] = useState({})
  const canvasRef = useRef(null)
  const prevState = useRef(null)

  // Process each VIX tick
  useEffect(() => {
    if (!lastMessage) return
    const msg = lastMessage
    const vixData = msg.vix || msg
    const vixValue = typeof vixData === 'object' ? vixData.vix : vixData
    if (!vixValue || vixValue <= 0) return

    // Process signals
    const state = processTick(vixValue, prevState.current)
    prevState.current = state
    setSignalState(state)

    // Update histories
    setTickHistory(prev => {
      const next = [...prev, vixValue]
      return next.length > MAX_TICKS ? next.slice(-MAX_TICKS) : next
    })
    setFastEmaHistory(prev => {
      const next = [...prev, state.fastEma]
      return next.length > MAX_TICKS ? next.slice(-MAX_TICKS) : next
    })
    setSlowEmaHistory(prev => {
      const next = [...prev, state.slowEma]
      return next.length > MAX_TICKS ? next.slice(-MAX_TICKS) : next
    })

    // Zone change alert
    if (state.zoneChanged) {
      setAlerts(prev => {
        const newAlert = {
          from: state.prevZone?.label,
          to: state.zone.label,
          vix: vixValue,
          time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
        }
        return [newAlert, ...prev].slice(0, 6)
      })
    }

    // Trade signals from backend
    if (msg.trade_signals) setTradeSignals(msg.trade_signals)
    if (msg.index_prices) setIndexPrices(msg.index_prices)
  }, [lastMessage])

  // Draw chart
  useEffect(() => {
    if (!canvasRef.current || tickHistory.length < 2) return
    drawChart(canvasRef.current, tickHistory, fastEmaHistory, slowEmaHistory)
  }, [tickHistory, fastEmaHistory, slowEmaHistory])

  const vix = signalState?.vix || 0
  const zone = signalState?.zone || getZone(0)
  const score = signalState?.score || 0

  return (
    <div style={S.container}>
      {/* Main Card */}
      <div style={{ ...S.card, borderLeft: `3px solid ${zone.color}` }}>
        <div style={S.mainRow}>
          <div>
            <div style={S.label}>INDIA VIX</div>
            <div style={{ ...S.bigNumber, color: zone.color }}>{vix.toFixed(2)}</div>
            <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
              <span style={{ ...S.badge, background: zone.bgDim, color: zone.color }}>{zone.label}</span>
              <span style={{ ...S.badge, background: 'rgba(10,132,255,0.12)', color: COLORS.accent }}>
                {signalState?.crossSignal || 'FLAT'}
              </span>
            </div>
          </div>
          {/* Buyer Edge Score Dial */}
          <ScoreDial score={score} />
        </div>
        <div style={{ ...S.actionPill, background: zone.bgDim, color: zone.color, marginTop: 8 }}>
          {zone.action}
        </div>
      </div>

      {/* Chart */}
      {!compact && (
        <div style={S.card}>
          <div style={S.label}>VIX CHART — Last {tickHistory.length} ticks</div>
          <canvas ref={canvasRef} width={440} height={90} style={{ width: '100%', height: 90, marginTop: 6 }} />
        </div>
      )}

      {/* Signal Grid 2x2 */}
      <div style={S.grid}>
        <SignalCell label="MOMENTUM" value={signalState?.momentum?.text || '—'} color={signalState?.momentum?.color || COLORS.textDim} />
        <SignalCell label="ROC" value={signalState?.roc ? `${signalState.roc > 0 ? '+' : ''}${signalState.roc.toFixed(2)}%` : '—'}
          color={signalState?.spike ? COLORS.red : COLORS.textDim} badge={signalState?.spike ? 'SPIKE' : null} />
        <SignalCell label="EMA CROSS" value={signalState?.crossSignal || 'FLAT'}
          color={signalState?.crossSignal === 'BULLISH' ? COLORS.red : signalState?.crossSignal === 'BEARISH' ? COLORS.green : COLORS.textDim} />
        <SignalCell label="STRIKE BIAS" value={zone.strikeBias?.split('—')[0]?.trim() || '—'} color={zone.color} />
      </div>

      {/* Live Trade Signals */}
      {tradeSignals.length > 0 && (
        <div style={S.card}>
          <div style={S.label}>LIVE TRADE SIGNALS</div>
          {tradeSignals.map((sig, i) => (
            <TradeSignalCard key={i} signal={sig} />
          ))}
        </div>
      )}

      {/* Zone Ladder */}
      {!compact && (
        <div style={S.card}>
          <div style={S.label}>VIX ZONES</div>
          {ZONES.map(z => (
            <div key={z.id} style={{
              ...S.zoneRow,
              background: zone.id === z.id ? z.bgDim : 'transparent',
              borderLeft: zone.id === z.id ? `3px solid ${z.color}` : '3px solid transparent',
              boxShadow: zone.id === z.id ? `0 0 12px ${z.bgDim}` : 'none',
            }}>
              <span style={{ color: z.color, fontWeight: 700, fontSize: 11, width: 70 }}>{z.label}</span>
              <span style={{ color: COLORS.textDim, fontSize: 10 }}>{z.min}–{z.max === 100 ? '∞' : z.max}</span>
              <span style={{ color: COLORS.text, fontSize: 10, flex: 1, textAlign: 'right' }}>{z.action.split(',')[0]}</span>
            </div>
          ))}
        </div>
      )}

      {/* Alert Log */}
      {!compact && alerts.length > 0 && (
        <div style={S.card}>
          <div style={S.label}>ZONE ALERTS</div>
          {alerts.map((a, i) => (
            <div key={i} style={S.alertRow}>
              <span style={{ color: COLORS.textDim, fontSize: 10 }}>{a.time}</span>
              <span style={{ fontSize: 10 }}>
                <span style={{ color: COLORS.textDim }}>{a.from}</span>
                <span style={{ color: COLORS.text, margin: '0 4px' }}>→</span>
                <span style={{ color: getZone(a.vix).color, fontWeight: 700 }}>{a.to}</span>
              </span>
              <span style={{ color: COLORS.text, fontFamily: 'var(--font-mono)', fontSize: 10 }}>{a.vix.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Status */}
      <div style={{ textAlign: 'center', padding: '4px 0' }}>
        <span style={{ fontSize: 9, color: status === 'connected' ? COLORS.green : COLORS.orange }}>
          VIX WS: {status.toUpperCase()}
        </span>
      </div>
    </div>
  )
}

/** Score Dial — SVG arc */
function ScoreDial({ score }) {
  const color = scoreColor(score)
  const angle = (score / 100) * 180
  const rad = (angle - 90) * (Math.PI / 180)
  const r = 32
  const cx = 40, cy = 40
  const x = cx + r * Math.cos(rad)
  const y = cy + r * Math.sin(rad)
  const largeArc = angle > 90 ? 1 : 0

  return (
    <div style={{ textAlign: 'center' }}>
      <svg width={80} height={50} viewBox="0 0 80 50">
        <path d="M 8 40 A 32 32 0 0 1 72 40" fill="none" stroke="#1E2130" strokeWidth="5" />
        {score > 0 && (
          <path d={`M 8 40 A 32 32 0 ${largeArc} 1 ${x} ${y}`} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" />
        )}
        <text x="40" y="38" textAnchor="middle" fill={color} fontSize="16" fontWeight="700" fontFamily="var(--font-mono)">{score}</text>
        <text x="40" y="48" textAnchor="middle" fill="#8E8E93" fontSize="7">BUYER EDGE</text>
      </svg>
    </div>
  )
}

/** Signal Cell */
function SignalCell({ label, value, color, badge }) {
  return (
    <div style={S.signalCell}>
      <div style={{ fontSize: 9, color: COLORS.textDim, letterSpacing: '0.05em', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color, marginTop: 2 }}>
        {value}
        {badge && <span style={{ ...S.badge, marginLeft: 4, fontSize: 8, background: 'rgba(255,59,48,0.15)', color: COLORS.red }}>{badge}</span>}
      </div>
    </div>
  )
}

/** Trade Signal Card */
function TradeSignalCard({ signal }) {
  const isCall = signal.direction.includes('CALL')
  const color = isCall ? COLORS.green : COLORS.red
  const bgDim = isCall ? 'rgba(48,209,88,0.08)' : 'rgba(255,59,48,0.08)'

  return (
    <div style={{ ...S.tradeCard, borderLeft: `3px solid ${color}`, background: bgDim }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13, color }}>
          {signal.direction} {signal.index} {signal.strike}
        </span>
        <span style={{
          fontSize: 9, padding: '2px 6px', borderRadius: 4, fontWeight: 600,
          background: signal.confidence === 'HIGH' ? 'rgba(255,59,48,0.15)' : signal.confidence === 'MEDIUM' ? 'rgba(255,159,10,0.15)' : 'rgba(142,142,147,0.12)',
          color: signal.confidence === 'HIGH' ? COLORS.red : signal.confidence === 'MEDIUM' ? COLORS.orange : COLORS.textDim,
        }}>{signal.confidence}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 9, color: COLORS.textDim }}>ENTRY</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: COLORS.accent }}>{signal.entry?.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 9, color: COLORS.textDim }}>STOPLOSS</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: COLORS.red }}>{signal.stoploss?.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 9, color: COLORS.textDim }}>TARGET</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: COLORS.green }}>{signal.target?.toLocaleString()}</div>
        </div>
      </div>

      <div style={{ fontSize: 10, color: COLORS.textDim, lineHeight: 1.4 }}>{signal.reason}</div>
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <span style={{ fontSize: 9, color: COLORS.textDim }}>VIX: {signal.vix}</span>
        <span style={{ fontSize: 9, color: COLORS.textDim }}>VIX ROC: {signal.vix_roc}%</span>
        <span style={{ fontSize: 9, color: COLORS.textDim }}>Price ROC: {signal.price_roc}%</span>
      </div>
    </div>
  )
}

/** Canvas Chart Drawing */
function drawChart(canvas, ticks, fastEma, slowEma) {
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height
  ctx.clearRect(0, 0, w, h)

  if (ticks.length < 2) return

  const min = Math.min(...ticks) - 0.5
  const max = Math.max(...ticks) + 0.5
  const range = max - min || 1

  const toX = (i) => (i / (ticks.length - 1)) * w
  const toY = (v) => h - ((v - min) / range) * h

  // Zone bands
  const zones = [
    { at: 13, color: 'rgba(142,142,147,0.08)' },
    { at: 18, color: 'rgba(255,214,10,0.08)' },
    { at: 24, color: 'rgba(255,159,10,0.08)' },
  ]
  for (const z of zones) {
    if (z.at >= min && z.at <= max) {
      const y = toY(z.at)
      ctx.strokeStyle = 'rgba(255,255,255,0.06)'
      ctx.lineWidth = 0.5
      ctx.setLineDash([4, 4])
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = 'rgba(255,255,255,0.2)'
      ctx.font = '8px monospace'
      ctx.fillText(z.at.toString(), 2, y - 2)
    }
  }

  // Slow EMA line
  if (slowEma.length >= 2) {
    ctx.strokeStyle = 'rgba(255,159,10,0.5)'
    ctx.lineWidth = 1
    ctx.beginPath()
    slowEma.forEach((v, i) => i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)))
    ctx.stroke()
  }

  // Fast EMA line
  if (fastEma.length >= 2) {
    ctx.strokeStyle = 'rgba(10,132,255,0.6)'
    ctx.lineWidth = 1
    ctx.beginPath()
    fastEma.forEach((v, i) => i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)))
    ctx.stroke()
  }

  // VIX line
  ctx.strokeStyle = '#F5F5F7'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ticks.forEach((v, i) => i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)))
  ctx.stroke()

  // Current value dot
  const lastX = toX(ticks.length - 1)
  const lastY = toY(ticks[ticks.length - 1])
  const zone = getZone(ticks[ticks.length - 1])
  ctx.fillStyle = zone.color
  ctx.beginPath(); ctx.arc(lastX, lastY, 3, 0, Math.PI * 2); ctx.fill()
}

/** Styles */
const S = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    maxWidth: 480,
    width: '100%',
  },
  card: {
    background: COLORS.cardBg,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 8,
    padding: 12,
  },
  mainRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  label: {
    fontSize: 9,
    fontWeight: 600,
    color: COLORS.textDim,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  bigNumber: {
    fontFamily: 'var(--font-mono)',
    fontSize: 36,
    fontWeight: 700,
    lineHeight: 1,
  },
  badge: {
    fontSize: 9,
    fontWeight: 700,
    padding: '2px 6px',
    borderRadius: 4,
    letterSpacing: '0.05em',
  },
  actionPill: {
    fontSize: 11,
    padding: '6px 10px',
    borderRadius: 6,
    textAlign: 'center',
    fontWeight: 500,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 6,
  },
  signalCell: {
    background: COLORS.cardBg,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 6,
    padding: '8px 10px',
  },
  zoneRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 8px',
    borderRadius: 4,
    marginTop: 4,
    transition: 'all 0.3s ease',
  },
  alertRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 0',
    borderBottom: `1px solid ${COLORS.border}`,
  },
  tradeCard: {
    borderRadius: 6,
    padding: '10px 12px',
    marginTop: 6,
  },
}
