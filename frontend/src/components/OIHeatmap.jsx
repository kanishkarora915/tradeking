/**
 * TRADEKING — OI Heatmap
 * Strike-wise OI visualization for the selected index.
 */
import React, { useEffect, useState } from 'react'
import { formatLargeNumber, formatNumber } from '../utils/formatters'
import { oiHeatmapColor } from '../utils/calculations'

export default function OIHeatmap({ index }) {
  const [chain, setChain] = useState([])
  const [maxPain, setMaxPain] = useState(0)
  const [callWall, setCallWall] = useState(0)
  const [putWall, setPutWall] = useState(0)

  useEffect(() => {
    fetch(`/api/oi-chain/${index}`)
      .then(r => r.json())
      .then(data => {
        setChain(data.chain || [])
        setMaxPain(data.max_pain || 0)
        setCallWall(data.call_wall || 0)
        setPutWall(data.put_wall || 0)
      })
      .catch(() => {})
  }, [index])

  if (!chain.length) return null

  const maxCallOI = Math.max(...chain.map(s => s.call_oi || 0))
  const maxPutOI = Math.max(...chain.map(s => s.put_oi || 0))
  const maxOI = Math.max(maxCallOI, maxPutOI)

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span className="text-xs uppercase text-secondary font-semibold">OI Heatmap</span>
        <span className="mono text-xs text-secondary">
          Max Pain: <span className="text-blue font-bold">{formatNumber(maxPain)}</span>
        </span>
      </div>

      <div style={styles.legend}>
        <span className="text-xs" style={{ color: 'var(--signal-green)' }}>Put Wall: {formatNumber(putWall)}</span>
        <span className="text-xs" style={{ color: 'var(--signal-red)' }}>Call Wall: {formatNumber(callWall)}</span>
      </div>

      <div style={styles.tableWrap}>
        <div style={styles.tableHeader}>
          <span className="text-xs text-secondary" style={{ width: 60, textAlign: 'right' }}>Call OI</span>
          <span className="text-xs text-secondary" style={{ width: 70, textAlign: 'center' }}>Strike</span>
          <span className="text-xs text-secondary" style={{ width: 60, textAlign: 'left' }}>Put OI</span>
        </div>
        <div style={styles.rows}>
          {chain.map((s) => {
            const isMaxPain = s.strike === maxPain
            const isCallWall = s.strike === callWall
            const isPutWall = s.strike === putWall

            return (
              <div key={s.strike} style={{ ...styles.row, background: isMaxPain ? 'var(--accent-blue-dim)' : 'transparent' }}>
                <div
                  className="heatmap-cell mono"
                  style={{
                    width: 60,
                    background: oiHeatmapColor(s.call_oi, maxOI),
                    color: isCallWall ? 'var(--signal-red)' : 'var(--text-primary)',
                    fontWeight: isCallWall ? 700 : 400,
                  }}
                >
                  {formatLargeNumber(s.call_oi)}
                </div>
                <div
                  className="mono text-xs font-medium"
                  style={{
                    width: 70,
                    textAlign: 'center',
                    color: isMaxPain ? 'var(--accent-blue)' : 'var(--text-primary)',
                    fontWeight: isMaxPain ? 700 : 400,
                  }}
                >
                  {formatNumber(s.strike)}
                </div>
                <div
                  className="heatmap-cell mono"
                  style={{
                    width: 60,
                    textAlign: 'left',
                    background: oiHeatmapColor(s.put_oi, maxOI),
                    color: isPutWall ? 'var(--signal-green)' : 'var(--text-primary)',
                    fontWeight: isPutWall ? 700 : 400,
                  }}
                >
                  {formatLargeNumber(s.put_oi)}
                </div>
              </div>
            )
          })}
        </div>
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
    maxHeight: 320,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  legend: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  tableWrap: {
    flex: 1,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  tableHeader: {
    display: 'flex',
    justifyContent: 'center',
    gap: 4,
    paddingBottom: 4,
    borderBottom: '1px solid var(--border)',
    marginBottom: 4,
  },
  rows: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 1,
  },
  row: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 4,
    borderRadius: 2,
    padding: '1px 0',
  },
}
