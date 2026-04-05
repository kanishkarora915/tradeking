/**
 * TRADEKING VIX Engine — Pure Signal Math
 * All functions are pure — no side effects, easy to unit test.
 */
import { ZONES, EMA_FAST_ALPHA, EMA_SLOW_ALPHA, ROC_SPIKE_THRESHOLD, EMA_CROSS_BUFFER } from './constants'

/** Incremental EMA: newEMA = alpha * value + (1 - alpha) * prevEMA */
export function ema(value, prevEma, alpha) {
  if (prevEma === null || prevEma === undefined) return value
  return alpha * value + (1 - alpha) * prevEma
}

/** Rate of Change: ((current - previous) / previous) * 100 */
export function roc(current, previous) {
  if (!previous || previous === 0) return 0
  return ((current - previous) / previous) * 100
}

/** Spike detector: |ROC| > threshold */
export function isSpike(rocValue) {
  return Math.abs(rocValue) > ROC_SPIKE_THRESHOLD
}

/** EMA crossover signal */
export function emaCrossSignal(fastEma, slowEma) {
  if (fastEma === null || slowEma === null) return 'FLAT'
  const diff = fastEma - slowEma
  if (diff > EMA_CROSS_BUFFER) return 'BULLISH'
  if (diff < -EMA_CROSS_BUFFER) return 'BEARISH'
  return 'FLAT'
}

/** Get current VIX zone */
export function getZone(vix) {
  for (const zone of ZONES) {
    if (vix >= zone.min && vix < zone.max) return zone
  }
  return ZONES[ZONES.length - 1] // DEAD ZONE fallback
}

/** Buyer Edge Score (0-100) */
export function buyerEdgeScore(vix, fastEma, slowEma, rocValue, spikeDetected) {
  // Base: (VIX / 30) * 50, capped at 50
  let base = Math.min((vix / 30) * 50, 50)

  // Momentum bonus: if fast > slow, add up to 25
  let momentum = 0
  if (fastEma !== null && slowEma !== null && fastEma > slowEma) {
    momentum = Math.min((fastEma - slowEma) * 20, 25)
  }

  // Spike bonus: if spike AND ROC > 0, add 25
  let spike = 0
  if (spikeDetected && rocValue > 0) {
    spike = 25
  }

  return Math.min(100, Math.max(0, Math.round(base + momentum + spike)))
}

/** Score color based on value */
export function scoreColor(score) {
  if (score >= 70) return '#FF3B30'
  if (score >= 45) return '#FF9F0A'
  if (score >= 25) return '#FFD60A'
  return '#30D158'
}

/** Momentum direction text */
export function momentumDirection(fastEma, slowEma, rocValue) {
  if (fastEma === null || slowEma === null) return { text: '—', color: '#8E8E93' }
  if (rocValue > 0.5 && fastEma > slowEma) return { text: 'RISING', color: '#FF3B30' }
  if (rocValue < -0.5 && fastEma < slowEma) return { text: 'FALLING', color: '#30D158' }
  if (rocValue > 0.1) return { text: 'TICKING UP', color: '#FF9F0A' }
  if (rocValue < -0.1) return { text: 'TICKING DOWN', color: '#FFD60A' }
  return { text: 'FLAT', color: '#8E8E93' }
}

/** Process a new VIX tick and return full signal state */
export function processTick(vix, prevState) {
  const prev = prevState || {}
  const prevVix = prev.vix || vix
  const fastEmaVal = ema(vix, prev.fastEma ?? null, EMA_FAST_ALPHA)
  const slowEmaVal = ema(vix, prev.slowEma ?? null, EMA_SLOW_ALPHA)
  const rocVal = roc(vix, prevVix)
  const spike = isSpike(rocVal)
  const crossSignal = emaCrossSignal(fastEmaVal, slowEmaVal)
  const zone = getZone(vix)
  const score = buyerEdgeScore(vix, fastEmaVal, slowEmaVal, rocVal, spike)
  const momentum = momentumDirection(fastEmaVal, slowEmaVal, rocVal)
  const prevZone = prev.zone || null

  // Zone change detection
  const zoneChanged = prevZone && prevZone.id !== zone.id

  return {
    vix,
    fastEma: fastEmaVal,
    slowEma: slowEmaVal,
    roc: rocVal,
    spike,
    crossSignal,
    zone,
    score,
    momentum,
    zoneChanged,
    prevZone,
  }
}
