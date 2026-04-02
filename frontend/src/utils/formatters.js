/**
 * TRADEKING — Number & Time Formatters
 */

export function formatNumber(num, decimals = 0) {
  if (num === null || num === undefined) return '—'
  return Number(num).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function formatScore(score) {
  if (score === null || score === undefined) return '0.0'
  const prefix = score > 0 ? '+' : ''
  return `${prefix}${Number(score).toFixed(1)}`
}

export function formatPct(pct, decimals = 2) {
  if (pct === null || pct === undefined) return '—'
  const prefix = pct > 0 ? '+' : ''
  return `${prefix}${Number(pct).toFixed(decimals)}%`
}

export function formatCrores(value) {
  if (!value) return '₹0 Cr'
  const abs = Math.abs(value)
  const prefix = value >= 0 ? '+' : '-'
  if (abs >= 100) {
    return `${prefix}₹${(abs).toFixed(0)} Cr`
  }
  return `${prefix}₹${abs.toFixed(1)} Cr`
}

export function formatTime(isoString) {
  if (!isoString) return '—'
  const d = new Date(isoString)
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

export function formatLargeNumber(num) {
  if (!num) return '0'
  const abs = Math.abs(num)
  if (abs >= 10000000) return `${(num / 10000000).toFixed(1)}Cr`
  if (abs >= 100000) return `${(num / 100000).toFixed(1)}L`
  if (abs >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

export function signalColor(signal) {
  if (!signal) return 'var(--text-secondary)'
  if (signal.includes('CALL')) return 'var(--signal-green)'
  if (signal.includes('PUT')) return 'var(--signal-red)'
  return 'var(--text-secondary)'
}

export function signalClass(signal) {
  if (!signal) return 'wait'
  if (signal.includes('CALL')) return 'call'
  if (signal.includes('PUT')) return 'put'
  return 'wait'
}
