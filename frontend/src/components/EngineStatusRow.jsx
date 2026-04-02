/**
 * TRADEKING — Engine Status Row
 * Shows 8 engine indicators with scores for active index.
 */
import React, { useEffect, useState } from 'react'
import { formatScore } from '../utils/formatters'

const ENGINE_LABELS = {
  engine_01_oi_state: { name: 'OI State', short: 'OI' },
  engine_02_unusual_flow: { name: 'Unusual Flow', short: 'UF' },
  engine_03_futures_basis: { name: 'Futures Basis', short: 'FB' },
  engine_04_iv_skew: { name: 'IV Skew', short: 'IV' },
  engine_05_liquidity_pool: { name: 'Liquidity', short: 'LQ' },
  engine_06_microstructure: { name: 'Microstructure', short: 'MS' },
  engine_07_macro: { name: 'Macro', short: 'MC' },
  engine_08_trap: { name: 'Trap Detect', short: 'TR' },
}

export default function EngineStatusRow({ engines, index }) {
  const [engineData, setEngineData] = useState({})

  useEffect(() => {
    if (engines) {
      setEngineData(engines)
    } else {
      // Fetch from API
      fetch(`/api/engines/${index}`)
        .then(r => r.json())
        .then(setEngineData)
        .catch(() => {})
    }
  }, [engines, index])

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span className="text-xs uppercase text-secondary font-semibold">Engine Status</span>
        <span className="mono text-xs text-secondary">{index}</span>
      </div>
      <div style={styles.grid}>
        {Object.entries(ENGINE_LABELS).map(([key, { name, short }]) => {
          const engine = engineData[key] || {}
          const score = engine.score || 0
          const isCore = key === 'engine_08_trap'

          return (
            <div key={key} style={{ ...styles.engineRow, borderLeft: isCore ? '2px solid var(--accent-blue)' : '2px solid transparent', paddingLeft: 8 }}>
              <div style={styles.engineHeader}>
                <span className={`engine-dot engine-dot--${score > 0 ? 'bullish' : score < 0 ? 'bearish' : 'neutral'}`} />
                <span className="text-xs font-medium" style={{ flex: 1, marginLeft: 6 }}>{name}</span>
                <span className={`mono text-xs font-bold ${score > 0 ? 'text-green' : score < 0 ? 'text-red' : 'text-secondary'}`}>
                  {formatScore(score)}
                </span>
              </div>
              {/* Mini bar */}
              <div style={styles.miniBar}>
                <div style={styles.miniBarCenter} />
                <div
                  style={{
                    position: 'absolute',
                    left: score >= 0 ? '50%' : `${50 + (score / (key.includes('trap') ? 3 : 2)) * 50}%`,
                    width: `${Math.abs(score) / (key.includes('trap') ? 3 : 2) * 50}%`,
                    height: '100%',
                    background: score > 0 ? 'var(--signal-green)' : score < 0 ? 'var(--signal-red)' : 'transparent',
                    borderRadius: 2,
                    opacity: 0.6,
                    transition: 'all 0.4s ease',
                  }}
                />
              </div>
              {/* Extra info for trap engine */}
              {isCore && engine.trap_type && (
                <div style={styles.trapInfo}>
                  <span className={`mono text-xs font-bold ${engine.trap_type === 'BULL_TRAP' ? 'text-red' : 'text-green'}`}>
                    {engine.trap_type} [{engine.conditions_total}/5]
                  </span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const styles = {
  container: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 12,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingBottom: 8,
    borderBottom: '1px solid var(--border)',
  },
  grid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  engineRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  engineHeader: {
    display: 'flex',
    alignItems: 'center',
  },
  miniBar: {
    position: 'relative',
    height: 4,
    background: 'var(--bg-elevated)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  miniBarCenter: {
    position: 'absolute',
    left: '50%',
    top: 0,
    width: 1,
    height: '100%',
    background: 'var(--text-tertiary)',
  },
  trapInfo: {
    marginTop: 2,
    paddingLeft: 14,
  },
}
