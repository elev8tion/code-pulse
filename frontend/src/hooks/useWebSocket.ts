import { useEffect, useRef, useCallback } from 'react'
import { WSMessage } from '../types'

const WS_URL = `ws://${window.location.host}/ws`
const RECONNECT_DELAY_MS = 3000

type MessageHandler = (msg: WSMessage) => void
type StatusHandler = (connected: boolean) => void

export function useWebSocket(
  onMessage: MessageHandler,
  onStatusChange?: StatusHandler,
) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onMessageRef = useRef(onMessage)
  const onStatusRef = useRef(onStatusChange)

  // Keep refs current without triggering reconnects
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])
  useEffect(() => { onStatusRef.current = onStatusChange }, [onStatusChange])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      onStatusRef.current?.(true)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage
        if (msg.type !== 'ping') {
          onMessageRef.current(msg)
        }
      } catch (err) {
        // Log malformed WebSocket messages to aid debugging in development
        console.warn('[CodePulse] Failed to parse WebSocket message:', err)
      }
    }

    ws.onclose = () => {
      onStatusRef.current?.(false)
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])
}
