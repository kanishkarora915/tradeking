/**
 * TRADEKING — WebSocket Hook
 * Connects to /ws/live with auto-reconnect and exponential backoff.
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/live`
const MAX_BACKOFF = 30000
const INITIAL_BACKOFF = 1000

export default function useWebSocket(onMessage) {
  const [status, setStatus] = useState('connecting') // 'connected' | 'connecting' | 'reconnecting' | 'disconnected'
  const wsRef = useRef(null)
  const backoffRef = useRef(INITIAL_BACKOFF)
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        backoffRef.current = INITIAL_BACKOFF
      }

      ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') return
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (e) {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        setStatus('reconnecting')
        scheduleReconnect()
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch (e) {
      setStatus('disconnected')
      scheduleReconnect()
    }
  }, [onMessage])

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    reconnectTimer.current = setTimeout(() => {
      setStatus('reconnecting')
      connect()
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF)
    }, backoffRef.current)
  }, [connect])

  useEffect(() => {
    connect()
    // Ping every 30 seconds to keep alive
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => {
      clearInterval(pingInterval)
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { status }
}
