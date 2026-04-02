/**
 * TRADEKING — Confluence Score Gauge
 * Visual bar showing -10 to +10 normalized score.
 */
import React from 'react'
import { gaugePosition } from '../utils/calculations'

export default function ConfluenceGauge({ score }) {
  const position = gaugePosition(score || 0)
  const width = Math.abs(score || 0) * 5 // % width of the fill
  const isPositive = score > 0

  return (
    <div style={styles.container}>
      <div style={styles.labels}>
        <span className="mono text-xs text-red">-10</span>
        <span className="mono text-xs text-secondary">0</span>
        <span className="mono text-xs text-green">+10</span>
      </div>
      <div className="gauge-container">
        {/* Center line */}
        <div className="gauge-center-line" />
        {/* Fill */}
        <div
          className="gauge-fill"
          style={{
            left: isPositive ? '50%' : `${50 - width}%`,
            width: `${width}%`,
            background: isPositive ? 'var(--signal-green)' : score < 0 ? 'var(--signal-red)' : 'var(--text-tertiary)',
            opacity: 0.7,
          }}
        />
        {/* Score marker */}
        <div
          style={{
            position: 'absolute',
            left: `${position}%`,
            top: -3,
            transform: 'translateX(-50%)',
            width: 4,
            height: 14,
            borderRadius: 2,
            background: isPositive ? 'var(--signal-green)' : score < 0 ? 'var(--signal-red)' : 'var(--text-secondary)',
            transition: 'left 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        />
      </div>
    </div>
  )
}

const styles = {
  container: {
    padding: '4px 0',
  },
  labels: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
}
