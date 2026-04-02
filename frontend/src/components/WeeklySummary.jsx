/**
 * TRADEKING — Weekly Summary Panel
 * Appears after market close (3:30 PM).
 */
import React, { useEffect, useState } from 'react'
import { formatScore } from '../utils/formatters'

export default function WeeklySummary() {
  const [summary, setSummary] = useState(null)
  const [available, setAvailable] = useState(false)

  useEffect(() => {
    fetch('/api/weekly-summary')
      .then(r => r.json())
      .then(data => {
        setAvailable(data.available)
        if (data.available) setSummary(data.summary)
      })
      .catch(() => {})
  }, [])

  if (!available || !summary) return null

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span className="text-xs uppercase text-secondary font-semibold">Post-Close Summary</span>
      </div>
      {Object.entries(summary).map(([index, data]) => (
        <div key={index} style={styles.indexRow}>
          <span className="mono text-sm font-bold">{index}</span>
          <span className={`signal-badge signal-badge--${data.final_signal?.includes('CALL') ? 'call' : data.final_signal?.includes('PUT') ? 'put' : 'wait'}`}>
            {data.final_signal}
          </span>
          <span className="mono text-xs text-secondary">{formatScore(data.final_score)}</span>
          {data.trap_detected && (
            <span className="mono text-xs text-gold">{data.trap_type}</span>
          )}
        </div>
      ))}
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
    marginBottom: 8,
    paddingBottom: 8,
    borderBottom: '1px solid var(--border)',
  },
  indexRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '6px 0',
    borderBottom: '1px solid var(--border)',
  },
}
