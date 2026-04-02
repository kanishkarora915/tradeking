/**
 * TRADEKING — Signal State Management Hook
 * NO MOCK DATA — only real API data.
 */
import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = '/api'

export default function useSignals() {
  const [signals, setSignals] = useState({})
  const [macro, setMacro] = useState({})
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const prevSignals = useRef({})

  const fetchSignals = useCallback(async () => {
    try {
      const [sigRes, macroRes] = await Promise.all([
        fetch(`${API_BASE}/signals`),
        fetch(`${API_BASE}/macro`),
      ])

      if (!sigRes.ok || !macroRes.ok) throw new Error('API not available')

      const sigData = await sigRes.json()
      const macroData = await macroRes.json()

      setSignals(prev => {
        prevSignals.current = prev
        return sigData
      })
      setMacro(macroData)
      setLastUpdate(new Date().toISOString())
      setLoading(false)
    } catch (e) {
      console.warn('Backend not available:', e.message)
      setLoading(false)
    }
  }, [])

  // Stable callback — no dependency on signals state
  const handleWSMessage = useCallback((message) => {
    if (message.type === 'signals' && message.data) {
      setSignals(prev => {
        prevSignals.current = prev
        return message.data
      })
      setLastUpdate(new Date().toISOString())
    }
  }, [])

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 60000)
    return () => clearInterval(interval)
  }, [fetchSignals])

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
