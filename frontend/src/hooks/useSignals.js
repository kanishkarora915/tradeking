/**
 * TRADEKING — Signal State Management Hook
 */
import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = '/api'

// Mock data for development when backend is not running
function generateMockSignals() {
  const rand = (min, max) => Math.random() * (max - min) + min
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)]

  const indices = ['NIFTY', 'BANKNIFTY', 'SENSEX']
  const bases = { NIFTY: 23450, BANKNIFTY: 51200, SENSEX: 77800 }
  const result = {}

  for (const index of indices) {
    const score = Math.round(rand(-8, 8) * 10) / 10
    const signal = score > 5 ? 'STRONG_CALL' : score > 3 ? 'CALL' : score < -5 ? 'STRONG_PUT' : score < -3 ? 'PUT' : 'WAIT'
    const bullish = Math.floor(rand(1, 6))
    const bearish = Math.floor(rand(0, 4))
    const hasTrap = Math.random() < 0.25
    const trapType = hasTrap ? pick(['BULL_TRAP', 'BEAR_TRAP']) : null

    result[index] = {
      signal,
      score,
      confidence: Math.abs(score) > 5 ? 'HIGH' : Math.abs(score) > 3 ? 'MEDIUM' : 'LOW',
      engines_bullish: bullish,
      engines_bearish: bearish,
      top_reason: hasTrap
        ? `${trapType} detected at ${bases[index] + pick([-100, -50, 50, 100])}`
        : pick(['Strong unusual call flow', 'FII net long + expanding basis', 'OI state: BULLISH, velocity +12%', 'Macro sentiment aligned']),
      ivr_gate: false,
      expiry_gate: false,
      spot_price: bases[index] + Math.round(rand(-50, 50)),
      ivr: Math.round(rand(15, 55)),
      pcr: Math.round(rand(0.6, 1.4) * 100) / 100,
      vix: Math.round(rand(11, 19) * 100) / 100,
      trap: {
        active: hasTrap,
        type: trapType,
        confidence: hasTrap ? pick(['CONFIRMED', 'PARTIAL']) : null,
        level: hasTrap ? bases[index] + pick([-100, -50, 0, 50, 100]) : 0,
      },
      engines: {
        engine_01_oi_state: { score: Math.round(rand(-2, 2) * 10) / 10 },
        engine_02_unusual_flow: { score: Math.round(rand(-3, 3) * 10) / 10 },
        engine_03_futures_basis: { score: Math.round(rand(-2, 2) * 10) / 10 },
        engine_04_iv_skew: { score: Math.round(rand(-2, 2) * 10) / 10 },
        engine_05_liquidity_pool: { score: Math.round(rand(-1, 1) * 10) / 10 },
        engine_06_microstructure: { score: Math.round(rand(-1, 1) * 10) / 10 },
        engine_07_macro: { score: Math.round(rand(-2, 2) * 10) / 10 },
        engine_08_trap: { score: hasTrap ? (trapType === 'BULL_TRAP' ? -3 : 3) : 0, trap_type: trapType, conditions_total: hasTrap ? pick([3, 4, 5]) : 0 },
      },
      timestamp: new Date().toISOString(),
    }
  }
  return result
}

function generateMockMacro() {
  const rand = (min, max) => Math.random() * (max - min) + min
  return {
    vix: Math.round(rand(11, 19) * 100) / 100,
    vix_change: Math.round(rand(-1.5, 1.5) * 100) / 100,
    vix_level: 'NORMAL',
    fii_cash_net: Math.round(rand(-3000, 3000)),
    fii_cash_direction: Math.random() > 0.5 ? 'BUY' : 'SELL',
    gift_nifty: Math.round(23500 + rand(-80, 80)),
    gift_nifty_bias: ['BULLISH', 'NEUTRAL', 'BEARISH'][Math.floor(Math.random() * 3)],
    gift_nifty_gap: Math.round(rand(-60, 60)),
    fii_futures_net: Math.round(rand(-50000, 50000)),
    market_open: false,
    expiry_day: false,
    timestamp: new Date().toISOString(),
  }
}

export default function useSignals() {
  const [signals, setSignals] = useState({})
  const [macro, setMacro] = useState({})
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const prevSignals = useRef({})

  // Fetch initial data from REST API
  const fetchSignals = useCallback(async () => {
    try {
      const [sigRes, macroRes] = await Promise.all([
        fetch(`${API_BASE}/signals`),
        fetch(`${API_BASE}/macro`),
      ])

      if (!sigRes.ok || !macroRes.ok) throw new Error('API not available')

      const sigData = await sigRes.json()
      const macroData = await macroRes.json()

      prevSignals.current = signals
      setSignals(sigData)
      setMacro(macroData)
      setLastUpdate(new Date().toISOString())
      setLoading(false)
    } catch (e) {
      // Fallback to mock data when backend is not running
      console.warn('Backend not available, using mock data')
      prevSignals.current = signals
      setSignals(generateMockSignals())
      setMacro(generateMockMacro())
      setLastUpdate(new Date().toISOString())
      setLoading(false)
    }
  }, [])

  // Handle WebSocket message
  const handleWSMessage = useCallback((message) => {
    if (message.type === 'signals' && message.data) {
      prevSignals.current = signals
      setSignals(message.data)
      setLastUpdate(new Date().toISOString())
    }
  }, [signals])

  // Fetch on mount
  useEffect(() => {
    fetchSignals()
    // Also poll every 60s as fallback
    const interval = setInterval(fetchSignals, 60000)
    return () => clearInterval(interval)
  }, [fetchSignals])

  // Check if a signal changed (for animation triggers)
  const signalChanged = useCallback((index) => {
    const prev = prevSignals.current[index]?.signal
    const curr = signals[index]?.signal
    return prev && curr && prev !== curr
  }, [signals])

  return {
    signals,
    macro,
    loading,
    lastUpdate,
    handleWSMessage,
    signalChanged,
    refetch: fetchSignals,
  }
}
