/**
 * TRADEKING VIX Engine — WebSocket Hook
 * Connects to /ws/vix with reconnect + REST fallback.
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const FALLBACK_POLL_MS = 2000

export default function useVIXSocket(wsUrl) {
  const [status, setStatus] = useState('connecting')
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)
  const backoffRef = useRef(1000)
  const reconnectTimer = useRef(null)
  const pollTimer = useRef(null)
  const destroyed = useRef(false)

  useEffect(() => {
    destroyed.current = false

    function connect() {
      if (destroyed.current) return
      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          if (destroyed.current) return
          setStatus('connected')
          backoffRef.current = 1000
          // Stop fallback polling
          if (pollTimer.current) {
            clearInterval(pollTimer.current)
            pollTimer.current = null
          }
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            setLastMessage(data)
          } catch (e) { /* ignore */ }
        }

        ws.onclose = () => {
          if (destroyed.current) return
          setStatus('reconnecting')
          startFallbackPolling()
          scheduleReconnect()
        }

        ws.onerror = () => { ws.close() }
      } catch (e) {
        if (!destroyed.current) {
          setStatus('disconnected')
          startFallbackPolling()
          scheduleReconnect()
        }
      }
    }

    function scheduleReconnect() {
      if (destroyed.current) return
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      reconnectTimer.current = setTimeout(() => {
        if (!destroyed.current) {
          connect()
          backoffRef.current = Math.min(backoffRef.current * 2, 30000)
        }
      }, backoffRef.current)
    }

    function startFallbackPolling() {
      if (pollTimer.current || destroyed.current) return
      pollTimer.current = setInterval(async () => {
        try {
          const res = await fetch('/api/vix')
          if (res.ok) {
            const data = await res.json()
            setLastMessage({ type: 'vix_update', vix: data, trade_signals: data.trade_signals || [], index_prices: data.index_prices || {} })
          }
        } catch (e) { /* ignore */ }
      }, FALLBACK_POLL_MS)
    }

    connect()

    return () => {
      destroyed.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (pollTimer.current) clearInterval(pollTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [wsUrl])

  return { status, lastMessage }
}
