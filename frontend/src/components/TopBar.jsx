/**
 * TRADEKING — TopBar Component
 * VIX, GIFT Nifty, FII net, market status, connection status
 */
import React from 'react'
import { formatNumber, formatScore, formatCrores } from '../utils/formatters'

export default function TopBar({ macro, wsStatus, lastUpdate }) {
  const statusClass = wsStatus === 'connected' ? 'live' : wsStatus === 'reconnecting' ? 'reconnecting' : 'offline'
  const statusLabel = wsStatus === 'connected' ? 'LIVE' : wsStatus === 'reconnecting' ? 'RECONNECTING...' : 'OFFLINE'

  return (
    <div style={styles.bar}>
      {/* Logo */}
      <div style={styles.logo}>
        <span style={styles.logoText}>TRADEKING</span>
        <span className="text-xs text-secondary" style={{ marginLeft: 8 }}>Institutional Intelligence</span>
      </div>

      {/* Macro Pills */}
      <div style={styles.pills}>
        <Pill label="VIX" value={macro.vix?.toFixed(2) || '—'} change={macro.vix_change} />
        <Pill label="GIFT NIFTY" value={formatNumber(macro.gift_nifty)} badge={macro.gift_nifty_bias} />
        <Pill label="FII CASH" value={formatCrores(macro.fii_cash_net)} direction={macro.fii_cash_direction} />
        <Pill label="FII FUTURES" value={formatNumber(macro.fii_futures_net)} direction={macro.fii_futures_net > 0 ? 'BUY' : 'SELL'} />
      </div>

      {/* Status */}
      <div style={styles.status}>
        {macro.expiry_day && (
          <span style={styles.expiryBadge}>EXPIRY DAY</span>
        )}
        <span className={`status-dot status-dot--${statusClass}`} />
        <span className="mono text-xs" style={{ color: wsStatus === 'connected' ? 'var(--signal-green)' : 'var(--warning-gold)' }}>
          {statusLabel}
        </span>
        {lastUpdate && (
          <span className="text-xs text-secondary" style={{ marginLeft: 8 }}>
            {new Date(lastUpdate).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
          </span>
        )}
      </div>
    </div>
  )
}

function Pill({ label, value, change, direction, badge }) {
  const changeColor = change > 0 ? 'var(--signal-red)' : change < 0 ? 'var(--signal-green)' : 'var(--text-secondary)'
  const dirColor = direction === 'BUY' ? 'var(--signal-green)' : direction === 'SELL' ? 'var(--signal-red)' : 'var(--text-secondary)'
  const badgeColor = badge === 'BULLISH' ? 'var(--signal-green)' : badge === 'BEARISH' ? 'var(--signal-red)' : 'var(--text-secondary)'

  return (
    <div style={styles.pill}>
      <span className="text-xs uppercase text-secondary">{label}</span>
      <span className="mono text-sm font-semibold" style={{ color: direction ? dirColor : 'var(--text-primary)' }}>
        {value}
      </span>
      {change !== undefined && change !== null && (
        <span className="mono text-xs" style={{ color: changeColor }}>
          {change > 0 ? '+' : ''}{change?.toFixed(2)}
        </span>
      )}
      {badge && (
        <span className="text-xs font-medium" style={{ color: badgeColor }}>{badge}</span>
      )}
    </div>
  )
}

const styles = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 48,
    padding: '0 16px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--bg-card)',
    flexShrink: 0,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  logoText: {
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    fontSize: 16,
    color: 'var(--accent-blue)',
    letterSpacing: '0.1em',
  },
  pills: {
    display: 'flex',
    gap: 20,
    alignItems: 'center',
  },
  pill: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 1,
  },
  status: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  expiryBadge: {
    fontFamily: 'var(--font-mono)',
    fontSize: 10,
    fontWeight: 700,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'var(--warning-gold-dim)',
    color: 'var(--warning-gold)',
    letterSpacing: '0.05em',
  },
}
