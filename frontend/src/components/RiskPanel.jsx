/**
 * TRADEKING — Risk Panel
 * Capital & risk status display.
 */
import React, { useEffect, useState } from 'react'
import { formatNumber } from '../utils/formatters'

export default function RiskPanel() {
  const [risk, setRisk] = useState(null)

  useEffect(() => {
    fetch('/api/risk')
      .then(r => r.json())
      .then(setRisk)
      .catch(() => {})
  }, [])

  if (!risk) return null

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span className="text-xs uppercase text-secondary font-semibold">Risk Management</span>
      </div>

      <div style={styles.grid}>
        <RiskRow label="Total Capital" value={`\u20B9${formatNumber(risk.total_capital)}`} />
        <RiskRow label="Max Risk/Trade" value={`\u20B9${formatNumber(risk.max_risk_per_trade)}`} accent />
        <RiskRow label="Daily Loss Limit" value={`\u20B9${formatNumber(risk.daily_loss_limit)}`} warn />
        <RiskRow label="Stop Loss" value={`${risk.stop_loss_pct}% of premium`} />
      </div>

      <div style={styles.rules}>
        <span className="text-xs uppercase text-secondary font-semibold" style={{ marginBottom: 6, display: 'block' }}>Active Rules</span>
        {risk.rules && Object.entries(risk.rules).map(([key, value]) => (
          <div key={key} style={styles.ruleRow}>
            <span className="text-xs text-secondary">{key.replace(/_/g, ' ')}</span>
            <span className="mono text-xs font-medium">{typeof value === 'boolean' ? (value ? 'ON' : 'OFF') : value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function RiskRow({ label, value, accent, warn }) {
  return (
    <div style={styles.riskRow}>
      <span className="text-xs text-secondary">{label}</span>
      <span className={`mono text-sm font-bold ${accent ? 'text-blue' : warn ? 'text-gold' : ''}`}>{value}</span>
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
    marginBottom: 10,
    paddingBottom: 8,
    borderBottom: '1px solid var(--border)',
  },
  grid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    marginBottom: 12,
  },
  riskRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  rules: {
    paddingTop: 10,
    borderTop: '1px solid var(--border)',
  },
  ruleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '3px 0',
  },
}
