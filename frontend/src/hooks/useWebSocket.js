/**
 * TRADEKING — WebSocket Hook
 * Connects to /ws/live with auto-reconnect and exponential backoff.
 * Fixed: uses ref for onMessage to prevent reconnect loops.
 */
import { useEffect, useRef, useState } from 'react'

const MAX_BACKOFF = 30000
const INITIAL_BACKOFF = 1000

export default function useWebSocket(onMessage) {
  const [status, setStatus] = useState('connecting')
  const wsRef = useRef(null)
  const backoffRef = useRef(INITIAL_BACKOFF)
  const reconnectTimer = useRef(null)
  const onMessageRef = useRef(onMessage)

  // Keep callback ref updated without triggering reconnect
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    let destroyed = false

    function connect() {
      if (destroyed) return

      try {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const ws = new WebSocket(`${protocol}://${window.location.host}/ws/live`)
        wsRef.current = ws

        ws.onopen = () => {
          if (destroyed) return
          setStatus('connected')
          backoffRef.current = INITIAL_BACKOFF
        }

        ws.onmessage = (event) => {
          try {
            if (event.data === 'pong') return
            const data = JSON.parse(event.data)
            onMessageRef.current?.(data)
          } catch (e) {
            // ignore
          }
        }

        ws.onclose = () => {
          if (destroyed) return
          setStatus('reconnecting')
          scheduleReconnect()
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch (e) {
        if (!destroyed) {
          setStatus('disconnected')
          scheduleReconnect()
        }
      }
    }

    function scheduleReconnect() {
      if (destroyed) return
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      reconnectTimer.current = setTimeout(() => {
        if (!destroyed) {
          connect()
          backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF)
        }
      }, backoffRef.current)
    }

    connect()

    // Ping every 30 seconds to keep alive
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => {
      destroyed = true
      clearInterval(pingInterval)
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on intentional close
        wsRef.current.close()
      }
    }
  }, []) // empty deps — connect once, never re-trigger

  return { status }
}
