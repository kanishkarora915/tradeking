/**
 * TRADEKING — Index Signal Card
 * Main signal display for NIFTY / BANKNIFTY / SENSEX
 */
import React, { useEffect, useState } from 'react'
import { formatNumber, formatScore, signalClass } from '../utils/formatters'
import { confidencePct } from '../utils/calculations'
import ConfluenceGauge from './ConfluenceGauge'

export default function IndexCard({ index, data }) {
  const signal = data?.signal || 'WAIT'
  const score = data?.score || 0
  const confidence = data?.confidence || 'LOW'
  const spot = data?.spot_price || 0
  const prevClose = data?.prev_close || 0
  const changePct = data?.price_change_pct || 0
  const enginesBull = data?.engines_bullish || 0
  const enginesBear = data?.engines_bearish || 0
  const topReason = data?.top_reason || '—'
  const ivr = data?.ivr || 0
  const pcr = data?.pcr || 0
  const vix = data?.vix || 0
  const ivrGate = data?.ivr_gate
  const expiryGate = data?.expiry_gate
  const trade = data?.trade || {}

  const cls = signalClass(signal)
  const isCall = signal.includes('CALL')
  const isPut = signal.includes('PUT')

  // Animate score on change
  const [displayScore, setDisplayScore] = useState(score)
  useEffect(() => {
    const start = displayScore
    const end = score
    const duration = 600
    const startTime = Date.now()

    const animate = () => {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
      setDisplayScore(start + (end - start) * eased)
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [score])

  return (
    <div
      className={`card card--${cls} ${isCall ? 'pulse-green' : isPut ? 'pulse-red' : ''}`}
      style={styles.card}
    >
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span className="mono font-bold text-md">{index}</span>
          <span className={`status-dot status-dot--live`} style={{ marginLeft: 8 }} />
          <span className="text-xs text-secondary" style={{ marginLeft: 4 }}>LIVE</span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span className="mono font-bold text-lg">{formatNumber(spot)}</span>
          {changePct !== 0 && (
            <span className={`mono text-xs ${changePct > 0 ? 'text-green' : 'text-red'}`} style={{ marginLeft: 6 }}>
              {changePct > 0 ? '+' : ''}{changePct.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      {/* Gate Overlays */}
      {ivrGate && (
        <div style={styles.gateOverlay}>
          <span className="mono font-bold text-sm text-gold">IV TOO EXPENSIVE — WAIT</span>
        </div>
      )}
      {expiryGate && (
        <div style={{ ...styles.gateOverlay, background: 'var(--warning-gold-dim)' }}>
          <span className="mono font-bold text-sm text-gold">EXPIRY DAY — CAUTION</span>
        </div>
      )}

      {/* Big Signal */}
      <div style={styles.signalArea}>
        <span style={{ fontSize: 14, color: isCall ? 'var(--signal-green)' : isPut ? 'var(--signal-red)' : 'var(--text-secondary)' }}>
          {isCall ? '\u25B2' : isPut ? '\u25BC' : '\u25CF'}
        </span>
        <span
          className="mono font-bold"
          style={{
            fontSize: 36,
            color: isCall ? 'var(--signal-green)' : isPut ? 'var(--signal-red)' : 'var(--text-secondary)',
            letterSpacing: '0.05em',
          }}
        >
          {signal.replace('STRONG_', 'STRONG ')}
        </span>
      </div>

      {/* Score + Confidence */}
      <div style={styles.scoreRow}>
        <div>
          <span className="text-xs text-secondary uppercase">Score</span>
          <span className="mono font-bold text-lg" style={{ marginLeft: 8, color: isCall ? 'var(--signal-green)' : isPut ? 'var(--signal-red)' : 'var(--text-primary)' }}>
            {formatScore(displayScore)} / 10
          </span>
        </div>
        <div style={{ flex: 1, marginLeft: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="text-xs text-secondary">Confidence</span>
            <span className={`mono text-xs font-semibold ${confidence === 'HIGH' ? 'text-green' : confidence === 'MEDIUM' ? 'text-blue' : 'text-secondary'}`}>
              {confidence}
            </span>
          </div>
          <div className="confidence-bar">
            <div
              className={`confidence-bar__fill confidence-bar__fill--${cls === 'call' ? 'green' : cls === 'put' ? 'red' : 'gray'}`}
              style={{ width: `${confidencePct(score)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Gauge */}
      <ConfluenceGauge score={score} />

      {/* Top Signal */}
      <div style={styles.reasonRow}>
        <span className="text-xs text-secondary">Top Signal:</span>
        <span className="mono text-xs font-medium" style={{ marginLeft: 6 }}>{topReason}</span>
      </div>

      {/* Active Engines */}
      <div style={styles.reasonRow}>
        <span className="text-xs text-secondary">Active Engines:</span>
        <span className="mono text-xs" style={{ marginLeft: 6 }}>
          <span className="text-green">{enginesBull}</span>
          <span className="text-secondary">/8</span>
          <span className="text-secondary" style={{ margin: '0 4px' }}>|</span>
          <span className="text-green">{enginesBull} bullish</span>
          <span className="text-secondary" style={{ margin: '0 4px' }}>/</span>
          <span className="text-red">{enginesBear} bearish</span>
        </span>
      </div>

      {/* Bottom Stats */}
      <div style={styles.bottomStats}>
        <StatPill label="IVR" value={ivr?.toFixed(0)} />
        <StatPill label="PCR" value={pcr?.toFixed(2)} />
        <StatPill label="VIX" value={vix?.toFixed(1)} />
      </div>

      {/* Trade Signal Box */}
      {trade.tradeable && (
        <div style={styles.tradeBox}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span className={`signal-badge signal-badge--${trade.direction === 'CALL' ? 'call' : 'put'}`}>
              {trade.direction} {trade.entry_strike}
            </span>
            <span className="mono text-xs text-secondary">RR: {trade.risk_reward}x | {trade.max_lots} lots</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div style={{ textAlign: 'center' }}>
              <span className="text-xs text-secondary">ENTRY</span>
              <div className="mono text-sm font-bold text-blue">{trade.entry_premium?.toFixed(1)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span className="text-xs text-secondary">STOPLOSS</span>
              <div className="mono text-sm font-bold text-red">{trade.stoploss_premium?.toFixed(1)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span className="text-xs text-secondary">TARGET</span>
              <div className="mono text-sm font-bold text-green">{trade.target_premium?.toFixed(1)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatPill({ label, value }) {
  return (
    <div style={styles.statPill}>
      <span className="text-xs text-secondary uppercase">{label}</span>
      <span className="mono text-sm font-semibold">{value || '—'}</span>
    </div>
  )
}

const styles = {
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    position: 'relative',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
  },
  signalArea: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: '8px 0',
  },
  scoreRow: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 8,
  },
  reasonRow: {
    display: 'flex',
    alignItems: 'center',
    padding: '4px 0',
    borderTop: '1px solid var(--border)',
  },
  bottomStats: {
    display: 'flex',
    justifyContent: 'space-around',
    padding: '8px 0 0',
    borderTop: '1px solid var(--border)',
  },
  statPill: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 2,
  },
  tradeBox: {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '10px 12px',
  },
  gateOverlay: {
    background: 'rgba(255, 214, 10, 0.08)',
    border: '1px solid rgba(255, 214, 10, 0.2)',
    borderRadius: 6,
    padding: '6px 12px',
    textAlign: 'center',
  },
}
