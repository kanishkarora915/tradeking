/**
 * TRADEKING — Main Application
 * Institutional Options Intelligence Dashboard
 */
import React, { useState, useMemo, useEffect } from 'react'
import TopBar from './components/TopBar'
import TrapAlertBanner from './components/TrapAlertBanner'
import IndexCard from './components/IndexCard'
import EngineStatusRow from './components/EngineStatusRow'
import OIHeatmap from './components/OIHeatmap'
import WeeklySummary from './components/WeeklySummary'
import RiskPanel from './components/RiskPanel'
import VIXEngine from './components/VIXEngine'
import useWebSocket from './hooks/useWebSocket'
import useSignals from './hooks/useSignals'

const INDICES = ['NIFTY', 'BANKNIFTY', 'SENSEX']

export default function App() {
  const [activeIndex, setActiveIndex] = useState('NIFTY')
  const [activeTab, setActiveTab] = useState('signals') // 'signals' | 'vix'
  const [authChecked, setAuthChecked] = useState(false)
  const { signals, macro, loading, lastUpdate, handleWSMessage } = useSignals()
  const { status: wsStatus } = useWebSocket(handleWSMessage)

  // Auto Kite login — check auth on load, redirect if not logged in
  useEffect(() => {
    fetch('/api/auth/status')
      .then(r => r.json())
      .then(data => {
        if (!data.authenticated) {
          window.location.href = '/api/auth/kite/login'
        } else {
          setAuthChecked(true)
        }
      })
      .catch(() => setAuthChecked(true))
  }, [])

  // Get active index engine data from signals
  const activeEngines = useMemo(() => {
    return signals[activeIndex]?.engines || null
  }, [signals, activeIndex])

  if (!authChecked || loading) {
    return (
      <div className="app-layout" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="mono text-xl font-bold text-blue" style={{ letterSpacing: '0.1em', marginBottom: 8 }}>
            TRADEKING
          </div>
          <div className="text-sm text-secondary">Loading engines...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="app-layout">
      {/* Top Bar */}
      <TopBar macro={macro} wsStatus={wsStatus} lastUpdate={lastUpdate} />

      {/* Tab Switcher */}
      <div style={styles.tabBar}>
        <button style={activeTab === 'signals' ? styles.tabActive : styles.tab} onClick={() => setActiveTab('signals')}>
          SIGNALS
        </button>
        <button style={activeTab === 'vix' ? styles.tabActive : styles.tab} onClick={() => setActiveTab('vix')}>
          VIX ENGINE
        </button>
      </div>

      {/* Trap Alert Banner */}
      <TrapAlertBanner signals={signals} />

      {activeTab === 'signals' ? (
        /* ─── SIGNALS TAB ─── */
        <div className="main-grid">
          <div style={styles.leftCol}>
            <MacroPanel macro={macro} />
            <OIHeatmap index={activeIndex} />
            <WeeklySummary />
          </div>

          <div style={styles.centerCol}>
            {INDICES.map((index) => (
              <div key={index} onClick={() => setActiveIndex(index)} style={{ cursor: 'pointer' }}>
                <IndexCard index={index} data={signals[index]} />
              </div>
            ))}
          </div>

          <div style={styles.rightCol}>
            <EngineStatusRow engines={activeEngines} index={activeIndex} />
            <RiskPanel />
          </div>
        </div>
      ) : (
        /* ─── VIX ENGINE TAB ─── */
        <div style={styles.vixLayout}>
          <div style={styles.vixCenter}>
            <VIXEngine />
          </div>
          <div style={styles.vixSide}>
            {INDICES.map((index) => (
              <div key={index}>
                <IndexCard index={index} data={signals[index]} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={styles.footer}>
        <span className="text-xs text-secondary">
          TRADEKING v1.0 — Institutional Options Intelligence
        </span>
        <span className="mono text-xs text-secondary">
          {wsStatus === 'connected' ? 'WS Connected' : 'WS ' + wsStatus}
          {lastUpdate && ` | Last: ${new Date(lastUpdate).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`}
        </span>
      </div>
    </div>
  )
}

/**
 * Macro Panel — VIX Gauge + FII/DII summary for left sidebar
 */
function MacroPanel({ macro }) {
  if (!macro || !macro.vix) return null

  const vixColor = macro.vix_level === 'HIGH' ? 'var(--signal-red)' : macro.vix_level === 'LOW' ? 'var(--signal-green)' : 'var(--text-primary)'

  return (
    <div style={styles.macroPanel}>
      <div style={styles.macroHeader}>
        <span className="text-xs uppercase text-secondary font-semibold">Macro Overview</span>
      </div>

      {/* VIX */}
      <div style={styles.macroRow}>
        <span className="text-xs text-secondary">India VIX</span>
        <span className="mono text-sm font-bold" style={{ color: vixColor }}>
          {macro.vix?.toFixed(2)}
        </span>
      </div>
      <div style={styles.macroRow}>
        <span className="text-xs text-secondary">VIX Change</span>
        <span className={`mono text-xs ${macro.vix_change > 0 ? 'text-red' : 'text-green'}`}>
          {macro.vix_change > 0 ? '+' : ''}{macro.vix_change?.toFixed(2)}
        </span>
      </div>

      {/* FII Cash */}
      <div style={{ ...styles.macroRow, marginTop: 8 }}>
        <span className="text-xs text-secondary">FII Cash Net</span>
        <span className={`mono text-xs font-bold ${macro.fii_cash_net > 0 ? 'text-green' : 'text-red'}`}>
          {macro.fii_cash_net > 0 ? '+' : ''}{macro.fii_cash_net?.toFixed(0)} Cr
        </span>
      </div>

      {/* GIFT Nifty */}
      <div style={styles.macroRow}>
        <span className="text-xs text-secondary">GIFT Nifty</span>
        <span className="mono text-xs font-semibold">{macro.gift_nifty?.toFixed(0) || '—'}</span>
      </div>
      <div style={styles.macroRow}>
        <span className="text-xs text-secondary">Gap</span>
        <span className={`mono text-xs ${macro.gift_nifty_gap > 0 ? 'text-green' : macro.gift_nifty_gap < 0 ? 'text-red' : 'text-secondary'}`}>
          {macro.gift_nifty_gap > 0 ? '+' : ''}{macro.gift_nifty_gap?.toFixed(0)} ({macro.gift_nifty_bias})
        </span>
      </div>

      {/* FII Futures */}
      <div style={{ ...styles.macroRow, marginTop: 8 }}>
        <span className="text-xs text-secondary">FII Fut Net</span>
        <span className={`mono text-xs font-bold ${macro.fii_futures_net > 0 ? 'text-green' : 'text-red'}`}>
          {macro.fii_futures_net?.toLocaleString() || '—'}
        </span>
      </div>

      {/* Market Status */}
      <div style={{ ...styles.macroRow, marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
        <span className="text-xs text-secondary">Market</span>
        <span className={`mono text-xs font-bold ${macro.market_open ? 'text-green' : 'text-red'}`}>
          {macro.market_open ? 'OPEN' : 'CLOSED'}
        </span>
      </div>
    </div>
  )
}

const styles = {
  tabBar: {
    display: 'flex',
    gap: 0,
    padding: '0 16px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--bg-card)',
    flexShrink: 0,
  },
  tab: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)',
    fontSize: 11,
    fontWeight: 600,
    padding: '8px 16px',
    cursor: 'pointer',
    letterSpacing: '0.08em',
  },
  tabActive: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid var(--accent-blue)',
    color: 'var(--accent-blue)',
    fontFamily: 'var(--font-mono)',
    fontSize: 11,
    fontWeight: 700,
    padding: '8px 16px',
    cursor: 'pointer',
    letterSpacing: '0.08em',
  },
  vixLayout: {
    display: 'grid',
    gridTemplateColumns: '500px 1fr',
    gap: 16,
    flex: 1,
    padding: 16,
    overflow: 'auto',
    minHeight: 0,
  },
  vixCenter: {
    overflow: 'auto',
    minHeight: 0,
  },
  vixSide: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'auto',
    minHeight: 0,
  },
  leftCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'auto',
    minHeight: 0,
  },
  centerCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'auto',
    minHeight: 0,
  },
  rightCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'auto',
    minHeight: 0,
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 16px',
    borderTop: '1px solid var(--border)',
    background: 'var(--bg-card)',
    flexShrink: 0,
  },
  macroPanel: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 12,
  },
  macroHeader: {
    marginBottom: 10,
    paddingBottom: 8,
    borderBottom: '1px solid var(--border)',
  },
  macroRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '3px 0',
  },
}
