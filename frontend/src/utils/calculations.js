/**
 * TRADEKING — Frontend Calculations
 */

export function calculatePCR(chain) {
  if (!chain || !chain.length) return 0
  let totalPutOI = 0
  let totalCallOI = 0
  for (const strike of chain) {
    totalPutOI += strike.put_oi || 0
    totalCallOI += strike.call_oi || 0
  }
  if (totalCallOI === 0) return 0
  return totalPutOI / totalCallOI
}

export function confidencePct(score) {
  // Map -10 to +10 score to 0-100% bar width
  return Math.min(100, Math.abs(score) * 10)
}

export function gaugePosition(score) {
  // Map -10 to +10 to 0-100% left position
  return ((score + 10) / 20) * 100
}

export function heatmapColor(value, max) {
  if (!max || !value) return 'transparent'
  const intensity = Math.min(1, Math.abs(value) / max)
  if (value > 0) {
    return `rgba(48, 209, 88, ${intensity * 0.6})`
  } else {
    return `rgba(255, 69, 58, ${intensity * 0.6})`
  }
}

export function oiHeatmapColor(oi, maxOI) {
  if (!maxOI || !oi) return 'transparent'
  const intensity = Math.min(1, oi / maxOI)
  return `rgba(10, 132, 255, ${intensity * 0.5 + 0.05})`
}
